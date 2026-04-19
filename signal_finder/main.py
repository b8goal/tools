"""Signal Finder - Entry point.

Usage:
    python main.py            # Run scheduler (every SCRAPE_INTERVAL_MINUTES)
    python main.py --once     # Run once immediately and exit
    python main.py --test     # Dry-run: scrape only, skip Notion upload
"""

import argparse
import logging
import sys
import time
from datetime import datetime

import json
import os
import schedule

from config import Config
from scrapers import FMKoreaScraper, KoreapasScraper, DcinsideScraper, PpomppuScraper
from collections import Counter
import requests
from notion_writer import NotionManager
from models.db import DatabaseManager

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("signal_finder.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("signal_finder")


# ---------------------------------------------------------------------------
# Scraper factory
# ---------------------------------------------------------------------------

SCRAPER_CLASSES = {
    "fmkorea":  FMKoreaScraper,
    "koreapas": KoreapasScraper,
    "dcinside": DcinsideScraper,
    "ppomppu":  PpomppuScraper,
}

SEEN_POSTS_FILE = "seen_posts.json"

def load_seen_posts() -> set:
    if os.path.exists(SEEN_POSTS_FILE):
        try:
            with open(SEEN_POSTS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen_posts(seen_urls: set) -> None:
    # 최대 5000개만 유지해서 파일이 무한정 커지는 것 방지
    urls = list(seen_urls)[-5000:]
    try:
        with open(SEEN_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(urls, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save seen posts: {e}")


def send_alert(config: Config, message: str) -> None:
    """Send an alert to a Discord/Slack webhook if configured."""
    if not config.alert_webhook_url:
        return
    try:
        payload = {"content": f"⚠️ **Signal Finder Alert**\n{message}"}
        requests.post(config.alert_webhook_url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")

def build_scrapers(config: Config) -> list:
    """Instantiate all enabled scrapers from config."""
    scrapers = []
    for key, cls in SCRAPER_CLASSES.items():
        scraper_cfg = config.scrapers.get(key)
        if scraper_cfg and scraper_cfg.enabled:
            scrapers.append(cls(config, scraper_cfg))
            logger.info(f"  ✅ {scraper_cfg.name} enabled (min upvotes: {scraper_cfg.min_upvotes})")
        else:
            logger.info(f"  ⏭️  {key} disabled")
    return scrapers


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_pipeline(config: Config, dry_run: bool = False) -> None:
    """Full pipeline: scrape → analyze → upload to Notion."""
    now = datetime.now()
    logger.info(f"{'='*60}")
    logger.info(f"🚀 Signal Finder pipeline started at {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}")

    # ── 1. Build scrapers ──
    logger.info("📋 Loading scrapers...")
    scrapers = build_scrapers(config)
    if not scrapers:
        logger.warning("No scrapers enabled. Check config.")
        return

    # ── 2. Scrape all sites ──
    all_scraped = []
    for scraper in scrapers:
        try:
            posts = scraper.scrape()
            logger.info(
                f"  [{scraper.scraper_config.name}] {len(posts)} posts scraped"
            )
            all_scraped.extend(posts)
        except Exception as e:
            logger.error(
                f"  [{scraper.scraper_config.name}] Pipeline error: {e}",
                exc_info=True,
            )

    logger.info(f"📦 Total scraped: {len(all_scraped)} posts across {len(scrapers)} sites")

    if not all_scraped:
        logger.warning("No posts scraped. Aborting pipeline.")
        send_alert(config, "수집된 게시글이 0건입니다. (스크래퍼 차단 의심)")
        return

    # ── 3. Deduplicate (중복 방지) ──
    db = DatabaseManager()
    unique_scraped = []
    scraped_urls = set()
    duplicate_scraped_count = 0
    for post in all_scraped:
        if post.url in scraped_urls:
            duplicate_scraped_count += 1
            continue
        scraped_urls.add(post.url)
        unique_scraped.append(post)

    if duplicate_scraped_count:
        logger.info(f"  🧹 Skipped {duplicate_scraped_count} duplicate rows within the same scrape batch.")

    seen_urls = load_seen_posts()
    recommended_urls = db.get_recommended_urls([post.url for post in unique_scraped])
    new_posts = []
    skipped_seen = 0
    skipped_recommended = 0
    for post in unique_scraped:
        if post.url in recommended_urls:
            skipped_recommended += 1
            continue
        if post.url in seen_urls:
            skipped_seen += 1
            continue
        new_posts.append(post)
            
    if not new_posts:
        logger.info(
            "  💤 No new posts to analyze. "
            f"Already seen: {skipped_seen}, already recommended: {skipped_recommended}."
        )
        return

    logger.info(
        f"  ✨ Found {len(new_posts)} new posts. "
        f"Bypassing seen={skipped_seen}, recommended={skipped_recommended}."
    )

    # ── 4. Analyze ──
    logger.info("🔍 Running signal analysis...")
    if config.gemini_api_key:
        from analyzers.llm_extractor import GeminiExtractor
        logger.info("🤖 Using Gemini API for analysis")
        extractor = GeminiExtractor(api_key=config.gemini_api_key)
    else:
        from analyzers.signal_extractor import SignalExtractor
        logger.info("🧠 Using Local Rule-based analysis")
        extractor = SignalExtractor()

    analyzed_posts = extractor.batch_analyze(new_posts)
    
    # Extract hot keywords from the analyzed LLM/Rule outputs
    kw_counter = Counter()
    for ap in analyzed_posts:
        for kw in ap.keywords:
            kw_counter[kw] += 1
    hot_keywords = kw_counter.most_common(10)

    logger.info(f"  📈 Hot keywords: {[kw for kw, _ in hot_keywords[:5]]}")
    logger.info(f"  ✅ Analyzed {len(analyzed_posts)} posts")

    if not analyzed_posts:
        logger.info("  💤 No investment-related posts after analysis. Skipping summary and Notion upload.")
        return

    # ── 5. Save to Database ──
    db.insert_posts(analyzed_posts)

    executive_summary = ""
    if analyzed_posts:
        from analyzers.codex_summary import CodexSummaryGenerator

        logger.info("🧠 Generating executive summary with Codex...")
        summary_generator = CodexSummaryGenerator(model=config.codex_summary_model)
        executive_summary = summary_generator.generate_executive_summary(analyzed_posts)
        logger.info("  📝 Summary generated.")

    # ── 6. Print summary ──
    _print_summary(analyzed_posts, hot_keywords, executive_summary)

    # ── 7. Upload to Notion ──
    if dry_run:
        logger.info("🔕 Dry-run mode: skipping Notion upload")
        return

    if not config.notion_token or not config.notion_parent_page_id:
        logger.warning(
            "⚠️  NOTION_TOKEN or NOTION_PARENT_PAGE_ID not set. "
            "Skipping Notion upload.\n"
            "   Set them in .env file to enable Notion integration."
        )
        return

    logger.info("📝 Uploading to Notion...")
    try:
        notion = NotionManager(config)
        page_id = notion.upsert_daily_page(now)
        notion.append_collection_section(
            page_id=page_id,
            analyzed_posts=analyzed_posts,
            hot_keywords=hot_keywords,
            collected_at=now,
            executive_summary=executive_summary,
        )
        db.mark_posts_recommended(analyzed_posts, recommended_at=now)
        for post in new_posts:
            seen_urls.add(post.url)
        save_seen_posts(seen_urls)
        logger.info(f"  ✅ Notion page updated (id: {page_id})")
    except Exception as e:
        logger.error(f"  ❌ Notion upload failed: {e}", exc_info=True)
        send_alert(config, f"Notion 업로드 실패: {e}")

    logger.info(f"{'='*60}")
    logger.info("✅ Pipeline complete")
    logger.info(f"{'='*60}")


def _print_summary(analyzed_posts, hot_keywords, executive_summary="") -> None:
    """Print a concise console summary of the run."""
    print("\n" + "═" * 60)
    print("📊 Signal Finder - 수집 결과 요약")
    print("═" * 60)

    if executive_summary:
        print("🤖 [AI 종합 트렌드 요약]")
        print(executive_summary)
        print("-" * 60)

    if hot_keywords:
        kws = "  ".join(f"#{kw}({cnt})" for kw, cnt in hot_keywords[:8])
        print(f"🔥 핫 키워드: {kws}")

    print(f"\n📋 수집 게시글: {len(analyzed_posts)}건")
    print()

    # Top 5 posts by score
    for i, ap in enumerate(analyzed_posts[:5], 1):
        print(f"  {i}. [{ap.post.source_name}] {ap.post.title[:45]}")
        print(f"     ⬆️ {ap.post.upvotes}  💬 {ap.post.comment_count}  📊 점수: {ap.score:.1f}")
        if ap.keywords:
            print(f"     🏷️ {', '.join(ap.keywords[:5])}")
        print()

    print("═" * 60 + "\n")


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def start_scheduler(config: Config, dry_run: bool = False) -> None:
    """Run the pipeline on a fixed interval using the schedule library."""
    interval = config.scrape_interval_minutes
    logger.info(
        f"⏰ Scheduler started: pipeline runs every {interval} minutes"
    )

    # Run immediately on startup
    run_pipeline(config, dry_run=dry_run)

    schedule.every(interval).minutes.do(run_pipeline, config=config, dry_run=dry_run)

    while True:
        schedule.run_pending()
        time.sleep(30)  # check every 30 seconds


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Signal Finder - 주식 커뮤니티 인사이트 수집기"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once and exit (no scheduler)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Dry-run: scrape and analyze but skip Notion upload",
    )
    args = parser.parse_args()

    logger.info("🔧 Loading config from environment...")
    config = Config.from_env()

    if args.once or args.test:
        run_pipeline(config, dry_run=args.test)
    else:
        start_scheduler(config, dry_run=False)


if __name__ == "__main__":
    main()
