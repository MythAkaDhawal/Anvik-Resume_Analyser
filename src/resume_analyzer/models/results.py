"""Matching, scoring, AI augmentation, and final analysis report models.

Implements strict validation across all analysis outputs, maintaining provenance
separation and human-review governance notices.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from resume_analyzer.models.candidate import Candidate
from resume_analyzer.models.enums import (
    ComponentStatus,
    EducationLevel,
    FeatureStatus,
    FitBand,
    MatchType,
    Provenance,
)
from resume_analyzer.models.job import JobRequirements

T = TypeVar("T")

DEFAULT_HUMAN_REVIEW_NOTICE = (
    "This report supports, and does not replace, human judgement. "
    "Scores reflect alignment between stated requirements and information extracted from the resume. "
    "AI-generated sections are interpretations that have not been verified. "
    "Do not use this report as the sole basis for any employment decision."
)


class ResultsBaseModel(BaseModel):
    """Base model enforcing strict schema validation and whitespace trimming."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SkillMatch(ResultsBaseModel):
    """Evaluation result for a single skill required or desired by a job.

    Attributes:
        target: Skill name as specified in the job requirement.
        target_canonical: Canonical taxonomy identifier, or None if unrecognized.
        is_required: True if skill was in required_skills, False if in optional_skills.
        matched_candidate_skill: Exact string from candidate skills that satisfied match.
        match_type: Type of match achieved (EXACT, ALIAS, FUZZY, or NONE).
        similarity: Similarity score 0.0-100.0 (100 for exact/alias, ratio for fuzzy, 0 for none).
        credit: Normalized credit contribution 0.0-1.0.
        provenance: Always Provenance.COMPUTED.
    """

    target: str
    target_canonical: str | None = None
    is_required: bool
    matched_candidate_skill: str | None = None
    match_type: MatchType
    similarity: float = Field(ge=0.0, le=100.0)
    credit: float = Field(ge=0.0, le=1.0)
    provenance: Provenance = Provenance.COMPUTED


class ExperienceAnalysis(ResultsBaseModel):
    """Evaluation of candidate work experience against minimum required years.

    Attributes:
        required_years: Target experience specified in the job.
        candidate_years: Extracted years of experience, or None if unknown.
        status: Alignment category ('met', 'partial', 'unmet', 'unknown', 'not_required').
        subscore: Normalized subscore 0.0-1.0 or None.
        gap_years: Difference between required and candidate years if deficient.
        provenance: Always Provenance.COMPUTED.
    """

    required_years: float = Field(ge=0.0)
    candidate_years: float | None = Field(default=None, ge=0.0)
    status: Literal["met", "partial", "unmet", "unknown", "not_required"]
    subscore: float | None = Field(default=None, ge=0.0, le=1.0)
    gap_years: float | None = None
    provenance: Provenance = Provenance.COMPUTED


class EducationAnalysis(ResultsBaseModel):
    """Evaluation of candidate education attainment against minimum required level.

    Attributes:
        required_level: Target attainment level required by the job.
        candidate_level: Candidate's highest detected attainment level.
        status: Alignment category ('met', 'below', 'unknown', 'not_required').
        field_match: True if candidate field matches preferred fields, or None.
        subscore: Normalized subscore 0.0-1.0 or None.
        provenance: Always Provenance.COMPUTED.
    """

    required_level: EducationLevel
    candidate_level: EducationLevel
    status: Literal["met", "below", "unknown", "not_required"]
    field_match: bool | None = None
    subscore: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: Provenance = Provenance.COMPUTED


class MatchResult(ResultsBaseModel):
    """Aggregated output from deterministic candidate-job matching engine.

    Attributes:
        skill_matches: One evaluation per job skill (both required and optional).
        required_credit: Mean credit across all required skills (0.0-1.0).
        optional_credit: Mean credit across optional skills, or None if no optional skills.
        experience: Evaluation of professional experience.
        education: Evaluation of educational attainment.
    """

    skill_matches: list[SkillMatch]
    required_credit: float = Field(ge=0.0, le=1.0)
    optional_credit: float | None = Field(default=None, ge=0.0, le=1.0)
    experience: ExperienceAnalysis
    education: EducationAnalysis

    @property
    def matched_skills(self) -> list[SkillMatch]:
        """Matched skills where match_type is not NONE."""
        return [s for s in self.skill_matches if s.match_type.value != "none"]

    @property
    def missing_required(self) -> list[str]:
        """Required target skills that were not matched."""
        return [
            s.target
            for s in self.skill_matches
            if s.is_required and s.match_type.value == "none"
        ]

    @property
    def missing_optional(self) -> list[str]:
        """Optional target skills that were not matched."""
        return [
            s.target
            for s in self.skill_matches
            if not s.is_required and s.match_type.value == "none"
        ]

    @property
    def experience_eval(self) -> ExperienceAnalysis:
        """Alias property for experience."""
        return self.experience

    @property
    def education_eval(self) -> EducationAnalysis:
        """Alias property for education."""
        return self.education


