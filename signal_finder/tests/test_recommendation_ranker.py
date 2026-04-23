"""Unit tests for the recommendation quality gate."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.recommendation_ranker import RecommendationRanker
from models.post import AnalyzedPost, ScrapedPost, Sentiment, SignalStrength


SOURCE_NAMES = {
    "dcinside": "DC 미주갤",
    "fmkorea": "FM Korea 주식",
    "ppomppu": "뽐뿌 증권포럼",
    "clien": "클리앙 주식한당",
}


def build_analyzed_post(
    *,
    source: str,
    idx: int,
    title: str,
    content: str,
    upvotes: int,
    comment_count: int,
    views: int = 0,
    tickers: list[str] | None = None,
    keywords: list[str] | None = None,
    sentiment: Sentiment = Sentiment.BULLISH,
    specificity_score: float = 0.0,
    actionability_score: float = 0.0,
    noise_score: float = 0.0,
    rejection_reasons: list[str] | None = None,
    category: str = "",
) -> AnalyzedPost:
    post = ScrapedPost(
        title=title,
        url=f"https://example.com/{source}/{idx}",
        source=source,
        source_name=SOURCE_NAMES[source],
        content=content,
        upvotes=upvotes,
        comment_count=comment_count,
        views=views,
        top_comments=["근거 숫자와 맥락이 있어야 투자 참고가 됩니다."],
        category=category,
    )
    return AnalyzedPost(
        post=post,
        summary=title,
        investment_insight=content[:120],
        tickers=tickers or [],
        keywords=keywords or [],
        sentiment=sentiment,
        signal_strength=SignalStrength.HIGH,
        score=float(upvotes + comment_count),
        specificity_score=specificity_score,
        actionability_score=actionability_score,
        noise_score=noise_score,
        rejection_reasons=rejection_reasons or [],
    )


class RecommendationRankerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ranker = RecommendationRanker()

    def test_rejects_meme_like_high_engagement_post(self) -> None:
        meme_post = build_analyzed_post(
            source="dcinside",
            idx=1,
            title="숏충이들 보면 로켓단같음 ㅋㅋ jpg",
            content="ㅋㅋ",
            upvotes=420,
            comment_count=85,
            keywords=["숏", "증시"],
            views=12000,
        )

        selected, rejected = self.ranker.select([meme_post])

        self.assertEqual(selected, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn("short_text", meme_post.rejection_reasons)
        self.assertIn("meme_title_low_specificity", meme_post.rejection_reasons)
        self.assertFalse(meme_post.recommendation_passed)

    def test_keeps_specific_company_analysis_post(self) -> None:
        quality_post = build_analyzed_post(
            source="fmkorea",
            idx=2,
            title="오늘자 씨티의 메모리 업체들의 LTA 예상",
            content=(
                "씨티는 SK하이닉스와 삼성전자의 LTA 물량 전망을 상향했고, "
                "2026년 CAPEX는 12% 증가, ASP는 8% 상승할 수 있다고 정리했다. "
                "공급 축소와 HBM 수요가 이어지면 실적 추정치도 상향될 가능성이 높다."
            ),
            upvotes=50,
            comment_count=12,
            views=4000,
            tickers=["SK하이닉스", "삼성전자"],
            keywords=["실적", "CAPEX", "메모리", "LTA"],
            specificity_score=5,
            actionability_score=4,
            noise_score=1,
        )

        selected, rejected = self.ranker.select([quality_post])

        self.assertEqual(len(selected), 1)
        self.assertEqual(rejected, [])
        self.assertTrue(quality_post.recommendation_passed)
        self.assertGreaterEqual(quality_post.recommendation_score, 70.0)

    def test_allows_macro_exception_without_ticker(self) -> None:
        macro_post = build_analyzed_post(
            source="fmkorea",
            idx=3,
            title="케빈 워시 연준 의장 후보자 발언 정리",
            content=(
                "케빈 워시는 FOMC가 데이터 중심으로 움직여야 한다고 말했고, "
                "CPI 둔화와 고용 둔화가 확인되면 25bp 인하 여지가 생긴다고 설명했다. "
                "시장에서는 금리, 달러, 장기채 방향성까지 함께 체크해야 한다는 의견이 나왔다."
            ),
            upvotes=49,
            comment_count=8,
            views=3000,
            keywords=["연준", "금리", "FOMC", "CPI"],
            sentiment=Sentiment.NEUTRAL,
            specificity_score=4,
            actionability_score=3,
            noise_score=1,
        )

        selected, _ = self.ranker.select([macro_post])

        self.assertEqual(len(selected), 1)
        self.assertTrue(macro_post.recommendation_passed)
        self.assertNotIn("no_ticker_or_strong_macro", macro_post.rejection_reasons)

    def test_enforces_source_caps_and_diversity_selection(self) -> None:
        candidates = []
        idx = 10
        for source in ("dcinside", "fmkorea", "ppomppu", "clien"):
            for rank in range(3):
                idx += 1
                candidates.append(
                    build_analyzed_post(
                        source=source,
                        idx=idx,
                        title=f"{source} 종목 분석 {rank}",
                        content=(
                            "엔비디아와 삼성전자 공급망 변화, 실적 가이던스, CAPEX, "
                            "25% 성장률, 밸류에이션 재평가 가능성을 정리한 분석 글이다."
                        ),
                        upvotes=120 - (rank * 5),
                        comment_count=25 - rank,
                        views=6000,
                        tickers=["NVDA", "삼성전자"],
                        keywords=["실적", "가이던스", "공급망", "CAPEX"],
                        specificity_score=5,
                        actionability_score=4,
                        noise_score=1,
                        category="📰뉴스" if source == "dcinside" else "",
                    )
                )

        selected, rejected = self.ranker.select(candidates)

        self.assertEqual(len(selected), 6)
        counts = {}
        for post in selected:
            counts[post.post.source] = counts.get(post.post.source, 0) + 1
        self.assertTrue(all(count <= 2 for count in counts.values()))
        self.assertTrue(all(source in counts for source in ("dcinside", "fmkorea", "ppomppu", "clien")))
        self.assertTrue(any("selection_quota" in post.rejection_reasons for post in rejected))

    def test_same_gate_applies_with_and_without_llm_enrichment(self) -> None:
        raw_post = build_analyzed_post(
            source="dcinside",
            idx=50,
            title="실시간 숏충이 표정... ㅋㅋ",
            content="ㅋㅋ",
            upvotes=180,
            comment_count=52,
            keywords=["숏", "주식"],
            views=5000,
        )
        llm_enriched_post = build_analyzed_post(
            source="dcinside",
            idx=51,
            title="실시간 숏충이 표정... ㅋㅋ",
            content="ㅋㅋ",
            upvotes=175,
            comment_count=50,
            keywords=["숏", "주식"],
            views=4800,
            specificity_score=5,
            actionability_score=5,
            noise_score=0,
        )

        selected, rejected = self.ranker.select([raw_post, llm_enriched_post])

        self.assertEqual(selected, [])
        self.assertEqual(len(rejected), 2)
        self.assertFalse(raw_post.recommendation_passed)
        self.assertFalse(llm_enriched_post.recommendation_passed)
        self.assertIn("short_text", raw_post.rejection_reasons)
        self.assertIn("short_text", llm_enriched_post.rejection_reasons)


if __name__ == "__main__":
    unittest.main()
