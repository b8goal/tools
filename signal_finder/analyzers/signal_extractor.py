"""Signal Finder - Investment signal extractor (keyword-based, v1).

LLM-free initial version: uses regex + keyword dictionaries to extract
investment signals, stock tickers/ETFs, and market sentiment from post text.
"""

import logging
import re
from collections import Counter
from typing import List, Tuple

from models.post import AnalyzedPost, ScrapedPost, Sentiment, SignalStrength

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyword dictionaries
# ---------------------------------------------------------------------------

# Korean stocks (종목명 → representative name)
KR_STOCKS: dict = {
    "삼성전자": "삼성전자",
    "삼전": "삼성전자",
    "하이닉스": "SK하이닉스",
    "sk하이닉스": "SK하이닉스",
    "현대차": "현대차",
    "기아": "기아",
    "셀트리온": "셀트리온",
    "카카오": "카카오",
    "네이버": "NAVER",
    "naver": "NAVER",
    "lg화학": "LG화학",
    "포스코": "POSCO",
    "한화오션": "한화오션",
    "한화에어로": "한화에어로스페이스",
    "두산에너빌": "두산에너빌리티",
    "조선": "조선주",
    "원전": "원전주",
    "방산": "방산주",
    "반도체": "반도체",
}

# US stocks (ticker + name)
US_STOCKS: dict = {
    "nvda": "NVDA",
    "nvidia": "NVDA",
    "tsla": "TSLA",
    "tesla": "TSLA",
    "aapl": "AAPL",
    "apple": "AAPL",
    "msft": "MSFT",
    "microsoft": "MSFT",
    "amzn": "AMZN",
    "amazon": "AMZN",
    "googl": "GOOGL",
    "goog": "GOOGL",
    "google": "GOOGL",
    "meta": "META",
    "asts": "ASTS",
    "amd": "AMD",
    "arm": "ARM",
    "intc": "INTC",
    "intel": "INTC",
    "smh": "SMH",
    "soxl": "SOXL",
    "tqqq": "TQQQ",
    "qqq": "QQQ",
    "spy": "SPY",
    "palantir": "PLTR",
    "pltr": "PLTR",
}

# Korean ETFs
KR_ETFS: dict = {
    "kodex": "KODEX",
    "tiger": "TIGER",
    "sol": "SOL",
    "kbstar": "KBSTAR",
    "hanaro": "HANARO",
    "arirang": "ARIRANG",
    "ace": "ACE",
}

# Macroeconomic & general market keywords
MACRO_KEYWORDS: List[str] = [
    "금리", "기준금리", "연준", "fed", "fomc",
    "인플레이션", "물가", "cpi", "pce",
    "환율", "달러", "원달러",
    "유가", "원유", "wti", "brent",
    "무역전쟁", "관세", "tariff",
    "이란", "중동", "호르무즈",
    "중국", "대만", "반도체법",
    "경기침체", "recession", "gdp",
    "트럼프", "바이든",
    "나스닥", "코스피", "코스닥", "국장", "미장", "증시", "주식",
    "배당", "etf", "포트폴리오", "실적", "어닝", "공매도", "숏", "롱",
]

# Bullish signal keywords
BULLISH_KEYWORDS: List[str] = [
    "매수", "사자", "올라간다", "상승", "급등", "상한가",
    "목표가 상향", "호실적", "어닝서프라이즈", "매수추천",
    "저점", "바닥", "반등", "돌파", "신고가",
    "수혜", "기대", "긍정", "호재", "좋아보", "좋아 보",
    "buy", "long", "bull",
]

# Bearish signal keywords
BEARISH_KEYWORDS: List[str] = [
    "매도", "팔자", "내려간다", "하락", "급락", "하한가",
    "목표가 하향", "어닝쇼크", "매도추천",
    "고점", "천장", "붕괴", "손절", "신저가",
    "악재", "우려", "위험", "리스크", "부정",
    "sell", "short", "bear",
]

# Watch / neutral keywords
WATCH_KEYWORDS: List[str] = [
    "관망", "지켜보자", "대기", "보류", "불확실",
    "혼조", "횡보", "모르겠", "애매",
    "wait", "hold",
]


# ---------------------------------------------------------------------------
# Ticker extraction regex
# ---------------------------------------------------------------------------

# US ticker: 2-5 uppercase letters (standalone, not inside a word)
US_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")

# Korean stock code: 6 digits
KR_CODE_RE = re.compile(r"\b(\d{6})\b")


