"""DC Inside 미국주식 갤러리 (미주갤) scraper."""

import logging
import re
from typing import List

from scrapers.base import BaseScraper
from models.post import ScrapedPost

logger = logging.getLogger(__name__)


class DcinsideScraper(BaseScraper):
    """Scraper for DC Inside US Stock minor gallery."""

    SOURCE = "dcinside"
    SOURCE_NAME = "DC 미주갤"

    LIST_URL = "https://gall.dcinside.com/mgallery/board/lists?id=stockus&exception_mode=recommend"
    BASE_URL = "https://gall.dcinside.com"

    # Priority headings (머리말) that indicate quality posts
    PRIORITY_HEADINGS = {"💡정보", "📰뉴스", "🌟베스트", "🔥HIT", "📚도서관", "✏매매공시"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # DC Inside needs referer header
        self.session.headers.update(
            {
                "Referer": "https://gall.dcinside.com/",
            }
        )

    def scrape_list(self) -> List[ScrapedPost]:
        """Scrape DC Inside 미주갤 board list."""
        soup = self.fetch_page(self.LIST_URL)
        posts = []

        # DC Inside uses table-like structure with class 'ub-content'
        rows = soup.select("tr.ub-content.us-post")

        if not rows:
            # Fallback selectors
            rows = soup.select("tr.ub-content")

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
        """Parse a DC Inside gallery row."""
        # Check if it's an ad or notice
        data_type = row.get("data-type", "")
        if data_type == "icon_notice":
            return None

        # Post number (to filter out ads/notices)
        num_el = row.select_one("td.gall_num")
        if num_el:
            num_text = num_el.get_text(strip=True)
            if num_text in ("공지", "설문", "AD", "광고"):
                return None

        # Title and URL
        title_el = row.select_one("td.gall_tit a:not(.reply_numbox)")
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")

        if href.startswith("/"):
            url = self.BASE_URL + href
        elif href.startswith("http"):
            url = href
        else:
            return None

        # Heading/Category (머리말)
        category = ""
        heading_el = row.select_one("td.gall_subject, em.icon_txt")
        if heading_el:
            category = heading_el.get_text(strip=True)

        # Upvotes (추천)
        upvotes = 0
        rec_el = row.select_one("td.gall_recommend")
        if rec_el:
            try:
                upvotes = int(rec_el.get_text(strip=True))
            except ValueError:
                pass

        # Views (조회수)
        views = 0
        count_el = row.select_one("td.gall_count")
        if count_el:
            try:
                views = int(count_el.get_text(strip=True))
            except ValueError:
                pass

        # Comment count
        comment_count = 0
        reply_el = row.select_one("a.reply_numbox span, .reply_num")
        if reply_el:
            try:
                comment_count = int(
                    re.sub(r"[^\d]", "", reply_el.get_text())
                )
            except ValueError:
                pass

        # Author
        author = ""
        writer_el = row.select_one(
            "td.gall_writer .nickname, td.gall_writer em"
        )
        if writer_el:
            author = writer_el.get_text(strip=True)

        # Give bonus score to priority headings
        bonus = 0
        if category in self.PRIORITY_HEADINGS:
            bonus = 10  # effectively bypasses min_upvotes filter

        return ScrapedPost(
            title=title,
            url=url,
            source=self.SOURCE,
            source_name=self.SOURCE_NAME,
            author=author,
            upvotes=upvotes + bonus,
            views=views,
            comment_count=comment_count,
            category=category,
        )

    def scrape_detail(self, post: ScrapedPost) -> ScrapedPost:
        """Scrape post detail page."""
        soup = self.fetch_page(post.url)

        # Post body
        content_el = soup.select_one("div.write_div, div.writing_view_box")
        if content_el:
            for tag in content_el.select(
                "script, style, img, iframe, .og_div"
            ):
                tag.decompose()
            post.content = content_el.get_text(strip=True)[:2000]

        # Comments
        comments = []
        comment_els = soup.select("li.ub-content p.usertxt")
        for cel in comment_els[:5]:
            text = cel.get_text(strip=True)[:200]
            if text:
                comments.append(text)
        post.top_comments = comments[:3]

        return post
