"""Signal Finder - Investment signal extractor using Gemini API."""

import json
import logging
from typing import List, Tuple
from collections import Counter

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from models.post import AnalyzedPost, ScrapedPost, Sentiment, SignalStrength

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
다음은 주식 커뮤니티의 인기글 목록입니다. 각 글을 분석하여 투자 관점에서 유의미한 정보가 있는지 평가해주세요.
단순 유머글, 정치글, 주식과 무관한 잡담이라면 is_investment_related를 false로 설정하세요.

게시글 목록:
{posts_text}

분석 결과를 반드시 아래와 같은 구조의 JSON 배열(Array) 형식으로만 응답해주세요. 마크다운(```json) 없이 순수 JSON 문자열만 반환하세요.
[
  {{
      "post_id": "글 번호(id)",
      "is_investment_related": true/false, // 주식, 경제, 기업, 투자 심리, 매매 등과 관련된 글인지 여부
      "summary": "글의 핵심 내용을 1~2줄로 요약",
      "insight": "이 글에서 얻을 수 있는 투자 인사이트 (없으면 '인사이트 없음')",
      "tickers": ["삼성전자", "TSLA", "AAPL"], // 언급된 구체적 주식 종목명 (없으면 빈 배열)
      "keywords": ["금리", "실적", "숏", "나스닥"], // 시장 주요 키워드 (없으면 빈 배열)
      "sentiment": "BULLISH", // BULLISH(상승/매수/호재), BEARISH(하락/매도/악재), NEUTRAL(중립/관망) 중 택1
      "score": 85 // 0~100 사이의 점수. 유의미한 정보일수록 높게 (잡담이면 0)
  }}
]
"""

class GeminiExtractor:
    """Extract investment signals from scraped posts using Gemini LLM."""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def analyze(self, post: ScrapedPost) -> AnalyzedPost:
        """Analyze a single post using Gemini API."""
        return self.batch_analyze([post])[0] if self.batch_analyze([post]) else AnalyzedPost(post=post, score=0.0)

    def batch_analyze(self, posts: List[ScrapedPost]) -> List[AnalyzedPost]:
        """Analyze a list of posts in batches to avoid rate limits."""
        if not posts:
            return []

        results = []
        batch_size = 10
        
        import time
        
        for i in range(0, len(posts), batch_size):
            batch = posts[i:i+batch_size]
            
            # Build posts text block
            posts_text = ""
            for idx, p in enumerate(batch):
                posts_text += f"\n--- ID: {idx} ---\n"
                posts_text += f"게시판: {p.source_name}\n"
                posts_text += f"제목: {p.title}\n"
                posts_text += f"추천수: {p.upvotes} / 댓글수: {p.comment_count}\n"
                content_preview = p.content[:500] if p.content else "내용 없음"
                posts_text += f"본문: {content_preview}\n"
                if p.top_comments:
                    posts_text += f"댓글: {' / '.join(p.top_comments[:30])}\n"
            
            prompt = PROMPT_TEMPLATE.format(posts_text=posts_text)

            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                )
                
                # Parse JSON array
                parsed_array = json.loads(response.text)
                
                # Process each item in the parsed array
                for item in parsed_array:
                    try:
                        post_id = int(item.get("post_id", -1))
                        if post_id < 0 or post_id >= len(batch):
                            continue
                        
                        original_post = batch[post_id]
                        
                        if not item.get("is_investment_related", False):
                            continue

                        sent_str = item.get("sentiment", "NEUTRAL").upper()
                        if sent_str == "BULLISH":
                            sentiment = Sentiment.BULLISH
                            signal_type = "매수/긍정"
                        elif sent_str == "BEARISH":
                            sentiment = Sentiment.BEARISH
                            signal_type = "매도/부정"
                        else:
                            sentiment = Sentiment.NEUTRAL
                            signal_type = "중립/관망"

                        score = float(item.get("score", 0.0))
                        score += original_post.upvotes * 1.0
                        score += original_post.comment_count * 0.2
                        
                        if score >= 60:
                            strength = SignalStrength.HIGH
                        elif score >= 25:
                            strength = SignalStrength.MEDIUM
                        else:
                            strength = SignalStrength.LOW

                        tickers = item.get("tickers", [])
                        keywords = item.get("keywords", [])
                        insight = item.get("insight", "인사이트 없음")
                        if insight == "인사이트 없음" and tickers:
                            insight = f"관련 종목: {', '.join(tickers)}"

                        analyzed = AnalyzedPost(
                            post=original_post,
                            summary=item.get("summary", ""),
                            investment_insight=insight,
                            tickers=tickers,
                            keywords=keywords,
                            sentiment=sentiment,
                            signal_strength=strength,
                            comment_summary="\n".join((original_post.top_comments or [])[:3]),
                            score=score,
                        )
                        if analyzed.score > 0:
                            results.append(analyzed)
                    except Exception as parse_e:
                        logger.error(f"Failed to parse item from LLM: {parse_e}")
                        
            except Exception as e:
                logger.error(f"Gemini API batch error: {e}")
            
            # Avoid rate limit between batches
            if i + batch_size < len(posts):
                logger.info("Waiting 15 seconds to avoid Gemini rate limits...")
                time.sleep(15)

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def generate_executive_summary(self, analyzed_posts: List[AnalyzedPost]) -> str:
        """Generate a 3-line executive summary based on all analyzed posts of the batch."""
        if not analyzed_posts:
            return "수집된 유의미한 투자 인사이트가 없습니다."

        posts_info = ""
        for p in analyzed_posts[:30]:  # Limit to top 30 to save tokens
            posts_info += f"- [{p.sentiment.value}] {p.post.title} (키워드: {', '.join(p.keywords)})\n"
            posts_info += f"  요약: {p.summary}\n"

        prompt = f"""
다음은 오늘 주식 커뮤니티에서 수집된 주요 투자 관련 게시글의 요약 데이터입니다.
이 데이터들을 종합하여, 현재 개인 투자자들의 주요 관심 테마(섹터)와 전반적인 시장 심리(공포/탐욕 등)를 3줄로 간결하게 요약해주세요.

수집된 데이터:
{posts_info}

응답 형식 (반드시 마크다운 없이 순수 텍스트 3줄로만 답변할 것):
1. [시장 심리] ...
2. [주요 테마] ...
3. [투자 인사이트] ...
"""
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            return "일간 브리핑 생성에 실패했습니다."

    def extract_hot_keywords(
        self, posts: List[ScrapedPost], top_n: int = 10
    ) -> List[Tuple[str, int]]:
        """Return top N keywords across all posts."""
        # Note: Since batch_analyze now returns LLM-extracted keywords in the AnalyzedPost,
        # it's better to pass AnalyzedPost directly to a keyword extractor if we want perfect sync.
        # But for backward compatibility with main.py which calls this on raw ScrapedPost,
        # we will just return a placeholder or we can implement a fast regex fallback here 
        # to avoid double-calling the LLM just for keywords.
        # Actually, in main.py, `analyzed_posts` is computed first! So main.py should be refactored 
        # slightly to get keywords from analyzed_posts. For now, we will just return an empty list 
        # or implement a simple keyword counter based on the post titles.
        counter: Counter = Counter()
        # Fallback to simple title extraction to save API calls
        for post in posts:
            words = [w for w in post.title.split() if len(w) >= 2]
            counter.update(words)
        return counter.most_common(top_n)
