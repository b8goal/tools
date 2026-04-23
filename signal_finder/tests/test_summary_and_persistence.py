"""Tests for local summaries, Notion formatting, and DB migration."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.signal_extractor import SignalExtractor
from models.db import DatabaseManager
from models.post import AnalyzedPost, ScrapedPost, SignalStrength
from notion_writer.manager import NotionManager


class SummaryAndPersistenceTest(unittest.TestCase):
    def test_signal_extractor_builds_post_and_comment_summary(self) -> None:
        extractor = SignalExtractor()
        post = ScrapedPost(
            title="메르 글 요약 테스트",
            url="https://example.com/merblog/1",
            source="merblog",
            source_name="네이버 메르 블로그",
            content=(
                "워시의 발언은 연준 독립성과 대차대조표 축소 논쟁을 다시 자극했다. "
                "시장에서는 장기금리 변동성과 성장주 밸류에이션 재평가 가능성을 함께 보고 있다."
            ),
            upvotes=10,
            comment_count=12,
            top_comments=[
                "베르테: MBS를 팔면 가격이 내려가고 금리는 반대로 올라간다고 보면 됩니다.",
                "이카루스: 실제로 정책까지 갈지는 몰라도 장기금리 변수는 체크해야겠네요.",
            ],
        )

        analyzed = extractor.analyze(post)

        self.assertIn("연준 독립성", analyzed.summary)
        self.assertIn("장기금리", analyzed.comment_summary)

    def test_notion_post_blocks_show_summary_and_comment_summary(self) -> None:
        manager = NotionManager.__new__(NotionManager)
        analyzed = AnalyzedPost(
            post=ScrapedPost(
                title="요약 표시 테스트",
                url="https://example.com/merblog/2",
                source="merblog",
                source_name="네이버 메르 블로그",
                upvotes=7,
                comment_count=4,
                top_comments=["댓글 원문 A", "댓글 원문 B"],
            ),
            summary="본문 요약이 여기에 표시됩니다.",
            comment_summary="댓글 핵심 반응이 여기에 표시됩니다.",
            signal_strength=SignalStrength.MEDIUM,
            recommendation_score=82.0,
            score=64.0,
        )

        blocks = manager._build_post_blocks(analyzed, "brown")
        rendered_lines = [
            block["paragraph"]["rich_text"][0]["text"]["content"]
            for block in blocks
            if block.get("type") == "paragraph"
        ]

        self.assertTrue(any("📝 본문 요약이 여기에 표시됩니다." in line for line in rendered_lines))
        self.assertTrue(any("💬 댓글 핵심 반응이 여기에 표시됩니다." in line for line in rendered_lines))
        self.assertFalse(any("댓글 원문 A" in line for line in rendered_lines))

    def test_database_manager_adds_comment_summary_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "signal.db"
            db = DatabaseManager(str(db_path))

            with sqlite3.connect(db_path) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(analyzed_posts)").fetchall()}

            self.assertIn("comment_summary", columns)


if __name__ == "__main__":
    unittest.main()
