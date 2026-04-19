"""클리앙 주식한당 scraper (v2 - placeholder).

클리앙 주식한당은 소모임 구조 + 로그인 필요하여
초기 버전에서는 미지원. 2차 버전에서 Playwright 기반으로 구현 예정.
"""

import logging
from typing import List

from scrapers.base import BaseScraper
from models.post import ScrapedPost

logger = logging.getLogger(__name__)


class ClienScraper(BaseScraper):
    """Placeholder scraper for Clien 주식한당 (v2).

    Requires:
    - Login authentication
    - Access to 소모임 (somoim) subsection
    - Potentially Playwright for JS-rendered content
    """

    SOURCE = "clien"
    SOURCE_NAME = "클리앙 주식한당"

    def scrape_list(self) -> List[ScrapedPost]:
        """Not yet implemented."""
        logger.info(
            f"[{self.SOURCE_NAME}] v2 기능 - 아직 미구현 (로그인 필요)"
        )
        return []

    def scrape_detail(self, post: ScrapedPost) -> ScrapedPost:
        """Not yet implemented."""
        return post
