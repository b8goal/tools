"""Recommendation gate and ranking logic for Signal Finder."""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Iterable, List, Sequence

from models.post import AnalyzedPost, Sentiment

logger = logging.getLogger(__name__)


STRONG_MACRO_KEYWORDS = {
    "금리",
    "금리인하",
    "금리인상",
    "cpi",
    "pce",
    "fomc",
    "실적",
    "가이던스",
    "관세",
    "제재",
    "원유재고",
    "환율",
    "공급망",
    "휴전",
    "ceasefire",
    "armistice",
    "원자재",
    "유가",
    "원유",
    "opec",
    "고용",
    "물가",
    "fed",
    "연준",
    "매출",
    "영업이익",
    "eps",
    "capex",
    "lta",
    "수주",
}

WEAK_DISCUSSION_KEYWORDS = {
    "주식",
    "증시",
    "국장",
    "미장",
    "숏",
    "롱",
    "투자심리",
    "시장심리",
    "시장전망",
    "시장예측",
    "하락장",
    "강세장",
    "호재",
    "악재",
    "멘탈",
}

ACTION_TERMS = {
    "매수",
    "매도",
    "비중",
    "분할매수",
    "분할매도",
    "익절",
    "손절",
    "대응",
    "관망",
    "포지션",
    "entry",
    "exit",
    "buy",
    "sell",
    "trim",
    "hedge",
    "watch",
}

MEME_PATTERNS = (
    "ㅋㅋ",
    "ㅎㅎ",
    "jpg",
    "gif",
    "개추",
    "추천좀",
    "추천 좀",
    "짤",
    "표정",
    "실시간",
    "로켓단",
    "숏충",
    "롱숭",
    "롱충",
    "숏신사",
    "개미핥기",
)

PROFANITY_PATTERNS = (
    "씨발",
    "병신",
    "ㅅㅂ",
    "좆",
    "개새",
)

REACTION_TITLE_RE = re.compile(r"(\?{2,}|!{2,}|\.{3,}|ㄷ{3,}|ㅋ{3,}|ㅎ{3,})")
NUMERIC_EVIDENCE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(%|퍼센트|bp|bps|달러|원|배|억|조|만|천|주|건|명|분기|년|개월|일)"
)

SOURCE_TRUST_SCORES = {
    "merblog": 10.0,
    "clien": 9.5,
    "ppomppu": 8.5,
    "fmkorea": 7.5,
    "koreapas": 7.0,
    "dcinside": 5.0,
}

DC_PRIORITY_HEADINGS = {"💡정보", "📰뉴스", "🌟베스트", "🔥HIT", "📚도서관", "✏매매공시"}


