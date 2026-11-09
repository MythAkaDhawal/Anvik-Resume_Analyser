"""Weighted scoring strategy with renormalization, coverage, and fit bands (FR-12, §7.5)."""

from __future__ import annotations

import logging
from typing import ClassVar, Literal

from resume_analyzer.config.settings import BandThresholds, ScoreWeights
from resume_analyzer.exceptions import ConfigurationError
from resume_analyzer.models.enums import ComponentStatus
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import MatchResult, ScoreComponent, ScoreResult
from resume_analyzer.scoring.bands import fit_band_for
from resume_analyzer.scoring.base import ScoringStrategy

logger = logging.getLogger(__name__)


class WeightedScoringStrategy(ScoringStrategy):
    """Multi-criteria weighted scoring strategy.

    Evaluates required skills, professional experience, education, and optional skills.
    Renormalizes weights when dimensions are NOT_APPLICABLE or UNKNOWN (under exclude policy).
    Calculates diagnostic data coverage and applies FitBand thresholds.
    """

    name: ClassVar[str] = "weighted"

    def __init__(
        self,
        weights: ScoreWeights | None = None,
        unknown_policy: Literal["exclude", "zero"] = "exclude",
        bands: BandThresholds | None = None,
    ) -> None:
        """Initialize WeightedScoringStrategy with weights, policy, and bands.

        Raises:
            ConfigurationError: If configured dimension weights do not sum to 1.0.
        """
        self.weights = weights or ScoreWeights()
        self.unknown_policy = unknown_policy
        self.bands = bands or BandThresholds()

        # Strict weight sum validation
        w_sum = (
            self.weights.required_skills
            + self.weights.experience
            + self.weights.education
            + self.weights.optional_skills
        )
        if abs(w_sum - 1.0) > 0.0001:
            raise ConfigurationError(
                f"Scoring weights must sum to 1.0 (current sum: {w_sum:.4f})",
                key="scoring.weights",
            )

    def _resolve_dim(
        self,
        name: str,
        weight: float,
        status_str: str,
        subscore: float | None,
    ) -> tuple[str, float, ComponentStatus, float | None]:
        """Resolve dimension status and effective subscore given unknown policy."""
        if status_str == "not_required":
            return name, weight, ComponentStatus.NOT_APPLICABLE, None
        if status_str == "unknown":
            if self.unknown_policy == "zero":
                return name, weight, ComponentStatus.EVALUATED, 0.0
            return name, weight, ComponentStatus.UNKNOWN, None
        return name, weight, ComponentStatus.EVALUATED, subscore or 0.0

    def _build_component(
        self,
        name: str,
        weight: float,
        status: ComponentStatus,
        subscore: float | None,
        sum_w_evaluated: float,
    ) -> ScoreComponent:
        if status == ComponentStatus.EVALUATED and sum_w_evaluated > 0.0:
            renorm_w = weight / sum_w_evaluated
            pts = round(100.0 * renorm_w * (subscore or 0.0), 1)
            explanation = (
                f"Weight {weight:.2f} (effective {renorm_w:.2f}) x {subscore:.4f}"
            )
        elif status == ComponentStatus.UNKNOWN:
            pts = None
            explanation = "Candidate data unknown; excluded under active policy"
        else:
            pts = None
            explanation = "Dimension not applicable to position requirements"

        return ScoreComponent(
            name=name,  # type: ignore[arg-type]
            status=status,
            weight=weight,
            subscore=subscore,
            points=pts,
            explanation=explanation,
        )

    def _collect_scoring_flags(
        self,
        match: MatchResult,
        coverage: float,
    ) -> list[str]:
        flags: list[str] = []
        if self.check_missing_required_skills(match):
            flags.append("MISSING_REQUIRED_SKILLS")
        if self.unknown_policy == "zero" and (
            match.experience.status == "unknown" or match.education.status == "unknown"
        ):
            flags.append("UNKNOWN_TREATED_AS_ZERO")
        if coverage < 1.0:
            flags.append("INCOMPLETE_DATA")
        return flags

    def score(self, match: MatchResult, job: JobRequirements) -> ScoreResult:
        """Calculate weighted score, evaluate dimensions, and assess data coverage."""
        dim_data: list[tuple[str, float, ComponentStatus, float | None]] = [
            (
                "required_skills",
                self.weights.required_skills,
                ComponentStatus.EVALUATED,
                match.required_credit,
            ),
            self._resolve_dim(
                "experience",
                self.weights.experience,
                match.experience.status,
                match.experience.subscore,
            ),
            self._resolve_dim(
                "education",
                self.weights.education,
                match.education.status,
                match.education.subscore,
            ),
        ]

        if not job.optional_skills or match.optional_credit is None:
            dim_data.append(
                (
                    "optional_skills",
                    self.weights.optional_skills,
                    ComponentStatus.NOT_APPLICABLE,
                    None,
                )
            )
        else:
            dim_data.append(
                (
                    "optional_skills",
                    self.weights.optional_skills,
                    ComponentStatus.EVALUATED,
                    match.optional_credit,
                )
            )

        evaluated_dims = [d for d in dim_data if d[2] == ComponentStatus.EVALUATED]
        unknown_dims = [d for d in dim_data if d[2] == ComponentStatus.UNKNOWN]

        sum_w_evaluated = sum(d[1] for d in evaluated_dims)
        sum_w_unknown = sum(d[1] for d in unknown_dims)

        if sum_w_evaluated > 0.0:
            weighted_subscore_sum = sum(d[1] * (d[3] or 0.0) for d in evaluated_dims)
            raw_score = 100.0 * (weighted_subscore_sum / sum_w_evaluated)
        else:
            raw_score = 0.0

        total_score = round(raw_score, 1)

        if self.unknown_policy == "zero":
            coverage = 1.0
        else:
            total_applicable = sum_w_evaluated + sum_w_unknown
            coverage = (
                round(sum_w_evaluated / total_applicable, 4)
                if total_applicable > 0.0
                else 1.0
            )

        components = [
            self._build_component(name, weight, status, subscore, sum_w_evaluated)
            for name, weight, status, subscore in dim_data
        ]
        flags = self._collect_scoring_flags(match, coverage)
        fit_band = fit_band_for(total_score, self.bands)

        return ScoreResult(
            strategy_name=self.name,
            total_score=total_score,
            components=components,
            coverage=coverage,
            fit_band=fit_band,
            flags=flags,
        )
