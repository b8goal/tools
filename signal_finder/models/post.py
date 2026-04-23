"""Data models for scraped and analyzed posts."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SignalStrength(Enum):
    """Investment signal strength level."""

    HIGH = "🔴 높음"
    MEDIUM = "🟡 중간"
    LOW = "🟢 낮음"


class Sentiment(Enum):
    """Market sentiment classification."""

    BULLISH = "📈 상승"
    BEARISH = "📉 하락"
    NEUTRAL = "➡️ 혼조"


@dataclass
class ScrapedPost:
    """A post scraped from a community site."""

    title: str
    url: str
    source: str  # site identifier: fmkorea, koreapas, dcinside, ppomppu, clien
    source_name: str  # display name: FM Korea 주식, 고파스 경제, etc.

    author: str = ""
    created_at: Optional[datetime] = None
    upvotes: int = 0
    comment_count: int = 0
    views: int = 0
    category: str = ""
    content: str = ""  # post body text
    top_comments: list = field(default_factory=list)  # list of comment strings

    scraped_at: datetime = field(default_factory=datetime.now)


@dataclass
class AnalyzedPost:
    """A post with extracted investment signals."""

    post: ScrapedPost

    # Analysis results
    summary: str = ""  # brief summary of the post
    investment_insight: str = ""  # investment implication
    tickers: list = field(default_factory=list)  # extracted stock tickers/names
    keywords: list = field(default_factory=list)  # investment keywords
    sentiment: Sentiment = Sentiment.NEUTRAL
    signal_strength: SignalStrength = SignalStrength.LOW
    comment_summary: str = ""  # summary of top comments

    score: float = 0.0  # calculated relevance score
    evidence_types: list = field(default_factory=list)  # structured evidence hints from LLM/rules

    # Recommendation ranking results
    recommendation_score: float = 0.0
    specificity_score: float = 0.0
    actionability_score: float = 0.0
    noise_score: float = 0.0
    recommendation_passed: bool = False
    rejection_reasons: list = field(default_factory=list)
