"""Signal Finder - Configuration management."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ScraperConfig:
    """Configuration for a specific scraper."""

    name: str
    url: str
    min_upvotes: int = 5
    min_comments: int = 5  # 댓글 수 기반 필터 조건 추가
    enabled: bool = True
    max_posts: int = 20


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Notion
    notion_token: str = ""
    notion_parent_page_id: str = ""
    
    # LLM (Gemini)
    gemini_api_key: str = ""

    # Executive summary (Codex CLI)
    codex_summary_model: str = ""

    # Alerting
    alert_webhook_url: str = ""

    # Scraping
    scrape_interval_minutes: int = 60
    request_timeout: int = 15
    request_delay: float = 2.0  # seconds between requests

    # User-Agent for HTTP requests
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    # Per-site configurations
    scrapers: dict = field(default_factory=dict)
    
    # Session Cookies
    koreapas_cookie: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls(
            notion_token=os.getenv("NOTION_TOKEN", ""),
            notion_parent_page_id=os.getenv("NOTION_PARENT_PAGE_ID", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            codex_summary_model=os.getenv("CODEX_SUMMARY_MODEL", ""),
            alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL", ""),
            scrape_interval_minutes=int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60")),
            koreapas_cookie=os.getenv("KOREAPAS_COOKIE", ""),
        )

        config.scrapers = {
            "fmkorea": ScraperConfig(
                name="FM Korea 주식",
                url="https://www.fmkorea.com/index.php?mid=stock&sort_index=pop&order_type=desc",
                min_upvotes=int(os.getenv("MIN_UPVOTES_FMKOREA", "10")),
                min_comments=20,
            ),
            "koreapas": ScraperConfig(
                name="고파스 경제",
                url="https://www.koreapas.com/bbs/zboard.php?id=econo",
                min_upvotes=int(os.getenv("MIN_UPVOTES_KOREAPAS", "3")),
                min_comments=5,  # 추천이 없어도 댓글이 5개 이상이면 핫한 글로 취급
            ),
            "dcinside": ScraperConfig(
                name="DC 미주갤",
                url="https://gall.dcinside.com/mgallery/board/lists?id=stockus&exception_mode=recommend",
                min_upvotes=int(os.getenv("MIN_UPVOTES_DC", "5")),
                min_comments=10,
            ),
            "ppomppu": ScraperConfig(
                name="뽐뿌 증권포럼",
                url="https://www.ppomppu.co.kr/zboard/zboard.php?id=stock",
                min_upvotes=int(os.getenv("MIN_UPVOTES_PPOMPPU", "5")),
                min_comments=10,
            ),
            "clien": ScraperConfig(
                name="클리앙 주식한당",
                url="https://www.clien.net/service/board/somoim",
                min_upvotes=3,
                enabled=False,  # v2 - requires login
            ),
        }

        return config
