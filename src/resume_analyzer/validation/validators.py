"""Central validation and quality assessment for jobs and candidate profiles (FR-08).

Enforces semantic constraints, collects all validation issues into single aggregated errors,
and emits parse-quality warnings without ever echoing untrusted resume text or PII.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from resume_analyzer.exceptions import DataValidationError, JobValidationError
from resume_analyzer.models.candidate import Candidate, ParseWarning
from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.models.job import JobRequirements

logger = logging.getLogger(__name__)

# Standard email regex pattern for candidate validation
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _validate_job_title_desc(job: JobRequirements, errors: list[str]) -> str:
    title = (job.job_title or "").strip()
    if not title:
        errors.append(
            "Job title is required and cannot be empty (must be 1-100 characters)"
        )
    elif len(title) > 100:
        errors.append(f"Job title exceeds 100 characters (length: {len(title)})")
    if job.description is not None:
        desc = job.description.strip()
        if len(desc) > 5000:
            errors.append(f"Description exceeds 5000 characters (length: {len(desc)})")
    return title


def _validate_job_skills_list(
    job: JobRequirements, errors: list[str]
) -> tuple[list[str], list[str]]:
    cleaned_required: list[str] = []
    seen_required_lower: set[str] = set()
    for item in job.required_skills:
        if not item:
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

    cleaned_optional: list[str] = []
    seen_optional_lower: set[str] = set()
    for item in job.optional_skills:
        if not item:
            continue
        s = str(item).strip()
        if not s:
            continue
        if len(s) > 60:
            errors.append(f"Optional skill '{s[:30]}...' exceeds 60 characters")
        lower = s.lower()
        if lower in seen_required_lower:
            errors.append(f"Skill '{s}' appears in both required and optional skills")
        elif lower not in seen_optional_lower:
            seen_optional_lower.add(lower)
            cleaned_optional.append(s)
    if len(cleaned_optional) > 50:
        errors.append(
            f"Optional skills list exceeds 50 items (count: {len(cleaned_optional)})"
        )
    return cleaned_required, cleaned_optional


def validate_job(job: JobRequirements | dict[str, Any]) -> JobRequirements:
    """Validate a job specification, collecting all errors before failing.

    Args:
        job: JobRequirements instance or dictionary of requirements.

    Returns:
        Validated and normalized JobRequirements instance.

    Raises:
        JobValidationError: If any job specification rules are violated
            (aggregates all issues with code E-DATA-001).
    """
    if isinstance(job, dict):
        # Initial dictionary construction runs Pydantic model validator
        return JobRequirements(**job)

    if not isinstance(job, JobRequirements):
        raise JobValidationError(
            "Job requirements must be a JobRequirements model or dict.",
            errors=["Input is not a JobRequirements model or dictionary."],
        )

    errors: list[str] = []

    title = _validate_job_title_desc(job, errors)
    cleaned_required, cleaned_optional = _validate_job_skills_list(job, errors)

    if job.min_experience_years < 0.0 or job.min_experience_years > 50.0:
        errors.append(
            f"min_experience_years must be between 0 and 50 (got {job.min_experience_years})"
        )

    if len(job.preferred_fields) > 10:
        errors.append(
            f"preferred_fields exceeds 10 items (got {len(job.preferred_fields)})"
        )

    if errors:
        raise JobValidationError(
            message=f"Job validation failed with {len(errors)} error(s)",
            errors=errors,
        )

    # Return refreshed model with trimmed values
    return JobRequirements(
        job_id=job.job_id,
        job_title=title,
        description=job.description.strip() if job.description else None,
        required_skills=cleaned_required,
        optional_skills=cleaned_optional,
        min_experience_years=job.min_experience_years,
        min_education_level=job.min_education_level,
        preferred_fields=[f.strip() for f in job.preferred_fields if f.strip()],
    )


def _check_candidate_impossibilities(candidate: Candidate) -> None:
    """Assert candidate structural bounds, raising DataValidationError on impossibility."""
    if (
        not candidate.candidate_id
        or len(candidate.candidate_id) != 12
        or not re.match(r"^[0-9a-f]{12}$", candidate.candidate_id)
    ):
        raise DataValidationError(
            "Candidate candidate_id is invalid (must be 12-character hexadecimal digest).",
            error_code="E-DATA-002",
            user_message="Candidate identifier is invalid or corrupt.",
        )

    if (
        candidate.total_experience_years is not None
        and candidate.total_experience_years < 0.0
    ):
        raise DataValidationError(
            "Candidate total experience years cannot be negative.",
            error_code="E-DATA-002",
            user_message="Candidate data contains invalid negative experience years.",
        )

    for entry in candidate.experience:
        if entry.duration_months is not None and entry.duration_months < 0:
            raise DataValidationError(
                "Experience entry duration cannot be negative.",
                error_code="E-DATA-002",
                user_message="Candidate experience entry contains invalid negative duration.",
            )


def _check_candidate_warnings(
    candidate: Candidate, ref_date: date
) -> list[ParseWarning]:
    """Check non-fatal data sanity warnings for candidate profile."""
    warnings: list[ParseWarning] = []

    if candidate.name and len(candidate.name) > 100:
        warnings.append(
            ParseWarning(
                code="NAME_TOO_LONG",
                message="Extracted candidate name exceeds 100 characters.",
                field="name",
            )
        )

    if candidate.email and not EMAIL_REGEX.match(candidate.email):
        warnings.append(
            ParseWarning(
                code="INVALID_EMAIL",
                message="Extracted candidate email does not match standard email structure.",
                field="email",
            )
        )

    if len(candidate.skills) > 300:
        warnings.append(
            ParseWarning(
                code="SKILL_LIST_TRUNCATED",
                message="Extracted skills count exceeded 300; list exceeds maximum recommended limit.",
                field="skills",
            )
        )

    future_bound = date(ref_date.year + 1, ref_date.month, ref_date.day)
    for entry in candidate.experience:
        if entry.start and entry.start > future_bound:
            warnings.append(
                ParseWarning(
                    code="FUTURE_DATE",
                    message="Experience start date is more than one year in the future.",
                    field="experience",
                )
            )
        if entry.start and entry.end and entry.end < entry.start:
            warnings.append(
                ParseWarning(
                    code="INVALID_DATE_RANGE",
                    message="Experience end date precedes the recorded start date.",
                    field="experience",
                )
            )

    return warnings


def validate_candidate(
    candidate: Candidate, reference_date: date | None = None
) -> list[ParseWarning]:
    """Perform sanity checks on a parsed Candidate profile.

    Validates structurally plausible bounds and emits non-fatal ParseWarnings.
    Never echoes raw resume text or candidate PII in warning messages.

    Args:
        candidate: Candidate profile to validate.
        reference_date: Reference date for current/future date checks. Defaults to date.today().

    Returns:
        List of generated ParseWarnings.

    Raises:
        DataValidationError: If candidate data contains structurally impossible values
            (e.g., negative duration or negative total experience years) with code E-DATA-002.
    """
    ref_date = reference_date or date.today()
    _check_candidate_impossibilities(candidate)
    return _check_candidate_warnings(candidate, ref_date)


def assess_parse_quality(candidate: Candidate) -> list[ParseWarning]:
    """Evaluate candidate completeness and emit standard parse-quality warnings.

    Detects missing or sparse sections and emits standardized warning codes
    per TECHNICAL_SPECIFICATION §6.8: NO_SKILLS, NO_EXPERIENCE_DATES,
    NO_EDUCATION, NO_EMAIL, NO_NAME.
    Messages are strictly neutral and contain no personal identifiers.

    Args:
        candidate: Candidate profile to evaluate.

    Returns:
        List of standard ParseWarning instances for missing or sparse sections.
    """
    quality_warnings: list[ParseWarning] = []

    # 1. Candidate Name check
    if not candidate.name or not candidate.name.strip():
        quality_warnings.append(
            ParseWarning(
                code="NO_NAME",
                message="Candidate name could not be reliably determined from document header.",
                field="name",
            )
        )

    # 2. Candidate Email check
    if not candidate.email or not candidate.email.strip():
        quality_warnings.append(
            ParseWarning(
                code="NO_EMAIL",
                message="No valid candidate email address detected in resume text.",
                field="email",
            )
        )

    # 3. Skills check
    if not candidate.skills:
        quality_warnings.append(
            ParseWarning(
                code="NO_SKILLS",
                message="No technical or professional skills were detected in the resume.",
                field="skills",
            )
        )

    # 4. Experience check
    has_experience_dates = any(e.start is not None for e in candidate.experience)
    if not candidate.experience or not has_experience_dates:
        quality_warnings.append(
            ParseWarning(
                code="NO_EXPERIENCE_DATES",
                message="No parseable employment history or dated work experience entries were identified.",
                field="experience",
            )
        )

    # 5. Education check
    has_valid_education = (
        len(candidate.education) > 0
        and candidate.highest_education_level != EducationLevel.UNSPECIFIED
    )
    if not has_valid_education:
        quality_warnings.append(
            ParseWarning(
                code="NO_EDUCATION",
                message="No recognized educational qualifications or degrees were found in the resume.",
                field="education",
            )
        )

    return quality_warnings