class SignalExtractor:
    """Extract investment signals from scraped posts (keyword-based)."""

    def __init__(self):
        # Build lowercase lookup maps
        self._kr_map = {k.lower(): v for k, v in KR_STOCKS.items()}
        self._us_map = {k.lower(): v for k, v in US_STOCKS.items()}
        self._etf_map = {k.lower(): v for k, v in KR_ETFS.items()}

        # US tickers that should be recognised even without context
        self._known_us_tickers = {v for v in US_STOCKS.values()}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, post: ScrapedPost) -> AnalyzedPost:
        """Return an AnalyzedPost derived from a ScrapedPost."""
        text = self._combined_text(post)
        text_lower = text.lower()

        keywords = self._extract_keywords(text, text_lower)
        tickers = self._extract_tickers(text, text_lower)
        etfs = self._extract_etfs(text_lower)
        sentiment, signal_type = self._classify_sentiment(text_lower)
        signal_strength, score = self._compute_score(
            post, keywords, tickers, sentiment
        )
        insight = self._build_insight(post, tickers, etfs, sentiment, signal_type)
        top_comments = (post.top_comments or [])[:3]

        analyzed = AnalyzedPost(
            post=post,
            summary=text[:200],
            investment_insight=insight,
            tickers=tickers + etfs,
            keywords=keywords,
            sentiment=sentiment,
            signal_strength=signal_strength,
            comment_summary="\n".join(top_comments),
            score=score,
        )
        return analyzed

    def batch_analyze(self, posts: List[ScrapedPost]) -> List[AnalyzedPost]:
        """Analyze a list of posts and return sorted by score (desc)."""
        results = []
        for post in posts:
            try:
                analyzed = self.analyze(post)
                # 투자 인사이트가 없는 잡담/뻘글(유머 등) 필터링:
                # 종목(티커)이나 관련 키워드가 1개라도 존재하는 글만 취합
                if len(analyzed.tickers) > 0 or len(analyzed.keywords) > 0:
                    results.append(analyzed)
            except Exception as e:
                logger.warning(f"Analysis failed for '{post.title}': {e}")
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def extract_hot_keywords(
        self, posts: List[ScrapedPost], top_n: int = 10
    ) -> List[Tuple[str, int]]:
        """Return top N keywords across all posts (keyword, count) sorted desc."""
        counter: Counter = Counter()
        for post in posts:
            text_lower = self._combined_text(post).lower()
            kws = self._extract_keywords(
                self._combined_text(post), text_lower
            )
            for kw in kws:
                counter[kw] += 1
        return counter.most_common(top_n)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _combined_text(self, post: ScrapedPost) -> str:
        parts = [post.title, post.content or ""]
        parts.extend(post.top_comments or [])
        return " ".join(parts)

    def _extract_keywords(self, text: str, text_lower: str) -> List[str]:
        """Extract recognised stock / macro keywords from text."""
        found = []

        # Korean stocks
        for keyword, canonical in self._kr_map.items():
            if keyword in text_lower and canonical not in found:
                found.append(canonical)

        # US stocks
        for keyword, canonical in self._us_map.items():
            if keyword in text_lower and canonical not in found:
                found.append(canonical)

        # Macro keywords
        for kw in MACRO_KEYWORDS:
            if kw in text_lower and kw not in found:
                found.append(kw)

        # Raw US tickers found in uppercase text
        for match in US_TICKER_RE.finditer(text):
            ticker = match.group(1)
            if ticker in self._known_us_tickers and ticker not in found:
                found.append(ticker)

        return found

    def _extract_tickers(self, text: str, text_lower: str) -> List[str]:
        """Extract ticker symbols only (stocks), not macro terms."""
        found = []
        for keyword, canonical in self._kr_map.items():
            if keyword in text_lower and canonical not in found:
                found.append(canonical)
        for keyword, canonical in self._us_map.items():
            if keyword in text_lower and canonical not in found:
                found.append(canonical)
        # Direct uppercase tickers
        for match in US_TICKER_RE.finditer(text):
            ticker = match.group(1)
            if ticker in self._known_us_tickers and ticker not in found:
                found.append(ticker)
        return found

    def _extract_etfs(self, text_lower: str) -> List[str]:
        """Extract ETF brand mentions."""
        found = []
        for keyword, canonical in self._etf_map.items():
            if keyword in text_lower and canonical not in found:
                found.append(canonical)
        return found

    def _classify_sentiment(
        self, text_lower: str
    ) -> Tuple[Sentiment, str]:
        """Return (Sentiment enum, signal_type string)."""
        bull_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
        bear_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
        watch_count = sum(1 for kw in WATCH_KEYWORDS if kw in text_lower)

        if bull_count > bear_count and bull_count > watch_count:
            return Sentiment.BULLISH, "매수"
        elif bear_count > bull_count and bear_count > watch_count:
            return Sentiment.BEARISH, "매도"
        elif watch_count > 0:
            return Sentiment.NEUTRAL, "관망"
        else:
            return Sentiment.NEUTRAL, "중립"

    def _compute_score(
        self,
        post: ScrapedPost,
        keywords: List[str],
        tickers: List[str],
        sentiment: Sentiment,
    ) -> Tuple[SignalStrength, float]:
        """Compute signal score and strength."""
        score = 0.0

        # Engagement
        score += post.upvotes * 1.5
        score += post.comment_count * 0.5
        score += min(post.views / 100, 20)  # cap view bonus at 20

        # Keyword richness
        score += len(tickers) * 3.0
        score += len(keywords) * 1.0

        # Sentiment directional bonus
        if sentiment != Sentiment.NEUTRAL:
            score += 5.0

        if score >= 60:
            strength = SignalStrength.HIGH
        elif score >= 25:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.LOW

        return strength, score

    def _build_insight(
        self,
        post: ScrapedPost,
        tickers: List[str],
        etfs: List[str],
        sentiment: Sentiment,
        signal_type: str,
    ) -> str:
        """Build a short human-readable insight string."""
        parts = []

        if signal_type not in ("중립", "관망"):
            parts.append(f"📌 신호: {signal_type}")

        sent_emoji = {
            Sentiment.BULLISH: "📈",
            Sentiment.BEARISH: "📉",
            Sentiment.NEUTRAL: "➡️",
        }.get(sentiment, "➡️")
        parts.append(f"{sent_emoji} {sentiment.value}")

        if tickers:
            parts.append(f"관련 종목: {', '.join(tickers[:5])}")

        if etfs:
            parts.append(f"ETF: {', '.join(etfs[:3])}")

        if post.category:
            parts.append(f"카테고리: {post.category}")

        return " | ".join(parts) if parts else "인사이트 없음"
