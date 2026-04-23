"""Local text summary helpers used across analyzers."""

from __future__ import annotations

import re


WHITESPACE_RE = re.compile(r"\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
AUTHOR_PREFIX_RE = re.compile(r"^(?:\[답글\]\s*)?([^:]{1,12}):\s+")


def normalize_text(text: str) -> str:
    """Collapse repeated whitespace while preserving readable spacing."""
    return WHITESPACE_RE.sub(" ", (text or "")).strip()


def build_post_summary(title: str, content: str, max_sentences: int = 2, max_chars: int = 220) -> str:
    """Build a short extractive summary from the post body."""
    normalized_title = normalize_text(title)
    normalized_content = normalize_text(content)
    if not normalized_content:
        return normalized_title[:max_chars]

    sentences = [segment.strip(" -") for segment in SENTENCE_SPLIT_RE.split(normalized_content) if segment.strip()]
    selected: list[str] = []
    for sentence in sentences:
        if sentence in selected:
            continue
        if len(sentence) < 14 and len(sentences) > 1:
            continue
        candidate = " ".join(selected + [sentence]).strip()
        if len(candidate) > max_chars and selected:
            break
        selected.append(sentence)
        if len(selected) >= max_sentences:
            break

    summary = " ".join(selected).strip() or normalized_content[:max_chars]
    return summary[:max_chars]


def build_comment_summary(comments: list[str], max_items: int = 2, max_chars: int = 220) -> str:
    """Build a compact digest from representative comment snippets."""
    cleaned: list[str] = []
    for raw_comment in comments or []:
        normalized = normalize_text(raw_comment)
        if not normalized:
            continue
        normalized = AUTHOR_PREFIX_RE.sub("", normalized)
        normalized = re.sub(r"^\[답글\]\s*", "", normalized)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)

    if not cleaned:
        return ""

    picked = [comment[:100] for comment in cleaned[:max_items]]
    summary = " / ".join(picked)
    if len(cleaned) > max_items:
        suffix = " / 추가 반응 있음"
        if len(summary) + len(suffix) <= max_chars:
            summary += suffix
    return summary[:max_chars]