class ScoreComponent(ResultsBaseModel):
    """Contribution of a single evaluation dimension to the overall score.

    Attributes:
        name: Name of scoring dimension.
        status: Evaluation status of this dimension.
        weight: Configured weight assigned to this dimension.
        subscore: Evaluated subscore 0.0-1.0 or None.
        points: Absolute points contributed to total score on 0-100 scale.
        explanation: Formula description showing calculation breakdown.
    """

    name: Literal["required_skills", "experience", "education", "optional_skills"]
    status: ComponentStatus
    weight: float = Field(ge=0.0, le=1.0)
    subscore: float | None = Field(default=None, ge=0.0, le=1.0)
    points: float | None = Field(default=None, ge=0.0, le=100.0)
    explanation: str


class ScoreResult(ResultsBaseModel):
    """Final computed alignment score, fit band, and contributing components.

    Attributes:
        strategy_name: Identifier of scoring strategy applied ('basic' or 'weighted').
        total_score: Overall score rounded to 1 decimal place (0.0-100.0).
        components: List of score components contributing to total.
        coverage: Proportion of intended weight that was evaluable (0.0-1.0).
        fit_band: Coarse fit category ('strong', 'moderate', 'limited', 'low').
        flags: System flags (e.g., 'INCOMPLETE_DATA', 'MISSING_REQUIRED_SKILLS').
        provenance: Always Provenance.COMPUTED.
    """

    strategy_name: str
    total_score: float = Field(ge=0.0, le=100.0)
    components: list[ScoreComponent]
    coverage: float = Field(ge=0.0, le=1.0)
    fit_band: FitBand
    flags: list[str] = Field(default_factory=list)
    provenance: Provenance = Provenance.COMPUTED


class FeatureResult(ResultsBaseModel, Generic[T]):
    """Standardized envelope for individual AI-augmented feature outputs.

    Attributes:
        feature: Unique identifier of AI feature (e.g. 'explanation').
        status: Invocation outcome ('ok', 'partial', 'unavailable', 'disabled', 'blocked').
        data: Validated payload of type T, or None if unavailable/disabled.
        error_code: Error identifier if feature encountered failure.
        prompt_id: Identifier of prompt template invoked.
        prompt_version: Semantic version of prompt template.
        model: Model name/identifier that generated output.
        provenance: Always Provenance.AI_GENERATED.
        dropped_items: Count of items dropped by post-inference grounding/validation.
    """

    feature: Literal[
        "extraction",
        "categorization",
        "explanation",
        "recommendations",
        "interview_questions",
    ]
    status: FeatureStatus
    data: T | None = None
    error_code: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    provenance: Provenance = Provenance.AI_GENERATED
    dropped_items: int = Field(default=0, ge=0)


class AIInsights(ResultsBaseModel):
    """Container holding outputs for all five optional AI augmentation features.

    Attributes:
        categorization: P2 AI skill categorization output.
        explanation: P3 deterministic match explanation.
        recommendations: P4 candidate improvement recommendations.
        interview_questions: P5 targeted interview questions.
        extraction_status: P1 AI extraction status metadata.
    """

    categorization: FeatureResult[list[Any]] | None = None
    explanation: FeatureResult[Any] | None = None
    recommendations: FeatureResult[list[Any]] | None = None
    interview_questions: FeatureResult[list[Any]] | None = None
    extraction_status: FeatureResult[None] | None = None


class ReportFlag(ResultsBaseModel):
    """Human-review advisory flag attached to an AnalysisReport.

    Attributes:
        code: Machine-readable flag code (e.g. 'MISSING_REQUIRED_SKILLS').
        message: Explanatory note describing reason for flag.
    """

    code: str
    message: str


class AnalysisReport(ResultsBaseModel):
    """Top-level immutable analysis report consolidating all pipeline stages.

    Attributes:
        schema_version: Report schema version ('1.0').
        report_id: Unique analysis identifier matching format YYYYMMDDTHHMMSSZ_<hex8>_<hex4>.
        created_at: Timezone-aware UTC timestamp when report was produced.
        app_version: Software version of resume analyzer.
        config_snapshot: Safe snapshot of configuration used for this analysis.
        candidate: Structured candidate profile.
        job: Job requirements specifications.
        match: Deterministic matching evaluation.
        score: Deterministic score calculation and fit band.
        ai: Optional AI-generated insights and recommendations.
        flags: Advisory flags for human reviewer.
        human_review_notice: Mandatory static human-judgement legal disclaimer.
    """

    schema_version: Literal["1.0"] = "1.0"
    report_id: str = Field(pattern=r"^\d{8}T\d{6}Z_[0-9a-f]{8}_[0-9a-f]{4}$")
    created_at: datetime
    app_version: str
    config_snapshot: dict[str, Any]
    candidate: Candidate
    job: JobRequirements
    match: MatchResult
    score: ScoreResult
    ai: AIInsights = Field(default_factory=AIInsights)
    flags: list[ReportFlag] = Field(default_factory=list)
    human_review_notice: str = DEFAULT_HUMAN_REVIEW_NOTICE

    @property
    def strategy_used(self) -> str:
        """Convenience property for strategy name."""
        return self.score.strategy_name
