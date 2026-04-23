"""Signal Finder - Investment signal extractor using Gemini API."""

import json
import logging
from typing import List, Tuple
from collections import Counter

from analyzers.text_summary import build_comment_summary, build_post_summary

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:  # pragma: no cover - optional dependency in local runs
    genai = None
    HarmCategory = None
    HarmBlockThreshold = None

from models.post import AnalyzedPost, ScrapedPost, Sentiment, SignalStrength

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
다음은 주식 커뮤니티의 인기글 목록입니다. 각 글을 분석하여 투자 관점에서 유의미한지, 그리고 실제 추천할 만한 품질인지 구분해주세요.
단순 유머글, 밈글, 반응형 제목, 정치글, 욕설 위주 글, 종목/이벤트 근거가 없는 감정 배설은 추천 대상으로 보지 마세요.

평가 기준:
- is_investment_related: 주식, 경제, 기업, 투자 심리, 매매와 실제로 관련 있는지
- is_recommendworthy: 실제로 데일리 추천 리스트에 넣을 만한 품질인지
- specificity_score(0~5): 글이 얼마나 구체적인 정보/종목/이벤트를 담고 있는지
- actionability_score(0~5): 독자가 투자 판단에 바로 활용할 수 있는지
- noise_score(0~5): 밈, 잡담, 욕설, 반응형 제목 등 노이즈가 얼마나 큰지
- evidence_type: 글의 근거 유형들. 가능한 값 예시 ["ticker", "macro", "earnings", "guidance", "valuation", "price_data", "supply_chain", "policy", "positioning"]

few-shot 예시:
[
  {{
    "title": "숏충이들 보면 로켓단같음",
    "label": {{
      "is_investment_related": true,
      "is_recommendworthy": false,
      "specificity_score": 1,
      "actionability_score": 0,
      "noise_score": 5,
      "rejection_reasons": ["meme_title_low_specificity", "weak_keyword_only"]
    }}
  }},
  {{
    "title": "???: 아빠 씨발 장난해 지금???",
    "label": {{
      "is_investment_related": false,
      "is_recommendworthy": false,
      "specificity_score": 0,
      "actionability_score": 0,
      "noise_score": 5,
      "rejection_reasons": ["meme_title_low_specificity", "short_text"]
    }}
  }},
  {{
    "title": "실시간 숏충이 표정...",
    "label": {{
      "is_investment_related": true,
      "is_recommendworthy": false,
      "specificity_score": 1,
      "actionability_score": 0,
      "noise_score": 4,
      "rejection_reasons": ["meme_title_low_specificity", "short_text"]
    }}
  }},
  {{
    "title": "케빈 워시 연준 의장 후보자 발언 정리",
    "label": {{
      "is_investment_related": true,
      "is_recommendworthy": true,
      "specificity_score": 5,
      "actionability_score": 4,
      "noise_score": 1,
      "rejection_reasons": []
    }}
  }},
  {{
    "title": "오늘자 씨티의 메모리 업체들의 LTA 예상",
    "label": {{
      "is_investment_related": true,
      "is_recommendworthy": true,
      "specificity_score": 5,
      "actionability_score": 4,
      "noise_score": 1,
      "rejection_reasons": []
    }}
  }},
  {{
    "title": "나비타스 세미컨덕터 NVTS 관련 자료 모음",
    "label": {{
      "is_investment_related": true,
      "is_recommendworthy": true,
      "specificity_score": 5,
      "actionability_score": 5,
      "noise_score": 1,
      "rejection_reasons": []
    }}
  }}
]

게시글 목록:
{posts_text}

