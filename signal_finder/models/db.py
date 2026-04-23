"""SQLite database module for persisting analyzed posts."""

import json
import logging
import sqlite3
from datetime import datetime
from typing import List

from models.post import AnalyzedPost

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for Signal Finder."""

    def __init__(self, db_path: str = "signal.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS analyzed_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_url TEXT UNIQUE,
                    source TEXT,
                    source_name TEXT,
                    title TEXT,
                    content TEXT,
                    upvotes INTEGER,
                    comment_count INTEGER,
                    views INTEGER,
                    scraped_at TIMESTAMP,
                    
                    summary TEXT,
                    comment_summary TEXT,
                    investment_insight TEXT,
                    tickers TEXT,
                    keywords TEXT,
                    sentiment TEXT,
                    signal_strength TEXT,
                    score REAL,
                    recommendation_score REAL DEFAULT 0,
                    specificity_score REAL DEFAULT 0,
                    actionability_score REAL DEFAULT 0,
                    noise_score REAL DEFAULT 0,
                    recommendation_passed INTEGER DEFAULT 0,
                    rejection_reasons TEXT DEFAULT '[]',
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Create an index on scraped_at for fast date range queries later
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraped_at ON analyzed_posts(scraped_at)"
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS recommended_posts (
                    post_url TEXT PRIMARY KEY,
                    source TEXT,
                    source_name TEXT,
                    title TEXT,
                    first_recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recommended_last_at
                ON recommended_posts(last_recommended_at)
                """
            )
            self._ensure_analyzed_post_columns(cursor)
            conn.commit()

    @staticmethod
    def _ensure_analyzed_post_columns(cursor) -> None:
        """Backfill columns when opening an existing database."""
        cursor.execute("PRAGMA table_info(analyzed_posts)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        required_columns = {
            "recommendation_score": "REAL DEFAULT 0",
            "specificity_score": "REAL DEFAULT 0",
            "actionability_score": "REAL DEFAULT 0",
            "noise_score": "REAL DEFAULT 0",
            "recommendation_passed": "INTEGER DEFAULT 0",
            "rejection_reasons": "TEXT DEFAULT '[]'",
            "comment_summary": "TEXT DEFAULT ''",
        }

        for column_name, ddl in required_columns.items():
            if column_name in existing_columns:
                continue
            cursor.execute(f"ALTER TABLE analyzed_posts ADD COLUMN {column_name} {ddl}")

    def get_recommended_urls(self, urls: List[str] | None = None) -> set[str]:
        """Return URLs that have already been uploaded to Notion."""
        query = "SELECT post_url FROM recommended_posts"
        rows = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if urls:
                    placeholders = ",".join("?" for _ in urls)
                    cursor.execute(
                        f"{query} WHERE post_url IN ({placeholders})",
                        urls,
                    )
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to load recommended post URLs: {e}")
            return set()

        return {row[0] for row in rows}

    def insert_posts(self, analyzed_posts: List[AnalyzedPost]):
        """Insert a list of AnalyzedPost into the database."""
        if not analyzed_posts:
            return

        query = """
            INSERT OR REPLACE INTO analyzed_posts (
                post_url, source, source_name, title, content, upvotes, 
                comment_count, views, scraped_at, summary, comment_summary, investment_insight, 
                tickers, keywords, sentiment, signal_strength, score,
                recommendation_score, specificity_score, actionability_score,
                noise_score, recommendation_passed, rejection_reasons
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        now = datetime.now()
        data = []
        for ap in analyzed_posts:
            data.append((
                ap.post.url,
                ap.post.source,
                ap.post.source_name,
                ap.post.title,
                ap.post.content or "",
                ap.post.upvotes,
                ap.post.comment_count,
                ap.post.views,
                ap.post.scraped_at or now,
                ap.summary,
                ap.comment_summary,
                ap.investment_insight,
                json.dumps(ap.tickers, ensure_ascii=False),
                json.dumps(ap.keywords, ensure_ascii=False),
                ap.sentiment.value,
                ap.signal_strength.value,
                ap.score,
                ap.recommendation_score,
                ap.specificity_score,
                ap.actionability_score,
                ap.noise_score,
                int(ap.recommendation_passed),
                json.dumps(ap.rejection_reasons, ensure_ascii=False),
            ))

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(query, data)
                conn.commit()
            logger.info(f"💾 Saved {len(data)} posts to local database ({self.db_path}).")
        except Exception as e:
            logger.error(f"Failed to save posts to database: {e}")

    def mark_posts_recommended(
        self,
        analyzed_posts: List[AnalyzedPost],
        recommended_at: datetime | None = None,
    ) -> None:
        """Persist URLs that have already been recommended in Notion."""
        if not analyzed_posts:
            return

        timestamp = (recommended_at or datetime.now()).isoformat(sep=" ", timespec="seconds")
        data = [
            (
                ap.post.url,
                ap.post.source,
                ap.post.source_name,
                ap.post.title,
                timestamp,
                timestamp,
            )
            for ap in analyzed_posts
        ]

        query = """
            INSERT INTO recommended_posts (
                post_url, source, source_name, title, first_recommended_at, last_recommended_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(post_url) DO UPDATE SET
                source = excluded.source,
                source_name = excluded.source_name,
                title = excluded.title,
                last_recommended_at = excluded.last_recommended_at
        """

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(query, data)
                conn.commit()
            logger.info(f"📝 Marked {len(data)} posts as already recommended.")
        except Exception as e:
            logger.error(f"Failed to mark recommended posts: {e}")
