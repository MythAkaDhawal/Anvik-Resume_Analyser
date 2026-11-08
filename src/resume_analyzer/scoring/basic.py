"""Basic scoring strategy based solely on required skill coverage (FR-12, §7.5)."""

from __future__ import annotations

from typing import ClassVar

from resume_analyzer.config.settings import BandThresholds
from resume_analyzer.models.enums import ComponentStatus
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import MatchResult, ScoreComponent, ScoreResult
from resume_analyzer.scoring.bands import fit_band_for
from resume_analyzer.scoring.base import ScoringStrategy


class BasicScoringStrategy(ScoringStrategy):
    """Basic scoring strategy evaluating required-skills coverage only.

    Formula: score_basic = 100 * required_credit
    Coverage is always 1.0. All dimensions other than required_skills are NOT_USED.
    """

    name: ClassVar[str] = "basic"

    def __init__(self, bands: BandThresholds | None = None) -> None:
        """Initialize BasicScoringStrategy with fit band thresholds."""
        self.bands = bands or BandThresholds()

    def score(self, match: MatchResult, job: JobRequirements) -> ScoreResult:
        """Calculate basic score from required skills credit."""
        raw_score = 100.0 * match.required_credit
        total_score = round(raw_score, 1)

        components: list[ScoreComponent] = [
            ScoreComponent(
                name="required_skills",
                status=ComponentStatus.EVALUATED,
                weight=1.0,
                subscore=match.required_credit,
                points=total_score,
                explanation=f"100 x {match.required_credit:.4f} required skill coverage",
            ),
            ScoreComponent(
                name="experience",
                status=ComponentStatus.NOT_USED,
                weight=0.0,
                subscore=None,
                points=None,
                explanation="Not evaluated in basic scoring strategy",
            ),
            ScoreComponent(
                name="education",
                status=ComponentStatus.NOT_USED,
                weight=0.0,
                subscore=None,
                points=None,
                explanation="Not evaluated in basic scoring strategy",
            ),
            ScoreComponent(
                name="optional_skills",
                status=ComponentStatus.NOT_USED,
                weight=0.0,
                subscore=None,
                points=None,
                explanation="Not evaluated in basic scoring strategy",
            ),
        ]

        flags: list[str] = []
        if self.check_missing_required_skills(match):
            flags.append("MISSING_REQUIRED_SKILLS")

        fit_band = fit_band_for(total_score, self.bands)

        return ScoreResult(
            strategy_name=self.name,
            total_score=total_score,
            components=components,
            coverage=1.0,
            fit_band=fit_band,
            flags=flags,
        )