분석 결과를 반드시 아래와 같은 구조의 JSON 배열(Array) 형식으로만 응답해주세요. 마크다운(```json) 없이 순수 JSON 문자열만 반환하세요.
[
  {{
      "post_id": "글 번호(id)",
      "is_investment_related": true/false, // 주식, 경제, 기업, 투자 심리, 매매 등과 관련된 글인지 여부
      "is_recommendworthy": true/false, // 데일리 추천에 넣을 만한 품질인지 여부
      "summary": "글의 핵심 내용을 1~2줄로 요약",
      "comment_summary": "댓글 반응의 핵심을 1~2줄로 요약. 댓글이 없으면 빈 문자열",
      "insight": "이 글에서 얻을 수 있는 투자 인사이트 (없으면 '인사이트 없음')",
      "tickers": ["삼성전자", "TSLA", "AAPL"], // 언급된 구체적 주식 종목명 (없으면 빈 배열)
      "keywords": ["금리", "실적", "숏", "나스닥"], // 시장 주요 키워드 (없으면 빈 배열)
      "evidence_type": ["ticker", "macro"], // 근거 유형 (없으면 빈 배열)
      "sentiment": "BULLISH", // BULLISH(상승/매수/호재), BEARISH(하락/매도/악재), NEUTRAL(중립/관망) 중 택1
      "score": 85, // 0~100 사이의 기본 관련성 점수. 유의미한 정보일수록 높게 (잡담이면 0)
      "specificity_score": 4, // 0~5
      "actionability_score": 3, // 0~5
      "noise_score": 1, // 0~5
      "rejection_reasons": [] // 예: ["short_text", "weak_keyword_only", "meme_title_low_specificity", "no_ticker_or_strong_macro"]
  }}
]
"""

class GeminiExtractor:
    """Extract investment signals from scraped posts using Gemini LLM."""

    def __init__(self, api_key: str):
        if genai is None:
            raise RuntimeError(
                "google-generativeai is not installed. Install it to use Gemini extraction."
            )
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def analyze(self, post: ScrapedPost) -> AnalyzedPost:
        """Analyze a single post using Gemini API."""
        analyzed_posts = self.batch_analyze([post])
        return analyzed_posts[0] if analyzed_posts else AnalyzedPost(post=post, score=0.0)

    def batch_analyze(self, posts: List[ScrapedPost]) -> List[AnalyzedPost]:
        """Analyze a list of posts in batches to avoid rate limits."""
        if not posts:
            return []

        results = []
        batch_size = 10
        fallback_extractor = None
        
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

                        score = self._clamp_score(item.get("score", 0.0), max_value=100.0)
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
                        if isinstance(tickers, str):
                            tickers = [tickers]
                        elif not isinstance(tickers, list):
                            tickers = []
                        if isinstance(keywords, str):
                            keywords = [keywords]
                        elif not isinstance(keywords, list):
                            keywords = []
                        evidence_types = item.get("evidence_type", [])
                        if isinstance(evidence_types, str):
                            evidence_types = [evidence_types]
                        insight = item.get("insight", "인사이트 없음")
                        if insight == "인사이트 없음" and tickers:
                            insight = f"관련 종목: {', '.join(tickers)}"

                        specificity_score = self._clamp_score(item.get("specificity_score", 0), max_value=5.0)
                        actionability_score = self._clamp_score(item.get("actionability_score", 0), max_value=5.0)
                        noise_score = self._clamp_score(item.get("noise_score", 0), max_value=5.0)
                        rejection_reasons = item.get("rejection_reasons", [])
                        if isinstance(rejection_reasons, str):
                            rejection_reasons = [rejection_reasons]
                        elif not isinstance(rejection_reasons, list):
                            rejection_reasons = []

                        summary = item.get("summary", "") or build_post_summary(
                            original_post.title,
                            original_post.content or "",
                        )
                        comment_summary = item.get("comment_summary", "") or build_comment_summary(
                            (original_post.top_comments or [])[:3]
                        )

                        analyzed = AnalyzedPost(
                            post=original_post,
                            summary=summary,
                            investment_insight=insight,
                            tickers=tickers,
                            keywords=keywords,
                            evidence_types=evidence_types,
                            sentiment=sentiment,
                            signal_strength=strength,
                            comment_summary=comment_summary,
                            score=score,
                            specificity_score=specificity_score,
                            actionability_score=actionability_score,
                            noise_score=noise_score,
                            recommendation_passed=bool(item.get("is_recommendworthy", False)),
                            rejection_reasons=rejection_reasons,
                        )
                        if analyzed.score > 0:
                            results.append(analyzed)
                    except Exception as parse_e:
                        logger.error(f"Failed to parse item from LLM: {parse_e}")
                        
            except Exception as e:
                logger.error(f"Gemini API batch error: {e}")
                if fallback_extractor is None:
                    from analyzers.signal_extractor import SignalExtractor

                    fallback_extractor = SignalExtractor()

                logger.warning(
                    "Falling back to local rule-based analysis for %s posts in the failed Gemini batch.",
                    len(batch),
                )
                results.extend(fallback_extractor.batch_analyze(batch))
            
            # Avoid rate limit between batches
            if i + batch_size < len(posts):
                logger.info("Waiting 15 seconds to avoid Gemini rate limits...")
                time.sleep(15)

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    @staticmethod
    def _clamp_score(value, max_value: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.0
        return max(0.0, min(max_value, parsed))

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
