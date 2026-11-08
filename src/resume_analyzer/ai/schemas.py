"""Pydantic schemas for structured Generative AI outputs (AI_PROMPTS §3-§7)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIBaseModel(BaseModel):
    """Base schema enforcing whitespace trimming and strict field checking."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# --- P1: Information Extraction Schemas ---


class ExtractionSkill(AIBaseModel):
    """Extracted skill item."""

    name: str = Field(min_length=1, max_length=80)


class ExtractionExperience(AIBaseModel):
    """Extracted experience record."""

    job_title: str | None = Field(default=None, max_length=100)
    company: str | None = Field(default=None, max_length=100)
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False


class ExtractionEducation(AIBaseModel):
    """Extracted education record."""

    degree: str | None = Field(default=None, max_length=120)
    field_of_study: str | None = Field(default=None, max_length=100)
    institution: str | None = Field(default=None, max_length=120)


class ExtractionResult(AIBaseModel):
    """Output envelope for P1 resume information extraction."""

    schema_version: str = "1.0"
    name: str | None = Field(default=None, max_length=100)
    skills: list[ExtractionSkill] = Field(default_factory=list)
    experience: list[ExtractionExperience] = Field(default_factory=list)
    education: list[ExtractionEducation] = Field(default_factory=list)
    suspected_injection: bool = False


# --- P2: Skill Categorization Schemas ---


class SkillCategoryItem(AIBaseModel):
    """Single categorized skill item."""

    skill: str
    category: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SkillCategorizationResult(AIBaseModel):
    """Output envelope for P2 skill categorization."""

    schema_version: str = "1.0"
    categories: list[SkillCategoryItem] = Field(default_factory=list)


# --- P3: Match Explanation Schemas ---


class StrengthItem(AIBaseModel):
    """Candidate strength cited with fact IDs."""

    point: str = Field(max_length=350)
    evidence: list[str] = Field(default_factory=list)


class ConcernItem(AIBaseModel):
    """Candidate gap or concern cited with fact IDs."""

    point: str = Field(max_length=350)
    evidence: list[str] = Field(default_factory=list)


class MatchExplanation(AIBaseModel):
    """Output envelope for P3 candidate-job compatibility explanation."""

    schema_version: str = "1.0"
    summary: str = Field(max_length=800)
    strengths: list[StrengthItem] = Field(default_factory=list)
    concerns: list[ConcernItem] = Field(default_factory=list)
    suggested_review_focus: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# --- P4: Improvement Recommendations Schemas ---


class RecommendationItem(AIBaseModel):
    """Single concrete improvement recommendation."""

    gap_id: str
    action: str = Field(max_length=300)
    resource_type: Literal[
        "course",
        "project",
        "certification",
        "practice",
        "work_experience",
        "resume_edit",
    ] = "practice"
    priority: Literal["high", "medium", "low"] = "medium"
    rationale: str = Field(max_length=250)


class ImprovementRecommendations(AIBaseModel):
    """Output envelope for P4 personalized improvement recommendations."""

    schema_version: str = "1.0"
    recommendations: list[RecommendationItem] = Field(default_factory=list)


# --- P5: Interview Questions Schemas ---


class InterviewQuestionItem(AIBaseModel):
    """Single structured interview question."""

    question: str = Field(min_length=10, max_length=400)
    category: Literal[
        "technical",
        "behavioral",
        "situational",
        "gap_probe",
        "verification",
    ] = "technical"
    target_skill: str | None = None
    difficulty: Literal["basic", "intermediate", "advanced"] = "intermediate"
    rationale: str = Field(max_length=250)
    what_to_listen_for: list[str] = Field(default_factory=list)


class InterviewQuestionsResult(AIBaseModel):
    """Output envelope for P5 interview question generation."""

    schema_version: str = "1.0"
    questions: list[InterviewQuestionItem] = Field(default_factory=list)
