"""KoreaPas (고파스) 경제 게시판 scraper."""

import logging
import re
from typing import List
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from models.post import ScrapedPost

logger = logging.getLogger(__name__)


class KoreapasScraper(BaseScraper):
    """Scraper for KoreaPas economy board (zboard-based)."""

    SOURCE = "koreapas"
    SOURCE_NAME = "고파스 경제"

    LIST_URL = "https://www.koreapas.com/bbs/zboard.php?id=econo"
    BASE_URL = "https://www.koreapas.com/bbs"

    def __init__(self, config, scraper_config):
        super().__init__(config, scraper_config)
        if config.koreapas_cookie:
            # 헤더에 직접 설정
            self.session.headers.update({"Cookie": config.koreapas_cookie})
            
            # 쿠키 파싱하여 세션 쿠키 자(Jar)에도 설정 (curl_cffi 호환성)
            try:
                for cookie_item in config.koreapas_cookie.split(";"):
                    if "=" in cookie_item:
                        name, value = cookie_item.strip().split("=", 1)
                        self.session.cookies.set(name, value, domain="www.koreapas.com")
                        self.session.cookies.set(name, value, domain="koreapas.com")
            except Exception as e:
                logger.warning(f"[고파스] 쿠키 파싱 중 오류 발생: {e}")
            
            logger.info("[고파스] 로그인 쿠키가 세션에 적용되었습니다.")

    def scrape_list(self) -> List[ScrapedPost]:
        """Scrape KoreaPas economy board list.

        KoreaPas uses zboard with `tr.list0/list1/list_notice` rows.
        The current layout exposes comment count and views in fixed columns.
        """
        # KoreaPas pages are effectively served in a CP949-compatible encoding.
        try:
            soup = self.fetch_page(self.LIST_URL, encoding="cp949")
        except Exception:
            soup = self.fetch_page(self.LIST_URL)

        posts = []

        rows = soup.select("tr.list_notice, tr.list0, tr.list1")

        for row in rows:
            try:
                post = self._parse_list_row(row)
                if post:
                    posts.append(post)
            except Exception as e:
                logger.debug(f"Failed to parse row: {e}")
                continue

        return posts

    def _parse_list_row(self, row) -> ScrapedPost:
        """Parse a zboard table row."""
        cols = row.select("td")
        if len(cols) < 6:
            return None

        row_classes = set(row.get("class", []))
        category = cols[0].get_text(" ", strip=True).lstrip("#").strip()
        if "list_notice" in row_classes or category == "공지":
            return None

        # Title rows have a dedicated detail link with page/divpage params.
        title_link = row.select_one('a[href*="view.php?id=econo&page="]')
        if not title_link:
            return None

        title = title_link.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if not title or len(title) < 2:
            return None

        if title in ("제목", "공지", "", "새로고침"):
            return None

        href = title_link.get("href", "")
        if "view.php" not in href.lower() or "no=" not in href.lower():
            return None

        url = urljoin(self.BASE_URL + "/", href)
        comment_count = self._parse_int(cols[1].get_text(" ", strip=True))
        views = self._parse_int(cols[4].get_text(" ", strip=True))

        return ScrapedPost(
            title=title,
            url=url,
            source=self.SOURCE,
            source_name=self.SOURCE_NAME,
            author="익명",
            upvotes=0,
            views=views,
            comment_count=comment_count,
            category=category,
        )

    def scrape_detail(self, post: ScrapedPost) -> ScrapedPost:
        """Scrape post detail page."""
        try:
            soup = self.fetch_page(post.url, encoding="cp949")
        except Exception:
            soup = self.fetch_page(post.url)

        author_el = soup.select_one("#memo_all span.daum")
        if author_el:
            post.author = author_el.get_text(strip=True)

        views_el = soup.select_one('#memo_all span.midbtn.mbox[title="조회수"] span')
        if views_el:
            post.views = self._parse_int(views_el.get_text(" ", strip=True))

        # Post body lives under #bonmoon on the current layout.
        content_el = soup.select_one('#bonmoon div[itemprop="articleBody"], #bonmoon td')
        if content_el:
            for tag in content_el.select(
                'script, style, img, iframe, form, input, span[style*="#f5f5f5"], span[style*="#fafafa"]'
            ):
                tag.decompose()
            post.content = self._normalize_text(content_el.get_text("\n", strip=True))[:2000]

        comments = []
        comment_els = soup.select("td.hansb")
        for cel in comment_els[:30]:  # 최대 30개까지 수집 (사용자 요청 반영)
            for tag in cel.select(
                'script, style, form, input, div[id^="report"], span[style*="#fafafa"], span[style*="#f5f5f5"]'
            ):
                tag.decompose()
            text = self._normalize_text(cel.get_text("\n", strip=True))[:200]
            if text:
                comments.append(text)
        post.top_comments = comments[:30]

        return post

    @staticmethod
    def _parse_int(text: str) -> int:
        digits = re.sub(r"[^\d]", "", text or "")
        return int(digits) if digits else 0

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()
