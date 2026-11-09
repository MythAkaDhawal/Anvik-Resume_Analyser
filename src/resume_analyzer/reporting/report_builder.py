"""Report builder for creating complete AnalysisReport instances.

Assembles candidate data, job requirements, matching results, deterministic score,
AI insights, human-review notice, provenance, and diagnostic flags.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from resume_analyzer.config.settings import Settings
from resume_analyzer.models.candidate import Candidate
from resume_analyzer.models.enums import FeatureStatus, MatchType
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import (
    AIInsights,
    AnalysisReport,
    MatchResult,
    ReportFlag,
    ScoreResult,
    SkillMatch,
)
from resume_analyzer.reporting.provenance import HUMAN_REVIEW_NOTICE


class ReportBuilder:
    """Builder for constructing standardized immutable AnalysisReport objects."""

    REPORT_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z_[0-9a-f]{8}_[0-9a-f]{4}$")

    @classmethod
    def generate_report_id(
        cls,
        candidate_id: str,
        timestamp: datetime | None = None,
    ) -> str:
        """Generate a compliant report ID string matching ^\\d{8}T\\d{6}Z_[0-9a-f]{8}_[0-9a-f]{4}$.

        Args:
            candidate_id: 12-hex candidate identifier.
            timestamp: Optional datetime; if omitted, current UTC time is used.

        Returns:
            Formatted report ID string.
        """
        ts = timestamp or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        ts_part = ts.strftime("%Y%m%dT%H%M%SZ")
        cid_hex = (
            candidate_id[:8].lower() if len(candidate_id) >= 8 else uuid.uuid4().hex[:8]
        )
        rand_hex = uuid.uuid4().hex[:4]
        return f"{ts_part}_{cid_hex}_{rand_hex}"

    @classmethod
    def build_flags(
        cls,
        candidate: Candidate,
        match: MatchResult,
        score: ScoreResult,
        ai: AIInsights | None,
    ) -> list[ReportFlag]:
        """Aggregate review flags from parsing, matching, scoring, and AI stages."""
        flags: list[ReportFlag] = []
        seen_codes: set[str] = set()

        def add_flag(code: str, message: str) -> None:
            if code not in seen_codes:
                flags.append(ReportFlag(code=code, message=message))
                seen_codes.add(code)

        # 1. Prompt-injection and manipulation indicators
        if candidate.injection_indicators:
            add_flag(
                "INJECTION_INDICATORS",
                "Possible attempt to manipulate automated screening — review manually.",
            )

        # 2. Missing required skills
        missing_required = [
            m
            for m in match.skill_matches
            if m.is_required and (m.credit < 0.5 or m.match_type == MatchType.NONE)
        ]
        if missing_required:
            add_flag(
                "MISSING_REQUIRED_SKILLS",
                f"{len(missing_required)} required skill(s) not found in resume.",
            )

        # 3. Incomplete candidate data
        has_incomplete = (
            "INCOMPLETE_DATA" in score.flags
            or candidate.total_experience_years is None
            or candidate.highest_education_level.value == 0
        )
        if has_incomplete:
            add_flag(
                "INCOMPLETE_DATA",
                "Resume has missing or incomplete experience or education data.",
            )

        # 4. Unknown data treated as zero
        if "UNKNOWN_TREATED_AS_ZERO" in score.flags:
            add_flag(
                "UNKNOWN_TREATED_AS_ZERO",
                "Unknown experience or education was treated as zero in scoring.",
            )

        # 5. Low text quality / parse warnings
        quality_codes = {"LOW_TEXT_QUALITY", "NO_SKILLS", "NO_EXPERIENCE_DATES"}
        if any(w.code in quality_codes for w in candidate.parse_warnings):
            add_flag(
                "LOW_PARSE_QUALITY",
                "Low parse quality detected; some information may be missing or unextracted.",
            )

        # 6. AI unavailable / errors
        if ai:
            features = [
                ai.categorization,
                ai.explanation,
                ai.recommendations,
                ai.interview_questions,
                ai.extraction_status,
            ]
            has_ai_issue = any(
                f is not None
                and f.status in (FeatureStatus.UNAVAILABLE, FeatureStatus.BLOCKED)
                for f in features
            )
            if has_ai_issue:
                add_flag(
                    "AI_UNAVAILABLE",
                    "One or more AI features could not be completed.",
                )

        return flags

    @classmethod
    def build_config_snapshot(
        cls,
        score: ScoreResult,
        settings: Settings | None,
    ) -> dict[str, Any]:
        """Build safe, secret-free snapshot of configuration parameters."""
        fuzzy_threshold = 85
        ai_enabled = False
        ai_provider = "none"
        ai_model: str | None = None

        if settings is not None:
            if hasattr(settings, "fuzzy") and hasattr(settings.fuzzy, "threshold"):
                fuzzy_threshold = settings.fuzzy.threshold
            elif hasattr(settings, "matching") and hasattr(
                settings.matching, "fuzzy_threshold"
            ):
                fuzzy_threshold = settings.matching.fuzzy_threshold
            if hasattr(settings, "ai"):
                ai_enabled = bool(getattr(settings.ai, "enabled", False))
                if ai_enabled:
                    ai_provider = str(getattr(settings.ai, "provider", "none"))
                    ai_model = getattr(settings.ai, "model", None)

        weights: dict[str, float] = {}
        if score.components:
            weights = {comp.name: comp.weight for comp in score.components}

        return {
            "strategy": score.strategy_name,
            "weights": weights,
            "fuzzy_threshold": fuzzy_threshold,
            "ai": {
                "enabled": ai_enabled,
                "provider": ai_provider,
                "model": ai_model,
            },
        }

    @classmethod
    def build(
        cls,
        candidate: Candidate,
        job: JobRequirements,
        match: MatchResult,
        score: ScoreResult,
        ai: AIInsights | None = None,
        settings: Settings | None = None,
        created_at: datetime | None = None,
    ) -> AnalysisReport:
        """Build an AnalysisReport combining all stage outputs into a validated schema.

        Args:
            candidate: Parsed and validated candidate profile.
            job: Validated job requirements.
            match: Evaluated match results.
            score: Evaluated score results.
            ai: Optional AI insights (defaults to empty insights).
            settings: Optional application settings for snapshot extraction.
            created_at: Optional fixed creation timestamp.

        Returns:
            Validated AnalysisReport instance.
        """
        created = created_at or datetime.now(UTC)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)

        report_id = cls.generate_report_id(candidate.candidate_id, created)
        app_version = "0.1.0"
        if (
            settings is not None
            and hasattr(settings, "app")
            and hasattr(settings.app, "version")
        ):
            app_version = settings.app.version

        ai_insights = ai or AIInsights()
        flags = cls.build_flags(candidate, match, score, ai_insights)
        config_snapshot = cls.build_config_snapshot(score, settings)

        return AnalysisReport(
            schema_version="1.0",
            report_id=report_id,
            created_at=created,
            app_version=app_version,
            config_snapshot=config_snapshot,
            candidate=candidate,
            job=job,
            match=match,
            score=score,
            ai=ai_insights,
            flags=flags,
            human_review_notice=HUMAN_REVIEW_NOTICE,
        )

    @classmethod
    def get_matched_skills(cls, report: AnalysisReport) -> list[SkillMatch]:
        """Return all skills with positive match credit."""
        return [m for m in report.match.skill_matches if m.credit > 0.0]

    @classmethod
    def get_missing_skills(cls, report: AnalysisReport) -> list[SkillMatch]:
        """Return missing skills (credit == 0), required skills listed first."""
        missing = [m for m in report.match.skill_matches if m.credit == 0.0]
        return sorted(missing, key=lambda m: (not m.is_required, m.target))
