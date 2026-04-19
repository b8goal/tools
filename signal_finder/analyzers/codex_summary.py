"""Executive summary generator powered by the local Codex CLI."""

import logging
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import List

from models.post import AnalyzedPost, Sentiment

logger = logging.getLogger(__name__)


class CodexSummaryGenerator:
    """Generate the daily executive summary with Codex CLI."""

    def __init__(self, model: str = "", codex_bin: str = "codex", timeout_seconds: int = 180):
        self.model = model.strip()
        self.codex_bin = codex_bin
        self.timeout_seconds = timeout_seconds
        self.repo_root = Path(__file__).resolve().parents[1]

    def generate_executive_summary(self, analyzed_posts: List[AnalyzedPost]) -> str:
        """Generate a 3-line executive summary."""
        if not analyzed_posts:
            return "수집된 유의미한 투자 인사이트가 없습니다."

        if not shutil.which(self.codex_bin):
            logger.warning("Codex CLI not found. Falling back to local summary.")
            return self._fallback_summary(analyzed_posts)

        prompt = self._build_prompt(analyzed_posts)
        cmd = [
            self.codex_bin,
            "exec",
            "--ephemeral",
            "--color",
            "never",
            "-s",
            "read-only",
            "-C",
            str(self.repo_root),
        ]
        if self.model:
            cmd.extend(["-m", self.model])

        with tempfile.TemporaryDirectory(prefix="codex-summary-") as tmp_dir:
            output_path = Path(tmp_dir) / "summary.txt"
            cmd.extend(["-o", str(output_path), "-"])

            try:
                result = subprocess.run(
                    cmd,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    cwd=self.repo_root,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                logger.error("Codex summary generation timed out after %s seconds.", self.timeout_seconds)
                return self._fallback_summary(analyzed_posts)
            except Exception as exc:
                logger.error("Failed to launch Codex summary generation: %s", exc)
                return self._fallback_summary(analyzed_posts)

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                logger.error("Codex summary generation failed: %s", stderr[-1000:] or result.returncode)
                return self._fallback_summary(analyzed_posts)

            try:
                summary = output_path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                logger.error("Failed to read Codex summary output: %s", exc)
                return self._fallback_summary(analyzed_posts)

        summary = self._normalize_summary(summary)
        if summary:
            return summary

        logger.warning("Codex summary returned empty output. Falling back to local summary.")
        return self._fallback_summary(analyzed_posts)

    def _build_prompt(self, analyzed_posts: List[AnalyzedPost]) -> str:
        post_lines = []
        for idx, post in enumerate(analyzed_posts[:25], 1):
            keywords = ", ".join(post.keywords[:6]) if post.keywords else "없음"
            tickers = ", ".join(post.tickers[:5]) if post.tickers else "없음"
            insight = post.investment_insight or "인사이트 없음"
            summary = post.summary or "요약 없음"
            post_lines.append(
                f"{idx}. [{post.post.source_name}] 제목={post.post.title} | "
                f"감성={post.sentiment.name} | 점수={post.score:.1f} | 키워드={keywords} | 종목={tickers}\n"
                f"   요약={summary}\n"
                f"   인사이트={insight}"
            )

        posts_blob = "\n".join(post_lines)
        return f"""
다음은 오늘 수집된 주식 커뮤니티 투자글 분석 결과다.
아래 데이터만 근거로 한국어 순수 텍스트 정확히 3줄로만 답해라.
마크다운, 코드블록, 서론, 결론, 군더더기 설명은 금지한다.
사용자를 직접 부르거나 호칭을 붙이지 말아라.
명령 실행이나 파일 변경은 하지 말고, 제공된 데이터만 사용해라.

응답 형식:
1. [시장 심리] ...
2. [주요 테마] ...
3. [투자 인사이트] ...

분석 데이터:
{posts_blob}
""".strip()

    def _fallback_summary(self, analyzed_posts: List[AnalyzedPost]) -> str:
        keywords = Counter()
        sentiments = Counter()
        sources = Counter()

        for post in analyzed_posts:
            keywords.update(post.keywords[:5])
            sentiments.update([post.sentiment])
            sources.update([post.post.source_name])

        top_keywords = [kw for kw, _ in keywords.most_common(4)] or ["관망", "종목별 대응"]
        top_sources = [src for src, _ in sources.most_common(2)] or ["커뮤니티"]
        top_post = max(analyzed_posts, key=lambda post: post.score)

        bullish = sentiments[Sentiment.BULLISH]
        bearish = sentiments[Sentiment.BEARISH]
        neutral = sentiments[Sentiment.NEUTRAL]

        if bullish > bearish:
            mood = "상승 기대가 우세하지만 종목별 옥석 가리기 분위기가 강합니다."
        elif bearish > bullish:
            mood = "경계 심리가 우세하고 방어적 관점의 의견이 상대적으로 많습니다."
        else:
            mood = "관망 심리와 선별 매수 심리가 혼재된 장세로 보입니다."

        if neutral > max(bullish, bearish):
            mood = "관망 심리가 강하지만 일부 테마에는 선별적 관심이 붙고 있습니다."

        insight = top_post.investment_insight or top_post.summary or top_post.post.title
        insight = re.sub(r"\s+", " ", insight).strip()

        return "\n".join(
            [
                f"1. [시장 심리] {mood}",
                f"2. [주요 테마] {'·'.join(top_keywords)} 중심으로 {', '.join(top_sources)}에서 대화가 집중됐습니다.",
                f"3. [투자 인사이트] 고득점 글 기준으로는 '{insight[:110]}' 흐름이 가장 강하게 포착됐습니다.",
            ]
        )

    @staticmethod
    def _normalize_summary(summary: str) -> str:
        lines = []
        for raw_line in summary.splitlines():
            line = raw_line.strip()
            if not line or line == "codex":
                continue
            if line.startswith("```") or line.startswith("tokens used"):
                continue
            line = re.sub(r"^형님[, ]+", "", line)
            lines.append(line)

        if not lines:
            return ""

        if len(lines) >= 3:
            return "\n".join(lines[:3])

        return "\n".join(lines)
