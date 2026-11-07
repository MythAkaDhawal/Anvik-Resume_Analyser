"""Domain models, enums, schemas, and analysis result data structures."""

from __future__ import annotations

from resume_analyzer.models.candidate import (
    Candidate,
    EducationEntry,
    ExperienceEntry,
    ParseWarning,
    Skill,
)
from resume_analyzer.models.enums import (
    ComponentStatus,
    EducationLevel,
    FeatureStatus,
    FitBand,
    MatchType,
    Provenance,
)
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import (
    DEFAULT_HUMAN_REVIEW_NOTICE,
    AIInsights,
    AnalysisReport,
    EducationAnalysis,
    ExperienceAnalysis,
    FeatureResult,
    MatchResult,
    ReportFlag,
    ScoreComponent,
    ScoreResult,
    SkillMatch,
)

__all__ = [
    "DEFAULT_HUMAN_REVIEW_NOTICE",
    "AIInsights",
    "AnalysisReport",
    "Candidate",
    "ComponentStatus",
    "EducationAnalysis",
    "EducationEntry",
    "EducationLevel",
    "ExperienceAnalysis",
    "ExperienceEntry",
    "FeatureResult",
    "FeatureStatus",
    "FitBand",
    "JobRequirements",
    "MatchResult",
    "MatchType",
    "ParseWarning",
    "Provenance",
    "ReportFlag",
    "ScoreComponent",
    "ScoreResult",
    "Skill",
    "SkillMatch",
]
