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

    def score(self, match: MatchResult, job: JobRequirements) -> ScoreResult:
        """Calculate weighted score, evaluate dimensions, and assess data coverage."""
        flags: list[str] = []

        # 1. Determine status and subscore for each of the 4 dimensions
        dim_data: list[tuple[str, float, ComponentStatus, float | None]] = []

        # Dimension 1: required_skills (always evaluated)
        dim_data.append(
            (
                "required_skills",
                self.weights.required_skills,
                ComponentStatus.EVALUATED,
                match.required_credit,
            )
        )

        # Dimension 2: experience
        exp_weight = self.weights.experience
        if match.experience.status == "not_required":
            dim_data.append(("experience", exp_weight, ComponentStatus.NOT_APPLICABLE, None))
        elif match.experience.status == "unknown":
            if self.unknown_policy == "zero":
                dim_data.append(("experience", exp_weight, ComponentStatus.EVALUATED, 0.0))
            else:
                dim_data.append(("experience", exp_weight, ComponentStatus.UNKNOWN, None))
        else:
            dim_data.append(
                (
                    "experience",
                    exp_weight,
                    ComponentStatus.EVALUATED,
                    match.experience.subscore or 0.0,
                )
            )

        # Dimension 3: education
        edu_weight = self.weights.education
        if match.education.status == "not_required":
            dim_data.append(("education", edu_weight, ComponentStatus.NOT_APPLICABLE, None))
        elif match.education.status == "unknown":
            if self.unknown_policy == "zero":
                dim_data.append(("education", edu_weight, ComponentStatus.EVALUATED, 0.0))
            else:
                dim_data.append(("education", edu_weight, ComponentStatus.UNKNOWN, None))
        else:
            dim_data.append(
                (
                    "education",
                    edu_weight,
                    ComponentStatus.EVALUATED,
                    match.education.subscore or 0.0,
                )
            )

        # Dimension 4: optional_skills
        opt_weight = self.weights.optional_skills
        if not job.optional_skills or match.optional_credit is None:
            dim_data.append(("optional_skills", opt_weight, ComponentStatus.NOT_APPLICABLE, None))
        else:
            dim_data.append(
                (
                    "optional_skills",
                    opt_weight,
                    ComponentStatus.EVALUATED,
                    match.optional_credit,
                )
            )

        # 2. Renormalization & score calculation
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

        # 3. Calculate data coverage
        if self.unknown_policy == "zero":
            coverage = 1.0
        else:
            total_applicable = sum_w_evaluated + sum_w_unknown
            if total_applicable > 0.0:
                coverage = round(sum_w_evaluated / total_applicable, 4)
            else:
                coverage = 1.0

        # 4. Construct components with individual point contributions
        components: list[ScoreComponent] = []
        for name, weight, status, subscore in dim_data:
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

            components.append(
                ScoreComponent(
                    name=name,  # type: ignore[arg-type]
                    status=status,
                    weight=weight,
                    subscore=subscore,
                    points=pts,
                    explanation=explanation,
                )
            )

        # 5. Diagnostic flags
        if self.check_missing_required_skills(match):
            flags.append("MISSING_REQUIRED_SKILLS")

        if self.unknown_policy == "zero" and (
            match.experience.status == "unknown" or match.education.status == "unknown"
        ):
            flags.append("UNKNOWN_TREATED_AS_ZERO")

        if coverage < 1.0:
            flags.append("INCOMPLETE_DATA")

        fit_band = fit_band_for(total_score, self.bands)

        return ScoreResult(
            strategy_name=self.name,
            total_score=total_score,
            components=components,
            coverage=coverage,
            fit_band=fit_band,
            flags=flags,
        )
