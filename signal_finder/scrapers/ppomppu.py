"""뽐뿌 증권포럼 scraper."""

import logging
import re
from typing import List

from scrapers.base import BaseScraper
from models.post import ScrapedPost

logger = logging.getLogger(__name__)


class PpomppuScraper(BaseScraper):
    """Scraper for Ppomppu stock forum (zboard-based).

    Note: Ppomppu returns 403 without proper headers/cookies.
    Additional session setup is needed.
    """

    SOURCE = "ppomppu"
    SOURCE_NAME = "뽐뿌 증권포럼"

    LIST_URL = "https://www.ppomppu.co.kr/zboard/zboard.php?id=stock"
    BASE_URL = "https://www.ppomppu.co.kr/zboard"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ppomppu requires specific headers to avoid 403
        self.session.headers.update(
            {
                "Referer": "https://www.ppomppu.co.kr/",
                "Host": "www.ppomppu.co.kr",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        # Warm up session by visiting main page first
        self._warmup_done = False

    def _warmup(self):
        """Visit main page first to get cookies."""
        if self._warmup_done:
            return
        try:
            self.session.get(
                "https://www.ppomppu.co.kr/",
                timeout=self.config.request_timeout,
            )
            self._warmup_done = True
            self.rate_limit()
        except Exception as e:
            logger.warning(f"Ppomppu warmup failed: {e}")

    def scrape_list(self) -> List[ScrapedPost]:
        """Scrape Ppomppu stock board list."""
        self._warmup()

        soup = self.fetch_page(self.LIST_URL)
        posts = []

        # Ppomppu zboard structure
        rows = soup.select("tr.common-list0, tr.common-list1, tr.list0, tr.list1")

        if not rows:
            # Broader fallback
            table = soup.select_one("table.board_table, table#revolution_main_table")
            if table:
                rows = table.select("tr")

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
        """Parse a Ppomppu table row."""
        cols = row.select("td")
        if len(cols) < 4:
            return None

        # Find title link
        title_link = None
        for col in cols:
            link = col.select_one("a.list_title, a.title, a[href*='view']")
            if link:
                title_link = link
                break

        if not title_link:
            # Try any link with view in href
            for col in cols:
                for link in col.select("a"):
                    href = link.get("href", "")
                    if "view" in href or ("no=" in href and "id=" in href):
                        title_link = link
                        break
                if title_link:
                    break

        if not title_link:
            return None

        title = title_link.get_text(strip=True)
        if not title or len(title) < 2:
            return None

        href = title_link.get("href", "")
        if href.startswith("http"):
            url = href
        elif href.startswith("/"):
            url = "https://www.ppomppu.co.kr" + href
        else:
            url = self.BASE_URL + "/" + href

        # Extract numeric fields
        upvotes = 0
        views = 0
        comment_count = 0
        author = ""

        for col in cols:
            col_class = col.get("class", [])
            col_class_str = (
                " ".join(col_class) if isinstance(col_class, list) else str(col_class)
            )
            col_text = col.get_text(strip=True)

            if "votes" in col_class_str or "vote" in col_class_str:
                try:
                    # Ppomppu shows upvotes - downvotes, extract first number
                    nums = re.findall(r"\d+", col_text)
                    if nums:
                        upvotes = int(nums[0])
                except (ValueError, IndexError):
                    pass
            elif "hit" in col_class_str or "count" in col_class_str:
                try:
                    views = int(re.sub(r"[^\d]", "", col_text))
                except ValueError:
                    pass
            elif "name" in col_class_str or "user" in col_class_str:
                author = col_text

        # Comment count from title [N]
        comment_match = re.search(r"\[(\d+)\]", title)
        if comment_match:
            comment_count = int(comment_match.group(1))
            title = re.sub(r"\s*\[\d+\]\s*", "", title).strip()

        return ScrapedPost(
            title=title,
            url=url,
            source=self.SOURCE,
            source_name=self.SOURCE_NAME,
            author=author,
            upvotes=upvotes,
            views=views,
            comment_count=comment_count,
        )

    def scrape_detail(self, post: ScrapedPost) -> ScrapedPost:
        """Scrape post detail page."""
        self._warmup()
        soup = self.fetch_page(post.url)

        # Post body
        content_el = soup.select_one(
            "div.sub_read_body, td.board-contents, div.content"
        )
        if content_el:
            for tag in content_el.select("script, style, img, iframe"):
                tag.decompose()
            post.content = content_el.get_text(strip=True)[:2000]

        # Comments
        comments = []
        comment_els = soup.select("div.comment_line, td.comment")
        for cel in comment_els[:5]:
            text = cel.get_text(strip=True)[:200]
            if text:
                comments.append(text)
        post.top_comments = comments[:3]

        return post