class RecommendationRanker:
    """Apply quality gates and final recommendation ranking."""

    MAX_RECOMMENDATIONS = 6
    MAX_PER_SOURCE = 2

    RECOMMENDATION_CUTOFF = 70.0
    MAX_NOISE_SCORE = 2.0
    MIN_SPECIFICITY_SCORE = 3.0

    MIN_EFFECTIVE_TEXT_LEN = 40
    MACRO_EXCEPTION_MIN_TEXT_LEN = 80

    def select(self, analyzed_posts: Sequence[AnalyzedPost]) -> tuple[list[AnalyzedPost], list[AnalyzedPost]]:
        """Return (selected, rejected) after scoring and source-balanced ranking."""
        if not analyzed_posts:
            return [], []

        source_counts = Counter(ap.post.source for ap in analyzed_posts)
        engagement_context = self._build_engagement_context(analyzed_posts)
        max_source_count = max(source_counts.values()) if source_counts else 1

        for post in analyzed_posts:
            self._score_post(post, source_counts, engagement_context, max_source_count)

        eligible = [post for post in analyzed_posts if self._passes_quality_gate(post)]
        eligible.sort(key=self._sort_key, reverse=True)

        selected: list[AnalyzedPost] = []
        selected_urls: set[str] = set()
        per_source_selected: Counter = Counter()

        # First pass: keep the top post per source.
        for post in eligible:
            if len(selected) >= self.MAX_RECOMMENDATIONS:
                break
            source = post.post.source
            if per_source_selected[source] > 0:
                continue
            self._mark_selected(post)
            selected.append(post)
            selected_urls.add(post.post.url)
            per_source_selected[source] += 1

        # Second pass: fill remaining slots by score while enforcing per-source caps.
        for post in eligible:
            if len(selected) >= self.MAX_RECOMMENDATIONS:
                break
            if post.post.url in selected_urls:
                continue
            source = post.post.source
            if per_source_selected[source] >= self.MAX_PER_SOURCE:
                self._mark_rejected(post, "selection_quota")
                continue
            self._mark_selected(post)
            selected.append(post)
            selected_urls.add(post.post.url)
            per_source_selected[source] += 1

        rejected: list[AnalyzedPost] = []
        for post in analyzed_posts:
            if post.post.url in selected_urls:
                continue
            if self._passes_quality_gate(post):
                self._mark_rejected(post, "selection_quota")
            rejected.append(post)

        selected.sort(key=self._sort_key, reverse=True)
        rejected.sort(key=self._sort_key, reverse=True)
        return selected, rejected

    @staticmethod
    def collect_rejection_reason_counts(posts: Iterable[AnalyzedPost]) -> Counter:
        """Aggregate rejection reasons for logging."""
        counter: Counter = Counter()
        for post in posts:
            counter.update(post.rejection_reasons)
        return counter

    def _score_post(
        self,
        post: AnalyzedPost,
        source_counts: Counter,
        engagement_context: dict[str, list[float]],
        max_source_count: int,
    ) -> None:
        combined_text = self._combined_text(post)
        detail_text = self._detail_text(post)
        normalized_keywords = [self._normalize_token(kw) for kw in post.keywords]
        evidence_types = [self._normalize_token(item) for item in post.evidence_types]

        strong_macro_hits = self._extract_strong_macro_hits(combined_text, normalized_keywords)
        numeric_evidence = self._has_numeric_evidence(combined_text)
        action_terms = self._has_action_terms(combined_text)
        meme_markers = self._count_matches(combined_text, MEME_PATTERNS)
        profanity_markers = self._count_matches(combined_text, PROFANITY_PATTERNS)
        reaction_title = bool(REACTION_TITLE_RE.search(post.post.title))
        effective_text_len = self._effective_text_length(detail_text)
        weak_only = self._is_weak_only_post(post, strong_macro_hits, numeric_evidence)

        derived_specificity = self._derive_specificity_score(
            post=post,
            strong_macro_hits=strong_macro_hits,
            numeric_evidence=numeric_evidence,
            effective_text_len=effective_text_len,
            weak_only=weak_only,
        )
        derived_actionability = self._derive_actionability_score(
            post=post,
            strong_macro_hits=strong_macro_hits,
            numeric_evidence=numeric_evidence,
            action_terms=action_terms,
            effective_text_len=effective_text_len,
        )
        derived_noise = self._derive_noise_score(
            post=post,
            meme_markers=meme_markers,
            profanity_markers=profanity_markers,
            reaction_title=reaction_title,
            effective_text_len=effective_text_len,
            weak_only=weak_only,
        )

        post.specificity_score = max(float(post.specificity_score or 0.0), derived_specificity)
        post.actionability_score = max(float(post.actionability_score or 0.0), derived_actionability)
        post.noise_score = max(float(post.noise_score or 0.0), derived_noise)

        rejection_reasons: list[str] = list(post.rejection_reasons or [])
        has_specific_asset = bool(post.tickers)
        has_strong_macro = bool(strong_macro_hits)
        macro_exception = (
            not has_specific_asset
            and has_strong_macro
            and effective_text_len >= self.MACRO_EXCEPTION_MIN_TEXT_LEN
            and post.specificity_score >= 4.0
        )

        if effective_text_len < self.MIN_EFFECTIVE_TEXT_LEN:
            rejection_reasons.append("short_text")
        if weak_only:
            rejection_reasons.append("weak_keyword_only")
        if not has_specific_asset and not has_strong_macro:
            rejection_reasons.append("no_ticker_or_strong_macro")
        if (meme_markers or profanity_markers or reaction_title) and post.specificity_score < 4.0:
            rejection_reasons.append("meme_title_low_specificity")

        if macro_exception:
            rejection_reasons = [reason for reason in rejection_reasons if reason != "no_ticker_or_strong_macro"]

        evidence_richness = self._compute_evidence_richness(
            post=post,
            strong_macro_hits=strong_macro_hits,
            numeric_evidence=numeric_evidence,
            evidence_types=evidence_types,
            effective_text_len=effective_text_len,
        )
        engagement_score = self._compute_engagement_score(post, engagement_context)
        source_trust = SOURCE_TRUST_SCORES.get(post.post.source, 6.0)
        diversity_bonus = self._compute_diversity_bonus(post.post.source, source_counts, max_source_count)
        dc_priority_bonus = 2.0 if post.post.source == "dcinside" and post.post.category in DC_PRIORITY_HEADINGS else 0.0
        macro_exception_bonus = 8.0 if macro_exception else 0.0
        noise_penalty = min(20.0, post.noise_score * 4.0)

        recommendation_score = (
            (post.specificity_score / 5.0) * 25.0
            + (post.actionability_score / 5.0) * 15.0
            + evidence_richness
            + engagement_score
            + source_trust
            + diversity_bonus
            + dc_priority_bonus
            + macro_exception_bonus
            - noise_penalty
        )

        if rejection_reasons:
            recommendation_score -= 12.0

        post.recommendation_score = round(max(0.0, min(100.0, recommendation_score)), 2)
        post.recommendation_passed = False
        post.rejection_reasons = self._dedupe_preserve_order(rejection_reasons)

    def _passes_quality_gate(self, post: AnalyzedPost) -> bool:
        if any(
            reason in post.rejection_reasons
            for reason in ("short_text", "weak_keyword_only", "no_ticker_or_strong_macro", "meme_title_low_specificity")
        ):
            return False
        if post.recommendation_score < self.RECOMMENDATION_CUTOFF:
            return False
        if post.noise_score > self.MAX_NOISE_SCORE:
            return False
        if post.specificity_score < self.MIN_SPECIFICITY_SCORE:
            return False
        return True

    def _mark_selected(self, post: AnalyzedPost) -> None:
        post.recommendation_passed = True
        post.rejection_reasons = []

    def _mark_rejected(self, post: AnalyzedPost, reason: str) -> None:
        post.recommendation_passed = False
        reasons = list(post.rejection_reasons)
        reasons.append(reason)
        post.rejection_reasons = self._dedupe_preserve_order(reasons)

    @staticmethod
    def _sort_key(post: AnalyzedPost) -> tuple[float, float, float]:
        return (post.recommendation_score, post.specificity_score, post.score)

    @staticmethod
    def _combined_text(post: AnalyzedPost) -> str:
        parts = [post.post.title, post.post.content or "", *(post.post.top_comments or [])]
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def _detail_text(post: AnalyzedPost) -> str:
        parts = [post.post.content or "", *(post.post.top_comments or [])]
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def _normalize_token(value: str) -> str:
        return re.sub(r"\s+", "", str(value or "").lower())

    @staticmethod
    def _effective_text_length(text: str) -> int:
        cleaned = re.sub(r"https?://\S+", " ", text)
        cleaned = re.sub(r"[^0-9a-zA-Z가-힣]+", "", cleaned)
        return len(cleaned)

    @staticmethod
    def _count_matches(text: str, patterns: Sequence[str]) -> int:
        lowered = text.lower()
        return sum(1 for pattern in patterns if pattern in lowered)

    def _extract_strong_macro_hits(self, combined_text: str, normalized_keywords: Sequence[str]) -> set[str]:
        lowered = combined_text.lower()
        hits = {term for term in STRONG_MACRO_KEYWORDS if term in lowered}
        hits.update(term for term in STRONG_MACRO_KEYWORDS if term in normalized_keywords)
        return hits

    @staticmethod
    def _has_numeric_evidence(text: str) -> bool:
        return bool(NUMERIC_EVIDENCE_RE.search(text))

    def _has_action_terms(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in ACTION_TERMS)

    def _is_weak_only_post(
        self,
        post: AnalyzedPost,
        strong_macro_hits: set[str],
        numeric_evidence: bool,
    ) -> bool:
        if post.tickers or strong_macro_hits or numeric_evidence:
            return False
        normalized_keywords = [self._normalize_token(kw) for kw in post.keywords]
        meaningful_keywords = [kw for kw in normalized_keywords if kw]
        if not meaningful_keywords:
            return False
        return all(kw in WEAK_DISCUSSION_KEYWORDS for kw in meaningful_keywords)

    def _derive_specificity_score(
        self,
        post: AnalyzedPost,
        strong_macro_hits: set[str],
        numeric_evidence: bool,
        effective_text_len: int,
        weak_only: bool,
    ) -> float:
        raw = 0.0
        if post.tickers:
            raw += 2.0
        if strong_macro_hits:
            raw += 2.0
        if numeric_evidence:
            raw += 1.0
        if effective_text_len >= 120:
            raw += 1.0
        if len(post.keywords) >= 3 and not weak_only:
            raw += 1.0
        return min(5.0, raw)

    def _derive_actionability_score(
        self,
        post: AnalyzedPost,
        strong_macro_hits: set[str],
        numeric_evidence: bool,
        action_terms: bool,
        effective_text_len: int,
    ) -> float:
        raw = 0.0
        if post.tickers:
            raw += 2.0
        if strong_macro_hits:
            raw += 1.0
        if action_terms or post.sentiment != Sentiment.NEUTRAL:
            raw += 1.0
        if numeric_evidence:
            raw += 1.0
        if effective_text_len >= 150:
            raw += 1.0
        return min(5.0, raw)

    @staticmethod
    def _derive_noise_score(
        post: AnalyzedPost,
        meme_markers: int,
        profanity_markers: int,
        reaction_title: bool,
        effective_text_len: int,
        weak_only: bool,
    ) -> float:
        raw = 0.0
        raw += min(2.0, float(meme_markers))
        raw += min(2.0, float(profanity_markers))
        if reaction_title:
            raw += 1.0
        if effective_text_len < 80:
            raw += 1.0
        if weak_only:
            raw += 1.0
        if len(post.post.title.strip()) <= 10:
            raw += 0.5
        return min(5.0, raw)

    @staticmethod
    def _compute_evidence_richness(
        post: AnalyzedPost,
        strong_macro_hits: set[str],
        numeric_evidence: bool,
        evidence_types: Sequence[str],
        effective_text_len: int,
    ) -> float:
        score = 0.0
        if post.tickers:
            score += 10.0
        if strong_macro_hits:
            score += min(8.0, len(strong_macro_hits) * 4.0)
        if numeric_evidence:
            score += 5.0
        if effective_text_len >= 150:
            score += 3.0
        if len(post.keywords) >= 3:
            score += 2.0
        if evidence_types:
            score += min(5.0, len(set(evidence_types)) * 2.0)
        return min(25.0, score)

    @staticmethod
    def _build_engagement_context(analyzed_posts: Sequence[AnalyzedPost]) -> dict[str, list[float]]:
        context: dict[str, list[float]] = {}
        for post in analyzed_posts:
            context.setdefault(post.post.source, []).append(
                post.post.upvotes + (post.post.comment_count * 0.6) + min(post.post.views / 500.0, 10.0)
            )
        for values in context.values():
            values.sort()
        return context

    @staticmethod
    def _compute_engagement_score(post: AnalyzedPost, context: dict[str, list[float]]) -> float:
        values = context.get(post.post.source) or []
        if not values:
            return 7.5

        raw_value = post.post.upvotes + (post.post.comment_count * 0.6) + min(post.post.views / 500.0, 10.0)
        if len(values) == 1:
            percentile = 0.5
        else:
            below_or_equal = sum(1 for value in values if value <= raw_value)
            percentile = (below_or_equal - 1) / max(1, len(values) - 1)
        percentile = max(0.0, min(1.0, percentile))
        return round(percentile * 15.0, 2)

    @staticmethod
    def _compute_diversity_bonus(source: str, source_counts: Counter, max_source_count: int) -> float:
        count = source_counts.get(source, 1)
        if max_source_count <= 1:
            return 10.0
        ratio = (count - 1) / max(1, max_source_count - 1)
        return round((1.0 - ratio) * 10.0, 2)

    @staticmethod
    def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
        seen = set()
        ordered = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered
