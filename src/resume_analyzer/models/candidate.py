"""Candidate profile, skill, experience, and education data models.

Enforces strict schema validation (extra='forbid', whitespace stripping)
and guarantees absence of protected/proxy demographic attributes (NFR-14).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from resume_analyzer.models.enums import EducationLevel, Provenance


class CandidateBaseModel(BaseModel):
    """Base model enforcing extra key prohibition and whitespace stripping."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ParseWarning(CandidateBaseModel):
    """Warning diagnostic produced during resume parsing.

    Attributes:
        code: Warning identifier code (e.g. 'NO_EXPERIENCE_DATES').
        message: Human-readable warning message free of resume text or PII.
        field: Optional name of the resume section or field involved.
    """

    code: str
    message: str
    field: str | None = None


class Skill(CandidateBaseModel):
    """Extracted candidate skill entity.

    Attributes:
        name: Skill string as extracted from resume (1-60 characters).
        canonical_name: Normalized canonical form from taxonomy, or None.
        category: Skill category name (e.g., 'Languages', 'Cloud/DevOps').
        category_provenance: Provenance of the category assignment.
        provenance: Provenance of the skill extraction.
        mentions: Number of occurrences detected in the resume text (>= 1).
    """

    name: str = Field(min_length=1, max_length=60)
    canonical_name: str | None = None
    category: str | None = None
    category_provenance: Provenance | None = None
    provenance: Provenance = Provenance.EXTRACTED_RULE
    mentions: int = Field(default=1, ge=1)


class ExperienceEntry(CandidateBaseModel):
    """A distinct professional employment record.

    Attributes:
        job_title: Position or role title.
        company: Employing organisation or company.
        start: Start date normalised to the first day of the month.
        end: End date normalised to first day of month; None if current/ongoing.
        is_current: True if explicitly stated as present/current role.
        duration_months: Elapsed calendar months computed from dates only.
        provenance: Provenance attribution label.
    """

    job_title: str | None = None
    company: str | None = None
    start: date | None = None
    end: date | None = None
    is_current: bool = False
    duration_months: int | None = Field(default=None, ge=0)
    provenance: Provenance = Provenance.EXTRACTED_RULE


class EducationEntry(CandidateBaseModel):
    """An educational degree or qualification record.

    Attributes:
        degree: Raw degree title text as identified in resume.
        level: Ordinal attainment level computed deterministically.
        field_of_study: Academic discipline or major.
        institution: College, university, or issuing institution.
        provenance: Provenance attribution label.
    """

    degree: str | None = None
    level: EducationLevel = EducationLevel.UNSPECIFIED
    field_of_study: str | None = None
    institution: str | None = None
    provenance: Provenance = Provenance.EXTRACTED_RULE


class Candidate(CandidateBaseModel):
    """Structured representation of a parsed candidate resume.

    Demographic attributes (age, DOB, gender, nationality, religion, photo,
    address, phone, marital status, graduation year) are deliberately excluded.

    Attributes:
        candidate_id: First 12 hex characters of SHA-256(file bytes).
        name: Candidate full name, or None if omitted/not found.
        email: Candidate email address, or None if omitted/not found.
        skills: List of extracted skills.
        experience: Ordered list of extracted work history entries.
        education: List of extracted educational qualifications.
        total_experience_years: Total non-overlapping years of experience; None if unknown.
        highest_education_level: Highest attainment level across education entries.
        source_format: Original upload file format ('pdf', 'docx', 'txt').
        parse_warnings: List of parse-quality diagnostic warnings.
        injection_indicators: Heuristic security scan indicator codes.
        parser_version: Semantic version of the parser that produced this object.
    """

    candidate_id: str = Field(pattern=r"^[0-9a-f]{12}$")
    name: str | None = None
    email: str | None = None
    skills: list[Skill] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    total_experience_years: float | None = Field(default=None, ge=0.0)
    highest_education_level: EducationLevel = EducationLevel.UNSPECIFIED
    source_format: Literal["pdf", "docx", "txt"]
    parse_warnings: list[ParseWarning] = Field(default_factory=list)
    injection_indicators: list[str] = Field(default_factory=list)
    parser_version: str
