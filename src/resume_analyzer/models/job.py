"""Job requirements specification and validation models.

Enforces bounds, case-insensitive deduplication, and aggregated error collection
via JobValidationError (code E-DATA-001).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resume_analyzer.exceptions import JobValidationError
from resume_analyzer.models.enums import EducationLevel


def _validate_job_title_and_desc(data: dict[str, Any], errors: list[str]) -> None:
    """Validate job title and optional description length."""
    raw_title = data.get("job_title")
    if raw_title is None or not str(raw_title).strip():
        errors.append(
            "Job title is required and cannot be empty (must be 1-100 characters)"
        )
    else:
        title_str = str(raw_title).strip()
        if len(title_str) > 100:
            errors.append(
                f"Job title exceeds 100 characters (length: {len(title_str)})"
            )
        data["job_title"] = title_str

    raw_desc = data.get("description")
    if raw_desc is not None:
        desc_str = str(raw_desc).strip()
        if len(desc_str) > 5000:
            errors.append(
                f"Description exceeds 5000 characters (length: {len(desc_str)})"
            )
        data["description"] = desc_str


def _validate_job_skills(data: dict[str, Any], errors: list[str]) -> None:
    """Validate and deduplicate required and optional job skills."""
    raw_required = data.get("required_skills")
    cleaned_required: list[str] = []
    seen_required_lower: set[str] = set()

    if raw_required is None or not isinstance(raw_required, list):
        errors.append("required_skills must be a non-empty list of skill names")
    else:
        for item in raw_required:
            if item is None:
                continue
            s = str(item).strip()
            if not s:
                continue
            if len(s) > 60:
                errors.append(f"Required skill '{s[:30]}...' exceeds 60 characters")
            lower = s.lower()
            if lower not in seen_required_lower:
                seen_required_lower.add(lower)
                cleaned_required.append(s)

        if not cleaned_required:
            errors.append("At least one required skill must be specified")
        elif len(cleaned_required) > 50:
            errors.append(
                f"Required skills list exceeds 50 items (count: {len(cleaned_required)})"
            )

    data["required_skills"] = cleaned_required

    raw_optional = data.get("optional_skills", [])
    cleaned_optional: list[str] = []
    seen_optional_lower: set[str] = set()

    if raw_optional is not None:
        if not isinstance(raw_optional, list):
            errors.append("optional_skills must be a list of skill names")
        else:
            for item in raw_optional:
                if item is None:
                    continue
                s = str(item).strip()
                if not s:
                    continue
                if len(s) > 60:
                    errors.append(f"Optional skill '{s[:30]}...' exceeds 60 characters")
                lower = s.lower()
                if lower in seen_required_lower:
                    errors.append(
                        f"Skill '{s}' appears in both required and optional skills"
                    )
                elif lower not in seen_optional_lower:
                    seen_optional_lower.add(lower)
                    cleaned_optional.append(s)

            if len(cleaned_optional) > 50:
                errors.append(
                    f"Optional skills list exceeds 50 items (count: {len(cleaned_optional)})"
                )

    data["optional_skills"] = cleaned_optional


def _validate_job_requirements(data: dict[str, Any], errors: list[str]) -> None:
    """Validate experience years, education level, and preferred fields."""
    raw_exp = data.get("min_experience_years", 0)
    try:
        exp_val = float(raw_exp)
        if exp_val < 0.0 or exp_val > 50.0:
            errors.append(
                f"min_experience_years must be between 0 and 50 (got {exp_val})"
            )
        data["min_experience_years"] = exp_val
    except (ValueError, TypeError):
        errors.append(f"min_experience_years must be a valid number (got {raw_exp})")

    raw_edu = data.get("min_education_level", EducationLevel.UNSPECIFIED)
    if isinstance(raw_edu, (str, int)) and not isinstance(raw_edu, EducationLevel):
        data["min_education_level"] = EducationLevel.from_string(raw_edu)

    raw_pref = data.get("preferred_fields", [])
    if raw_pref is not None:
        if not isinstance(raw_pref, list):
            errors.append("preferred_fields must be a list of strings")
        else:
            if len(raw_pref) > 10:
                errors.append(
                    f"preferred_fields exceeds 10 items (got {len(raw_pref)})"
                )
            data["preferred_fields"] = [
                str(f).strip() for f in raw_pref if str(f).strip()
            ]


class JobRequirements(BaseModel):
    """Specification of job requirements against which resumes are evaluated.

    Attributes:
        job_id: Unique slug or UUID identifier.
        job_title: Official position title (1-100 characters).
        description: Optional role summary or context (max 5000 characters).
        required_skills: Mandatory skills list (1-50 items, each 1-60 chars).
        optional_skills: Nice-to-have skills list (0-50 items, each 1-60 chars).
        min_experience_years: Minimum required experience in years (0-50).
        min_education_level: Minimum required education attainment level.
        preferred_fields: Preferred academic majors/disciplines (0-10 items).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    job_id: str = Field(default_factory=lambda: f"job-{uuid.uuid4().hex[:8]}")
    job_title: str
    description: str | None = None
    required_skills: list[str]
    optional_skills: list[str] = Field(default_factory=list)
    min_experience_years: float = Field(default=0.0)
    min_education_level: EducationLevel = EducationLevel.UNSPECIFIED
    preferred_fields: list[str] = Field(default_factory=list)

    @property
    def title(self) -> str:
        """Alias property for job_title."""
        return self.job_title

    @property
    def education_level(self) -> EducationLevel:
        """Alias property for min_education_level."""
        return self.min_education_level

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize_job(cls, data: Any) -> Any:
        """Validate all job fields and collect all issues into JobValidationError."""
        if not isinstance(data, dict):
            return data

        # Map common aliases if present
        if "title" in data and "job_title" not in data:
            data["job_title"] = data.pop("title")
        if "education_level" in data and "min_education_level" not in data:
            data["min_education_level"] = data.pop("education_level")

        errors: list[str] = []
        _validate_job_title_and_desc(data, errors)
        _validate_job_skills(data, errors)
        _validate_job_requirements(data, errors)

        if errors:
            raise JobValidationError(
                message=f"Job validation failed with {len(errors)} error(s)",
                errors=errors,
            )

        return data
