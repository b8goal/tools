"""Naver Mer blog scraper."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, List
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

from models.post import ScrapedPost
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


ALLOWED_CATEGORIES = {"경제/주식/국제정세/사회", "주절주절"}


@dataclass
class MerBlogComment:
    """Single collected blog comment."""

    author: str
    content: str
    created_at: str
    recommendation_count: int = 0
    depth: int = 0


class MerBlogCommentCollector:
    """Collect Naver blog comments through Playwright CLI."""

    def __init__(
        self,
        npx_bin: str | None = None,
        session_name: str | None = None,
        timeout_seconds: int = 45,
        workdir: str | None = None,
    ) -> None:
        self.npx_bin = npx_bin or os.getenv("NPX_BIN") or shutil.which("npx")
        self.session_name = session_name or f"sm{os.getpid() % 100000}{int(time.time()) % 100000}"
        self.timeout_seconds = timeout_seconds
        self.workdir = workdir or str(Path(__file__).resolve().parents[1])
        self.available = bool(self.npx_bin)

    def close(self) -> None:
        """Close the browser session."""
        if not self.available:
            return
        self._run_playwright(["--session", self.session_name, "close"], raw=False, check=False, timeout=15)

    def collect(self, url: str, log_no: str, top_n: int = 10, max_pages: int = 20) -> list[str]:
        """Return top comment snippets for a blog post."""
        return self.collect_post_data(url, log_no, top_n=top_n, max_pages=max_pages)["top_comments"]

    def collect_post_data(self, url: str, log_no: str, top_n: int = 10, max_pages: int = 20) -> dict[str, Any]:
        """Return rendered engagement metrics and top comment snippets."""
        if not self.available:
            return {"upvotes": 0, "comment_count": 0, "top_comments": []}

        self._open_post(url)
        metrics = self._wait_for_page_metrics(log_no)
        if not self._open_comments(log_no):
            return {**metrics, "top_comments": []}
        if not self._wait_for_comment_list(log_no):
            return {**metrics, "top_comments": []}

        comments = self._collect_comment_pages(log_no, max_pages=max_pages)
        return {
            **metrics,
            "top_comments": [self._format_comment(comment) for comment in self._select_top_comments(comments, top_n=top_n)],
        }

    def _collect_comment_pages(self, log_no: str, max_pages: int = 20) -> list[MerBlogComment]:
        self._rewind_to_first_page(log_no)

        collected: list[MerBlogComment] = []
        visited_pages: set[int] = set()
        while len(visited_pages) < max_pages:
            page_data = self._extract_comment_page(log_no)
            current_page = int(page_data.get("current_page", 1) or 1)
            if current_page in visited_pages:
                break
            visited_pages.add(current_page)

            for item in page_data.get("items", []):
                comment = self._build_comment(item)
                if comment:
                    collected.append(comment)

            total_pages = int(page_data.get("total_pages", current_page) or current_page)
            has_next = bool(page_data.get("has_next"))
            if not has_next or current_page >= total_pages:
                break
            if not self._go_to_next_page(log_no):
                break
            if not self._wait_for_page_change(log_no, current_page):
                break

        return collected

    def _build_comment(self, item: dict[str, Any]) -> MerBlogComment | None:
        content = self._normalize_comment_text(item.get("content", ""))
        if not content:
            return None

        author = self._normalize_comment_text(item.get("author", ""))
        created_at = self._normalize_comment_text(item.get("created_at", ""))
        recommendation_count = self._safe_int(item.get("recommendation_count", 0))
        depth = self._safe_int(item.get("depth", 0))
        return MerBlogComment(
            author=author,
            content=content,
            created_at=created_at,
            recommendation_count=recommendation_count,
            depth=depth,
        )

    def _open_post(self, url: str) -> None:
        self._run_playwright(["--session", self.session_name, "open", url], raw=False, timeout=120)

    def _open_comments(self, log_no: str) -> bool:
        expression = (
            f"(() => {{ const button = document.querySelector('#Comi{log_no}') "
            f"|| document.querySelector('#btn_comment_2'); if (!button) return false; "
            f"button.click(); return true; }})()"
        )
        return bool(self._evaluate_json(expression))

    def _wait_for_comment_list(self, log_no: str, timeout: float = 15.0) -> bool:
        expression = (
            f"(() => document.querySelectorAll('#naverComment_201_{log_no}_ct .u_cbox_comment').length)()"
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            count = self._safe_int(self._evaluate_json(expression))
            if count > 0:
                return True
            time.sleep(0.5)
        return False

    def _wait_for_page_metrics(self, log_no: str, timeout: float = 8.0) -> dict[str, int]:
        deadline = time.time() + timeout
        last_metrics = {"upvotes": 0, "comment_count": 0}
        while time.time() < deadline:
            metrics = self._extract_page_metrics(log_no)
            last_metrics = metrics
            if metrics["upvotes"] > 0 or metrics["comment_count"] > 0:
                return metrics
            time.sleep(0.4)
        return last_metrics

    def _rewind_to_first_page(self, log_no: str) -> None:
        guard = 0
        while guard < 30:
            page_data = self._extract_comment_page(log_no)
            current_page = int(page_data.get("current_page", 1) or 1)
            if current_page <= 1:
                return
            if not self._go_to_previous_page(log_no):
                return
            if not self._wait_for_page_change(log_no, current_page):
                return
            guard += 1

    def _extract_comment_page(self, log_no: str) -> dict[str, Any]:
        expression = f"""
        (() => {{
          const container = document.querySelector('#naverComment_201_{log_no}_ct');
          if (!container) {{
            return {{ current_page: 1, total_pages: 1, has_next: false, items: [] }};
          }}

          const parseCount = (text) => {{
            const match = String(text || '').match(/\\d+/g);
            if (!match) return 0;
            return Math.max(...match.map((value) => parseInt(value, 10) || 0));
          }};

          const comments = Array.from(container.querySelectorAll('.u_cbox_list .u_cbox_comment')).map((el) => {{
            let depth = 0;
            let parent = el.parentElement ? el.parentElement.closest('.u_cbox_comment') : null;
            while (parent) {{
              depth += 1;
              parent = parent.parentElement ? parent.parentElement.closest('.u_cbox_comment') : null;
            }}

            const box = Array.from(el.children).find((child) => child.classList && child.classList.contains('u_cbox_comment_box'))
              || el.querySelector('.u_cbox_comment_box');
            const author = box?.querySelector('.u_cbox_name_area, .u_cbox_nick, .u_cbox_name')?.textContent || '';
            const content = box?.querySelector('.u_cbox_contents, .u_cbox_text_wrap')?.textContent || '';
            const createdAt = box?.querySelector('.u_cbox_date')?.textContent || '';
            const recommendationCount = Math.max(
              0,
              ...Array.from(box?.querySelectorAll('.u_cbox_cnt_recomm') || []).map((node) => parseCount(node.textContent))
            );

            return {{
              author: author.trim(),
              content: content.trim(),
              created_at: createdAt.trim(),
              recommendation_count: recommendationCount,
              depth,
            }};
          }}).filter((item) => item.content);

          const currentPage = parseInt(container.querySelector('._currentPageNo')?.textContent || '1', 10) || 1;
          const totalPages = parseInt(container.querySelector('._lastPageNo')?.textContent || '1', 10) || 1;
          const hasNext = Boolean(container.querySelector('._naverCommentNext:not(.dimmed)'));

          return {{
            current_page: currentPage,
            total_pages: totalPages,
            has_next: hasNext,
            items: comments,
          }};
        }})()
        """
        return self._evaluate_json(expression) or {"current_page": 1, "total_pages": 1, "has_next": False, "items": []}

    def _extract_page_metrics(self, log_no: str) -> dict[str, int]:
        expression = f"""
        (() => {{
          const parseCount = (text) => {{
            const match = String(text || '').match(/\\d+/g);
            if (!match) return 0;
            return Math.max(...match.map((value) => parseInt(value, 10) || 0));
          }};

          const upvotes = Math.max(
            0,
            ...Array.from(document.querySelectorAll('.area_sympathy .u_likeit_text._count.num, .area_sympathy .u_likeit_list_count._count'))
              .map((node) => parseCount(node.textContent))
          );
          const commentCount = Math.max(
            0,
            ...Array.from(document.querySelectorAll('#commentCount, #floating_bottom_commentCount, ._commentCount'))
              .map((node) => parseCount(node.textContent))
          );

          return {{ upvotes, comment_count: commentCount }};
        }})()
        """
        return self._evaluate_json(expression) or {"upvotes": 0, "comment_count": 0}

    def _go_to_previous_page(self, log_no: str) -> bool:
        expression = (
            f"(() => {{ const button = document.querySelector('#naverComment_201_{log_no}_ct ._naverCommentPrev:not(.dimmed)'); "
            f"if (!button) return false; button.click(); return true; }})()"
        )
        return bool(self._evaluate_json(expression))

    def _go_to_next_page(self, log_no: str) -> bool:
        expression = (
            f"(() => {{ const button = document.querySelector('#naverComment_201_{log_no}_ct ._naverCommentNext:not(.dimmed)'); "
            f"if (!button) return false; button.click(); return true; }})()"
        )
        return bool(self._evaluate_json(expression))

    def _wait_for_page_change(self, log_no: str, previous_page: int, timeout: float = 8.0) -> bool:
        expression = f"(() => document.querySelector('#naverComment_201_{log_no}_ct ._currentPageNo')?.textContent?.trim() || '1')()"
        deadline = time.time() + timeout
        while time.time() < deadline:
            current_page = self._safe_int(self._evaluate_json(expression), default=previous_page)
            if current_page != previous_page:
                return True
            time.sleep(0.4)
        return False

    def _evaluate_json(self, expression: str) -> Any:
        return self._run_playwright(
            ["--session", self.session_name, "eval", expression],
            raw=True,
            timeout=self.timeout_seconds,
        )

    def _run_playwright(self, args: List[str], raw: bool, timeout: int, check: bool = True) -> Any:
        cmd = [
            self.npx_bin,
            "--yes",
            "--package",
            "@playwright/cli",
            "playwright-cli",
        ]
        if raw:
            cmd.append("--raw")
        cmd.extend(args)

        result = subprocess.run(
            cmd,
            cwd=self.workdir,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip()
        if check and result.returncode != 0:
            raise RuntimeError(output or f"Playwright CLI exited with code {result.returncode}.")
        if not raw:
            return output
        if not output:
            return None
        return json.loads(output)

    @staticmethod
    def _normalize_comment_text(text: str) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        return normalized[:280]

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_comment_datetime(value: str) -> datetime:
        match = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}):(\d{2})", value or "")
        if not match:
            return datetime.min
        return datetime(
            year=int(match.group(1)),
            month=int(match.group(2)),
            day=int(match.group(3)),
            hour=int(match.group(4)),
            minute=int(match.group(5)),
        )

    @classmethod
    def _select_top_comments(cls, comments: Iterable[MerBlogComment], top_n: int = 10) -> list[MerBlogComment]:
        deduped: dict[tuple[str, str, str], MerBlogComment] = {}
        for comment in comments:
            key = (comment.author, comment.content, comment.created_at)
            existing = deduped.get(key)
            if existing is None or comment.recommendation_count > existing.recommendation_count:
                deduped[key] = comment

        ranked = sorted(
            deduped.values(),
            key=lambda item: (
                item.recommendation_count,
                cls._parse_comment_datetime(item.created_at),
                -item.depth,
            ),
            reverse=True,
        )
        return ranked[:top_n]

    @staticmethod
    def _format_comment(comment: MerBlogComment) -> str:
        prefix = "[답글] " if comment.depth > 0 else ""
        if comment.author:
            return f"{prefix}{comment.author}: {comment.content}"[:280]
        return f"{prefix}{comment.content}"[:280]


class MerBlogScraper(BaseScraper):
    """Scraper for Naver Mer blog."""

    SOURCE = "merblog"
    SOURCE_NAME = "네이버 메르 블로그"
    BLOG_ID = "ranto28"
    BLOG_URL = f"https://blog.naver.com/{BLOG_ID}"
    RSS_URL = f"https://rss.blog.naver.com/{BLOG_ID}.xml"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session.headers.update({"Referer": self.BLOG_URL})
        self._comment_collector: MerBlogCommentCollector | None = None

    def scrape(self) -> List[ScrapedPost]:
        """Custom pipeline: RSS list -> latest allowed posts -> detail parsing."""
        if not self.scraper_config.enabled:
            logger.info(f"[{self.scraper_config.name}] Scraper disabled, skipping.")
            return []

        logger.info(f"[{self.scraper_config.name}] Starting scrape...")
        try:
            posts = self.scrape_list()
        except Exception as exc:
            logger.error(f"[{self.scraper_config.name}] RSS scrape failed: {exc}")
            return []

        logger.info(
            f"[{self.scraper_config.name}] {len(posts)} candidate posts found in allowed categories"
        )
        if not posts:
            return []

        collector = MerBlogCommentCollector(workdir=str(Path(__file__).resolve().parents[1]))
        if not collector.available:
            logger.warning("[%s] npx not found; comments will be skipped.", self.scraper_config.name)
            collector = None

        enriched: list[ScrapedPost] = []
        self._comment_collector = collector
        try:
            for post in posts[: self.scraper_config.max_posts]:
                try:
                    self.rate_limit()
                    enriched.append(self.scrape_detail(post))
                except Exception as exc:
                    logger.warning(
                        f"[{self.scraper_config.name}] Detail scrape failed for {post.url}: {exc}"
                    )
                    enriched.append(post)
        finally:
            if collector is not None:
                collector.close()
            self._comment_collector = None

        logger.info(f"[{self.scraper_config.name}] Scrape complete: {len(enriched)} posts")
        return enriched

    def scrape_list(self) -> List[ScrapedPost]:
        """Load latest allowed posts from the blog RSS feed."""
        response = self.session.get(self.RSS_URL, timeout=self.config.request_timeout)
        response.raise_for_status()
        return self.parse_rss(response.text, max_posts=self.scraper_config.max_posts)

    def scrape_detail(self, post: ScrapedPost) -> ScrapedPost:
        """Scrape full post detail and comments."""
        log_no = self.extract_log_no(post.url)
        detail_url = self.build_post_view_url(log_no) if log_no else post.url
        soup = self.fetch_page(detail_url)
        detail = self.extract_detail_fields(soup)

        post.author = detail.get("author", post.author)
        post.category = detail.get("category", post.category)
        post.content = detail.get("content", post.content)
        post.upvotes = detail.get("upvotes", post.upvotes)
        post.comment_count = detail.get("comment_count", post.comment_count)
        post.created_at = post.created_at or detail.get("created_at")

        collector = self._comment_collector
        if collector and log_no and post.comment_count > 0:
            try:
                rendered = collector.collect_post_data(detail_url, log_no, top_n=10)
                post.upvotes = rendered.get("upvotes", post.upvotes) or post.upvotes
                post.comment_count = rendered.get("comment_count", post.comment_count) or post.comment_count
                post.top_comments = rendered.get("top_comments", [])
            except Exception as exc:
                logger.warning(
                    "[%s] Comment collection failed for %s: %s",
                    self.scraper_config.name,
                    post.url,
                    exc,
                )
                post.top_comments = []

        return post

    @classmethod
    def parse_rss(cls, xml_text: str, max_posts: int = 10) -> List[ScrapedPost]:
        """Parse RSS XML into filtered ScrapedPost rows."""
        soup = BeautifulSoup(xml_text, "xml")
        items: list[ScrapedPost] = []
        seen_urls: set[str] = set()

        for item in soup.find_all("item"):
            title = cls._safe_text(item.find("title"))
            category = cls._safe_text(item.find("category")).strip()
            url = cls._canonicalize_url(cls._safe_text(item.find("guid")) or cls._safe_text(item.find("link")))
            created_at = cls._parse_rss_datetime(cls._safe_text(item.find("pubDate")))

            if not title or not url:
                continue
            if category not in ALLOWED_CATEGORIES:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            items.append(
                ScrapedPost(
                    title=title,
                    url=url,
                    source=cls.SOURCE,
                    source_name=cls.SOURCE_NAME,
                    category=category,
                    created_at=created_at,
                )
            )

        return items[:max_posts]

    @classmethod
    def extract_detail_fields(cls, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract detail fields from a post page."""
        title = cls._extract_text(
            soup,
            "div.se-module.se-title-text span, div.se-title-text span, div.pcol1 .se-title-text span",
        )
        author = cls._extract_text(soup, "span.nick a, span.nick")
        category = cls._extract_text(soup, "div.blog2_series a")
        created_at = cls._parse_detail_datetime(cls._extract_text(soup, "span.se_publishDate"))
        content = cls._extract_content(soup)
        upvotes = cls._extract_max_count(
            soup.select(
                "div.area_sympathy .u_likeit_text._count.num, "
                "div.area_sympathy .u_likeit_list_count._count"
            )
        )
        comment_count = cls._extract_max_count(
            soup.select("em#commentCount, em#floating_bottom_commentCount, em._commentCount")
        )

        return {
            "title": title,
            "author": author,
            "category": category,
            "created_at": created_at,
            "content": content,
            "upvotes": upvotes,
            "comment_count": comment_count,
        }

    @classmethod
    def extract_log_no(cls, url: str) -> str:
        """Return numeric post id from a canonical blog URL."""
        match = re.search(r"/(\d{9,})$", cls._canonicalize_url(url))
        return match.group(1) if match else ""

    @classmethod
    def build_post_view_url(cls, log_no: str) -> str:
        """Return the PostView URL that exposes the full desktop DOM."""
        return f"https://blog.naver.com/PostView.naver?blogId={cls.BLOG_ID}&logNo={log_no}"

    @classmethod
    def _extract_content(cls, soup: BeautifulSoup) -> str:
        content_el = soup.select_one("div.se-main-container")
        if not content_el:
            return ""

        content_clone = BeautifulSoup(str(content_el), "lxml")
        for tag in content_clone.select(
            "script, style, img, iframe, video, button, figure, svg, "
            ".se-module-oglink, .se-oglink, .se-image, .se-video, .se-sticker, .se-file"
        ):
            tag.decompose()

        parts: list[str] = []
        for node in content_clone.select("p, li"):
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            if text and text not in parts:
                parts.append(text)

        content = "\n".join(parts).strip()
        if not content:
            content = re.sub(r"\s+", " ", content_clone.get_text("\n", strip=True)).strip()
        return content[:6000]

    @classmethod
    def _extract_text(cls, soup: BeautifulSoup, selector: str) -> str:
        node = soup.select_one(selector)
        if not node:
            return ""
        return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()

    @staticmethod
    def _extract_max_count(nodes: Iterable[Any]) -> int:
        counts = []
        for node in nodes:
            digits = re.sub(r"[^\d]", "", node.get_text(" ", strip=True))
            if digits:
                counts.append(int(digits))
        return max(counts) if counts else 0

    @classmethod
    def _canonicalize_url(cls, url: str) -> str:
        if not url:
            return ""
        parts = urlsplit(url.strip())
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _safe_text(node: Any) -> str:
        if not node:
            return ""
        return node.get_text(" ", strip=True) if hasattr(node, "get_text") else str(node).strip()

    @staticmethod
    def _parse_rss_datetime(value: str) -> datetime | None:
        if not value:
            return None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed

    @staticmethod
    def _parse_detail_datetime(value: str) -> datetime | None:
        match = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{1,2}):(\d{2})", value or "")
        if not match:
            return None
        return datetime(
            year=int(match.group(1)),
            month=int(match.group(2)),
            day=int(match.group(3)),
            hour=int(match.group(4)),
            minute=int(match.group(5)),
        )
