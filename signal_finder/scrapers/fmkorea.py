"""FM Korea 주식 게시판 scraper."""

import logging
import re
from typing import List
from datetime import datetime

from scrapers.base import BaseScraper
from models.post import ScrapedPost

logger = logging.getLogger(__name__)


class FMKoreaScraper(BaseScraper):
    """Scraper for FM Korea stock board (XpressEngine-based)."""

    SOURCE = "fmkorea"
    SOURCE_NAME = "FM Korea 주식"

    # Popular posts URL (sorted by popularity)
    # listStyle=list ensures table format is returned
    LIST_URL = "https://www.fmkorea.com/index.php?mid=stock&sort_index=pop&order_type=desc&listStyle=list"
    BASE_URL = "https://www.fmkorea.com"

    def scrape_list(self) -> List[ScrapedPost]:
        """Scrape FM Korea stock board list sorted by popularity."""
        soup = self.fetch_page(self.LIST_URL)
        posts = []

        # table.bd_lst tbody tr — class없는 일반 게시글 row만 선택
        # notice 클래스를 가진 공지사항은 제외
        table = soup.find("table", class_="bd_lst")
        if not table:
            logger.warning("[FM Korea] table.bd_lst not found")
            return posts

        rows = table.select("tbody tr")
        for row in rows:
            classes = row.get("class", [])
            # 공지사항 행 스킵
            if any("notice" in c for c in classes):
                continue
            try:
                post = self._parse_list_row(row)
                if post:
                    posts.append(post)
            except Exception as e:
                logger.debug(f"Failed to parse row: {e}")
                continue

        return posts

    def _parse_text_list(self, soup) -> List[ScrapedPost]:
        """Parse the text-based post list (fallback parser)."""
        posts = []

        # Find all links that point to individual posts (numeric document_srl)
        post_links = soup.select('a[href*="/9"]')  # FM Korea post URLs have numeric IDs

        seen_urls = set()
        for link in post_links:
            href = link.get("href", "")
            title = link.get_text(strip=True)

            # Only process actual post links (not navigation, comments, etc.)
            if not title or len(title) < 5:
                continue

            # Normalize URL
            # href: /index.php?...&document_srl=XXXX 또는 /XXXX 형태
            match = re.search(r"document_srl=(\d+)", href)
            if match:
                url = f"{self.BASE_URL}/{match.group(1)}"
            elif href.startswith("/"):
                url = self.BASE_URL + href
            elif href.startswith("http"):
                url = href
            else:
                continue

            # Skip non-post links
            if "#comment" in url or "act=" in url or "mid=" in url:
                continue

            # Deduplicate
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Try to extract upvote count from nearby elements
            upvotes = 0
            parent = link.parent
            if parent:
                vote_el = parent.select_one(".voted_count, .vote_num, .vr_num")
                if vote_el:
                    try:
                        upvotes = int(re.sub(r"[^\d]", "", vote_el.get_text()))
                    except ValueError:
                        pass

                # Try to find comment count
                comment_el = parent.select_one(".comment_count, .reply_count")
                comment_count = 0
                if comment_el:
                    try:
                        comment_count = int(
                            re.sub(r"[^\d]", "", comment_el.get_text())
                        )
                    except ValueError:
                        pass

            # Find category
            category = ""
            category_el = (
                parent.select_one(".category, .cate") if parent else None
            )
            if category_el:
                category = category_el.get_text(strip=True)

            post = ScrapedPost(
                title=title,
                url=url,
                source=self.SOURCE,
                source_name=self.SOURCE_NAME,
                upvotes=upvotes,
                comment_count=comment_count,
                category=category,
            )
            posts.append(post)

        return posts

    def _parse_list_row(self, row) -> ScrapedPost:
        """Parse a single list row element."""
        # Title and URL
        title_el = row.select_one("a.title, h3.title a, a")
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")

        if href.startswith("/"):
            url = self.BASE_URL + href
        else:
            url = href

        # 추천수: class에 m_no와 m_no_voted를 함께 가진 td
        upvotes = 0
        vote_el = row.find("td", class_="m_no_voted")
        if vote_el:
            try:
                upvotes = int(re.sub(r"[^\d]", "", vote_el.get_text(strip=True)))
            except ValueError:
                pass

        # 댓글수: a.replyNum
        comment_count = 0
        reply_el = row.select_one("a.replyNum")
        if reply_el:
            try:
                comment_count = int(re.sub(r"[^\d]", "", reply_el.get_text()))
            except ValueError:
                pass

        # 조회수: td.m_no 중 m_no_voted가 아닌 첫 번째
        views = 0
        all_m_no = row.select("td.m_no")
        for el in all_m_no:
            if "m_no_voted" not in el.get("class", []):
                try:
                    views = int(re.sub(r"[^\d]", "", el.get_text()))
                    break
                except ValueError:
                    pass

        # 카테고리: td.cate
        category = ""
        cate_el = row.select_one("td.cate")
        if cate_el:
            category = cate_el.get_text(strip=True)

        return ScrapedPost(
            title=title,
            url=url,
            source=self.SOURCE,
            source_name=self.SOURCE_NAME,
            upvotes=upvotes,
            comment_count=comment_count,
            views=views,
            category=category,
        )

    def scrape_detail(self, post: ScrapedPost) -> ScrapedPost:
        """Scrape a single FM Korea post for content and comments."""
        soup = self.fetch_page(post.url)

        # Post body content
        content_el = soup.select_one("div.xe_content, div.rd_body, article.fr-view")
        if content_el:
            for tag in content_el.select("script, style, img, iframe"):
                tag.decompose()
            post.content = content_el.get_text(strip=True)[:2000]

        # Author
        author_el = soup.select_one("a.member_plate, .author a, .nick a, .user_info a")
        if author_el:
            post.author = author_el.get_text(strip=True)

        # Top comments
        comments = []
        comment_els = soup.select("div.fdb_lst_ul li, div.comment_item, .re_body")
        for cel in comment_els[:5]:
            text_el = cel.select_one(".comment-content, .xe_content, .comment_memo")
            if text_el:
                comment_text = text_el.get_text(strip=True)[:200]
                if comment_text:
                    comments.append(comment_text)
        post.top_comments = comments[:3]

        return post

    def scrape_trending_keywords(self) -> List[str]:
        """Scrape trending search keywords from FM Korea stock board."""
        try:
            soup = self.fetch_page(
                "https://www.fmkorea.com/index.php?mid=stock"
            )
            keywords = []
            # The search ranking section
            keyword_els = soup.select("div.search_rank a, .keyword_rank a")
            for el in keyword_els:
                kw = el.get_text(strip=True)
                # Clean up ranking number
                kw = re.sub(r"^\d+\.\s*", "", kw)
                kw = re.sub(r"\s*(new|\+\d+|-\d+)\s*$", "", kw)
                if kw:
                    keywords.append(kw)
            return keywords
        except Exception as e:
            logger.warning(f"Failed to scrape trending keywords: {e}")
            return []
