"""Tests for the Mer blog scraper and comment collector."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scrapers.merblog import MerBlogCommentCollector, MerBlogScraper


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class FakeMerBlogCommentCollector(MerBlogCommentCollector):
    """Deterministic collector for pagination tests."""

    def __init__(self, pages):
        super().__init__(npx_bin="npx")
        self.pages = pages
        self.index = 0

    def _open_post(self, url: str) -> None:
        return None

    def _open_comments(self, log_no: str) -> bool:
        return True

    def _wait_for_comment_list(self, log_no: str, timeout: float = 15.0) -> bool:
        return True

    def _wait_for_page_metrics(self, log_no: str, timeout: float = 8.0):
        return {"upvotes": 0, "comment_count": 0}

    def _rewind_to_first_page(self, log_no: str) -> None:
        self.index = 0

    def _extract_comment_page(self, log_no: str):
        return self.pages[self.index]

    def _go_to_next_page(self, log_no: str) -> bool:
        if self.index + 1 >= len(self.pages):
            return False
        self.index += 1
        return True

    def _wait_for_page_change(self, log_no: str, previous_page: int, timeout: float = 8.0) -> bool:
        return True

    def close(self) -> None:
        return None


class MerBlogScraperTest(unittest.TestCase):
    def test_parse_rss_filters_allowed_categories(self) -> None:
        xml_text = (FIXTURE_DIR / "merblog_rss.xml").read_text(encoding="utf-8")

        posts = MerBlogScraper.parse_rss(xml_text, max_posts=10)

        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].source, "merblog")
        self.assertEqual(posts[0].category, "경제/주식/국제정세/사회")
        self.assertEqual(posts[1].category, "주절주절")
        self.assertTrue(posts[0].url.endswith("/224261592600"))

    def test_extract_detail_fields(self) -> None:
        html = (FIXTURE_DIR / "merblog_post.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "lxml")

        detail = MerBlogScraper.extract_detail_fields(soup)

        self.assertEqual(detail["author"], "메르")
        self.assertEqual(detail["category"], "경제/주식/국제정세/사회")
        self.assertEqual(detail["upvotes"], 2194)
        self.assertEqual(detail["comment_count"], 112)
        self.assertIn("금리인하와 대차대조표 조정", detail["content"])
        self.assertEqual(detail["created_at"].year, 2026)

    def test_comment_collector_paginates_and_deduplicates(self) -> None:
        pages = json.loads((FIXTURE_DIR / "merblog_comment_pages.json").read_text(encoding="utf-8"))
        collector = FakeMerBlogCommentCollector(pages)

        comments = collector.collect("https://blog.naver.com/ranto28/224261592600", "224261592600", top_n=10)

        self.assertEqual(len(comments), 3)
        self.assertTrue(comments[0].startswith("[답글] 베르테:"))
        self.assertEqual(sum("베르테" in comment for comment in comments), 1)
        self.assertTrue(any("Money base" in comment for comment in comments))


if __name__ == "__main__":
    unittest.main()
