"""Signal Finder - Notion API manager.

Manages daily Signal Finder pages in Notion with the following structure:

📊 Signal Finder - 2026-04-19
  ━━━━━━━━━━━━━━━━━━━━━
  📈 오늘의 핫 키워드: #삼전 #이란 ...
  ━━━━━━━━━━━━━━━━━━━━━
  ⏰ 16:00 수집
  ├── 🔵 FM Korea 주식 (3건)
  ...
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

import notion_client as notion_sdk

from config import Config
from models.post import AnalyzedPost, Sentiment, SignalStrength

logger = logging.getLogger(__name__)

# Source colour coding for Notion callout colours
SOURCE_COLORS = {
    "fmkorea":  "blue",
    "koreapas": "yellow",
    "dcinside": "green",
    "ppomppu":  "orange",
    "clien":    "gray",
    "merblog":  "brown",
}

SOURCE_EMOJI = {
    "fmkorea":  "🔵",
    "koreapas": "🟡",
    "dcinside": "🟢",
    "ppomppu":  "🟠",
    "clien":    "⚪",
    "merblog":  "🟤",
}

SOURCE_NAMES = {
    "fmkorea": "FM Korea 주식",
    "koreapas": "고파스 경제",
    "dcinside": "DC 미주갤",
    "ppomppu": "뽐뿌 증권포럼",
    "clien": "클리앙 주식한당",
    "merblog": "네이버 메르 블로그",
}


class NotionManager:
    """Manages Signal Finder daily pages in Notion."""

    def __init__(self, config: Config):
        if not config.notion_token:
            raise ValueError(
                "NOTION_TOKEN is not set. "
                "Set it in your .env file before running."
            )
        self.config = config
        self.client = notion_sdk.Client(auth=config.notion_token)
        self.parent_page_id = config.notion_parent_page_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_daily_page(self, date: datetime = None) -> str:
        """Create or retrieve the daily Signal Finder page.

        Returns:
            The Notion page ID.
        """
        if date is None:
            date = datetime.now()

        title = f"📊 Signal Finder - {date.strftime('%Y-%m-%d')}"
        existing_id = self._find_page_by_title(title)

        if existing_id:
            logger.info(f"Daily page already exists: {title}")
            self._ensure_navigation_blocks(existing_id)
            return existing_id

        logger.info(f"Creating daily page: {title}")
        page = self.client.pages.create(
            parent={"page_id": self.parent_page_id},
            properties={
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
            children=self._build_header_blocks(date),
        )
        return page["id"]

    def append_collection_section(
        self,
        page_id: str,
        analyzed_posts: List[AnalyzedPost],
        hot_keywords: List[Tuple[str, int]],
        collected_at: datetime = None,
        executive_summary: str = "",
    ) -> None:
        """Append a new hourly collection section to the daily page.

        Args:
            page_id: Notion page ID (from upsert_daily_page).
            analyzed_posts: List of analyzed posts (all sources combined).
            hot_keywords: List of (keyword, count) tuples from SignalExtractor.
            collected_at: Timestamp of collection (defaults to now).
            executive_summary: AI generated executive summary of the collection.
        """
        if collected_at is None:
            collected_at = datetime.now()

        blocks = []

        # ── Time heading ──
        time_str = collected_at.strftime("%H:%M")
        blocks.append(self._heading2(f"⏰ {time_str} 수집"))

        # ── Executive Summary ──
        if executive_summary:
            blocks.append(self._callout(f"🤖 AI 종합 트렌드 요약\n{executive_summary}", "🤖", "blue"))

        # ── Hot keywords callout ──
        if hot_keywords:
            kw_text = "  ".join(f"#{kw}" for kw, _ in hot_keywords[:10])
            blocks.append(self._callout(f"📈 핫 키워드: {kw_text}", "💡", "yellow"))

        # ── Per-source sections ──
        source_groups: dict = {}
        for post in analyzed_posts:
            src = post.post.source
            source_groups.setdefault(src, []).append(post)

        source_order = ["fmkorea", "koreapas", "dcinside", "ppomppu", "clien", "merblog"]
        for source in source_order:
            posts_for_source = source_groups.get(source, [])
            blocks.extend(
                self._build_source_section(source, posts_for_source)
            )

        # ── Divider ──
        blocks.append({"object": "block", "type": "divider", "divider": {}})

        # Notion API: max 100 blocks per request
        for chunk in self._chunk(blocks, 100):
            self.client.blocks.children.append(
                block_id=page_id,
                children=chunk,
            )

        logger.info(
            f"Appended {time_str} collection section "
            f"({len(analyzed_posts)} posts, {len(source_groups)} sources)"
        )

    # ------------------------------------------------------------------
    # Block builders
    # ------------------------------------------------------------------

    def _build_header_blocks(self, date: datetime) -> list:
        """Build the initial blocks for a new daily page."""
        date_str = date.strftime("%Y년 %m월 %d일 (%A)")
        return [
            self._callout(
                f"📅 {date_str} | 주식 커뮤니티 인사이트 자동 수집",
                "📊",
                "blue",
            ),
            self._paragraph("📚 목차", color="gray"),
            self._table_of_contents(),
            {"object": "block", "type": "divider", "divider": {}},
        ]

    def _build_source_section(
        self, source: str, posts: List[AnalyzedPost]
    ) -> list:
        """Build blocks for a single source's posts."""
        emoji = SOURCE_EMOJI.get(source, "⚫")
        source_name = posts[0].post.source_name if posts else SOURCE_NAMES.get(source, source)
        count = len(posts)
        color = SOURCE_COLORS.get(source, "default")

        blocks = []
        # Source heading (toggle-like via heading 3)
        blocks.append(
            self._heading3(f"{emoji} {source_name} ({count}건)")
        )

        if not posts:
            blocks.append(self._paragraph("수집된 게시글이 없습니다.", color="gray"))
            return blocks

        for ap in posts:
            blocks.extend(self._build_post_blocks(ap, color))

        return blocks

    def _build_post_blocks(self, ap: AnalyzedPost, color: str) -> list:
        """Build blocks for a single analyzed post."""
        blocks = []

        # Title as a bulleted list item with link
        title_text = f"📌 {ap.post.title}"
        title_block = {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": title_text, "link": {"url": ap.post.url}},
                        "annotations": {"bold": True},
                    }
                ],
                "color": color + "_background",
            },
        }
        blocks.append(title_block)

        # Stats line
        stats = (
            f"⬆️ 추천 {ap.post.upvotes} | 💬 댓글 {ap.post.comment_count}"
        )
        if ap.post.views:
            stats += f" | 👁 조회 {ap.post.views}"
        blocks.append(self._indent_paragraph(stats))

        if ap.summary:
            blocks.append(self._indent_paragraph(f"📝 {ap.summary}"))

        # Insight
        if ap.investment_insight:
            blocks.append(self._indent_paragraph(f"💡 {ap.investment_insight}"))

        # Keywords hashtags
        if ap.keywords:
            kw_str = "  ".join(f"#{kw}" for kw in ap.keywords[:8])
            blocks.append(self._indent_paragraph(f"🏷️ {kw_str}"))

        # Signal strength
        strength_emoji = {
            SignalStrength.HIGH: "🔴",
            SignalStrength.MEDIUM: "🟡",
            SignalStrength.LOW: "🟢",
        }.get(ap.signal_strength, "⚪")
        blocks.append(
            self._indent_paragraph(
                f"📊 시그널: {strength_emoji} {ap.signal_strength.value} "
                f"(추천점수: {ap.recommendation_score:.1f} | 분석점수: {ap.score:.1f})"
            )
        )

        # Top comments
        if ap.comment_summary:
            blocks.append(self._indent_paragraph(f"💬 {ap.comment_summary}"))
        elif ap.post.top_comments:
            comments_str = " | ".join(
                f'"{c[:60]}"' for c in ap.post.top_comments[:3]
            )
            blocks.append(self._indent_paragraph(f"💬 댓글: {comments_str}"))

        return blocks

    # ------------------------------------------------------------------
    # Primitive block helpers
    # ------------------------------------------------------------------

    def _heading2(self, text: str) -> dict:
        return {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": text}}]
            },
        }

    def _heading3(self, text: str) -> dict:
        return {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": text}}]
            },
        }

    def _paragraph(self, text: str, color: str = "default") -> dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "color": color,
            },
        }

    def _indent_paragraph(self, text: str) -> dict:
        """Paragraph used as a child indent (no actual nesting to stay simple)."""
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": f"    {text}"},
                        "annotations": {"color": "gray"},
                    }
                ]
            },
        }

    def _callout(self, text: str, icon: str = "💡", color: str = "yellow") -> dict:
        return {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "icon": {"type": "emoji", "emoji": icon},
                "color": color + "_background",
            },
        }

    def _table_of_contents(self) -> dict:
        return {
            "object": "block",
            "type": "table_of_contents",
            "table_of_contents": {"color": "default"},
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _ensure_navigation_blocks(self, page_id: str) -> None:
        """Ensure the daily page has a top-level TOC block near the header."""
        try:
            blocks = self._list_child_blocks(page_id, page_size=10)
        except Exception as e:
            logger.warning(f"Failed to inspect page structure for TOC setup: {e}")
            return

        toc_index = next(
            (idx for idx, block in enumerate(blocks) if block.get("type") == "table_of_contents"),
            None,
        )
        label_index = next(
            (idx for idx, block in enumerate(blocks) if self._is_toc_label(block)),
            None,
        )

        # Keep order near the top: header -> label -> TOC -> divider.
        if label_index is None:
            if toc_index is not None and toc_index > 0:
                after_id = blocks[toc_index - 1]["id"]
            elif blocks:
                after_id = blocks[0]["id"]
            else:
                after_id = None
            kwargs = {"block_id": page_id, "children": [self._paragraph("📚 목차", color="gray")]}
            if after_id:
                kwargs["after"] = after_id
            self.client.blocks.children.append(**kwargs)
            blocks = self._list_child_blocks(page_id, page_size=10)
            toc_index = next(
                (idx for idx, block in enumerate(blocks) if block.get("type") == "table_of_contents"),
                None,
            )
            label_index = next(
                (idx for idx, block in enumerate(blocks) if self._is_toc_label(block)),
                None,
            )

        if toc_index is None:
            if label_index is not None:
                after_id = blocks[label_index]["id"]
            elif blocks:
                after_id = blocks[0]["id"]
            else:
                after_id = None
            kwargs = {"block_id": page_id, "children": [self._table_of_contents()]}
            if after_id:
                kwargs["after"] = after_id
            self.client.blocks.children.append(**kwargs)

    def _find_page_by_title(self, title: str) -> Optional[str]:
        """Search for an existing page with the given title under parent."""
        try:
            results = self.client.search(
                query=title,
                filter={"value": "page", "property": "object"},
            )
            for page in results.get("results", []):
                page_title = ""
                title_prop = page.get("properties", {}).get("title", {})
                title_arr = title_prop.get("title", [])
                if title_arr:
                    page_title = title_arr[0].get("plain_text", "")
                if page_title == title:
                    return page["id"]
        except Exception as e:
            logger.warning(f"Page search failed: {e}")
        return None

    def _list_child_blocks(self, block_id: str, page_size: int = 100) -> list:
        """List direct child blocks with pagination."""
        results = []
        start_cursor = None

        while True:
            params = {"block_id": block_id, "page_size": page_size}
            if start_cursor:
                params["start_cursor"] = start_cursor
            response = self.client.blocks.children.list(**params)
            results.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")

        return results

    @staticmethod
    def _is_toc_label(block: dict) -> bool:
        """Check whether a block is the '목차' label near the top of the page."""
        block_type = block.get("type")
        if block_type not in {"paragraph", "callout"}:
            return False

        data = block.get(block_type, {})
        rich_text = data.get("rich_text", [])
        text = "".join(rt.get("plain_text", "") for rt in rich_text).strip()
        return text == "📚 목차"

    @staticmethod
    def _chunk(lst: list, size: int):
        """Yield successive chunks of given size from a list."""
        for i in range(0, len(lst), size):
            yield lst[i : i + size]
