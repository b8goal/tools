"""Base scraper with shared HTTP session and utilities."""

import logging
import time
from abc import ABC, abstractmethod
from typing import List

import requests as _std_requests
from bs4 import BeautifulSoup
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from fake_useragent import UserAgent

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

REQUEST_EXCEPTION_TYPES = (_std_requests.RequestException,)
if CURL_CFFI_AVAILABLE:
    REQUEST_EXCEPTION_TYPES = (
        _std_requests.RequestException,
        curl_requests.RequestException,
    )

from config import Config, ScraperConfig
from models.post import ScrapedPost

logger = logging.getLogger(__name__)


def _retry_before_sleep_log(retry_state: RetryCallState):
    """Log retry metadata before sleeping between attempts."""
    scraper = retry_state.args[0] if retry_state.args else None
    url = retry_state.args[1] if len(retry_state.args) > 1 else "unknown-url"
    scraper_name = (
        scraper.scraper_config.name
        if scraper and hasattr(scraper, "scraper_config")
        else "unknown-scraper"
    )
    error = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "[%s] fetch_page retry before sleep (attempt=%s, url=%s, error=%s)",
        scraper_name,
        retry_state.attempt_number,
        url,
        error,
    )


def _retry_after_log(retry_state: RetryCallState):
    """Log retry metadata immediately after each call attempt."""
    scraper = retry_state.args[0] if retry_state.args else None
    url = retry_state.args[1] if len(retry_state.args) > 1 else "unknown-url"
    scraper_name = (
        scraper.scraper_config.name
        if scraper and hasattr(scraper, "scraper_config")
        else "unknown-scraper"
    )
    outcome_failed = bool(retry_state.outcome and retry_state.outcome.failed)
    error = retry_state.outcome.exception() if outcome_failed else None
    logger.debug(
        "[%s] fetch_page retry after attempt (attempt=%s, url=%s, failed=%s, error=%s)",
        scraper_name,
        retry_state.attempt_number,
        url,
        outcome_failed,
        error,
    )


class BaseScraper(ABC):
    """Abstract base class for community site scrapers."""

    def __init__(self, config: Config, scraper_config: ScraperConfig):
        self.config = config
        self.scraper_config = scraper_config

        if CURL_CFFI_AVAILABLE:
            # curl_cffi Session: Chrome TLS 핵거프린트 완전 위장
            self.session = curl_requests.Session(impersonate="chrome124")
            logger.debug("Using curl_cffi Session (Chrome impersonation)")
        else:
            # fallback: requests + 랜덤 UA
            ua = UserAgent(os='macos')
            self.session = _std_requests.Session()
            self.session.headers.update({
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            })
            logger.debug("Using requests Session (fallback)")

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        before_sleep=_retry_before_sleep_log,
        after=_retry_after_log,
        reraise=True,
    )
    def fetch_page(self, url: str, encoding: str = None) -> BeautifulSoup:
        """Fetch a page and return a BeautifulSoup object.

        Args:
            url: URL to fetch.
            encoding: Override response encoding (e.g., 'euc-kr').

        Returns:
            BeautifulSoup parsed HTML.

        Raises:
            RequestException: On HTTP errors.
        """
        import random
        # 약간의 추가 Jitter(1~3초)
        time.sleep(random.uniform(1.0, 3.0))

        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()

            if encoding:
                response.encoding = encoding

            return BeautifulSoup(response.text, "lxml")
        except REQUEST_EXCEPTION_TYPES as e:
            logger.error("[%s] Failed to fetch url=%s: %s", self.scraper_config.name, url, e)
            raise

    def rate_limit(self):
        """Sleep between requests to be polite (with Jitter)."""
        import random
        jitter = random.uniform(0.5, 2.0)
        time.sleep(self.config.request_delay + jitter)

    @abstractmethod
    def scrape_list(self) -> List[ScrapedPost]:
        """Scrape the board listing page for posts.

        Returns:
            List of ScrapedPost with basic info (title, url, upvotes, etc.).
        """
        ...

    @abstractmethod
    def scrape_detail(self, post: ScrapedPost) -> ScrapedPost:
        """Scrape a single post detail page to enrich content and comments.

        Args:
            post: ScrapedPost with at least url filled in.

        Returns:
            Enriched ScrapedPost with content and top_comments.
        """
        ...

    def scrape(self) -> List[ScrapedPost]:
        """Full scrape pipeline: list → filter → detail.

        Returns:
            List of ScrapedPost with content and comments filled in.
        """
        if not self.scraper_config.enabled:
            logger.info(f"[{self.scraper_config.name}] Scraper disabled, skipping.")
            return []

        logger.info(f"[{self.scraper_config.name}] Starting scrape...")

        try:
            posts = self.scrape_list()
        except Exception as e:
            logger.error(f"[{self.scraper_config.name}] List scrape failed: {e}")
            return []

        # Filter by minimum upvotes OR minimum comments
        filtered = [
            p for p in posts
            if p.upvotes >= self.scraper_config.min_upvotes
            or p.comment_count >= self.scraper_config.min_comments
        ]

        # Limit max posts
        filtered = filtered[: self.scraper_config.max_posts]

        logger.info(
            f"[{self.scraper_config.name}] {len(posts)} posts found, "
            f"{len(filtered)} passed filter (min upvotes: {self.scraper_config.min_upvotes} or min comments: {self.scraper_config.min_comments})"
        )

        # Scrape details for filtered posts
        enriched = []
        for post in filtered:
            try:
                self.rate_limit()
                enriched_post = self.scrape_detail(post)
                enriched.append(enriched_post)
            except Exception as e:
                logger.warning(
                    f"[{self.scraper_config.name}] Detail scrape failed for "
                    f"{post.url}: {e}"
                )
                # Still include the post with basic info
                enriched.append(post)

        logger.info(
            f"[{self.scraper_config.name}] Scrape complete: {len(enriched)} posts"
        )
        return enriched
