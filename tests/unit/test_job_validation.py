"""Unit tests for JobRequirements validation and error collection (UT-VAL-01..03, UT-VAL-06)."""

from __future__ import annotations

import pytest

from resume_analyzer.exceptions import DataValidationError, JobValidationError
from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.models.job import JobRequirements


def test_valid_job_accepted_and_whitespace_trimmed() -> None:
    """UT-VAL-01: Valid job accepted; whitespace trimmed on title and skills."""
    job = JobRequirements(
        job_title="   Software Engineer   ",
        description="  Backend engineer role  ",
        required_skills=["  Python  ", " Docker\t", "AWS "],
        optional_skills=[" Git "],
        min_experience_years=3,
        min_education_level=EducationLevel.BACHELOR,
    )

    assert job.job_title == "Software Engineer"
    assert job.description == "Backend engineer role"
    assert job.required_skills == ["Python", "Docker", "AWS"]
    assert job.optional_skills == ["Git"]
    assert job.min_experience_years == 3.0
    assert job.min_education_level == EducationLevel.BACHELOR


def test_job_with_several_problems_collects_all_errors() -> None:
    """UT-VAL-02: Job with several problems produces one JobValidationError listing all issues."""
    too_many_skills = [f"Skill_{i}" for i in range(55)]

    raw_data = {
        "job_title": "   ",  # Problem 1: empty title
        "required_skills": too_many_skills,  # Problem 2: exceeds 50 skills
        "min_experience_years": -5.0,  # Problem 3: negative experience
    }

    with pytest.raises(JobValidationError) as exc_info:
        JobRequirements.model_validate(raw_data)

    err = exc_info.value
    assert isinstance(err, DataValidationError)
    assert err.error_code == "E-DATA-001"

    # Verify that all problems were aggregated in the error details
    collected_errors = err.details.get("errors", [])
    assert len(collected_errors) >= 3

    error_blob = " ".join(collected_errors).lower()
    assert "title" in error_blob
    assert "50" in error_blob or "exceeds" in error_blob
    assert "negative" in error_blob or "between 0 and 50" in error_blob


def test_job_empty_required_skills_fails() -> None:
    """UT-VAL-02 (additional): Job with empty required_skills list fails."""
    with pytest.raises(JobValidationError) as exc_info:
        JobRequirements.model_validate(
            {
                "job_title": "Data Analyst",
                "required_skills": ["   ", ""],
            }
        )

    err = exc_info.value
    assert err.error_code == "E-DATA-001"
    assert "at least one required skill" in err.user_message.lower()


def test_deduplication_and_skill_collision() -> None:
    """UT-VAL-03: De-duplication (case-insensitive); collision between required and optional rejected."""
    # 1. Duplicates within required list are de-duplicated preserving first casing
    job = JobRequirements(
        job_title="Backend Developer",
        required_skills=["Python", "python", "PYTHON", "FastAPI"],
        optional_skills=["Docker"],
    )
    assert job.required_skills == ["Python", "FastAPI"]

    # 2. Skill appearing in both required and optional lists is detected and reported
    with pytest.raises(JobValidationError) as exc_info:
        JobRequirements.model_validate(
            {
                "job_title": "Backend Developer",
                "required_skills": ["Python", "SQL"],
                "optional_skills": ["python", "Docker"],
            }
        )

    err = exc_info.value
    assert "both required and optional" in err.user_message.lower()


def test_validation_messages_never_contain_resume_text() -> None:
    """UT-VAL-06: Validation messages are clean system diagnostics and never leak resume text."""
    try:
        JobRequirements.model_validate(
            {
                "job_title": "",
                "required_skills": [],
                "min_experience_years": -10,
            }
        )
    except JobValidationError as exc:
        msg = exc.user_message
        assert "resume" not in msg.lower()
        assert "candidate" not in msg.lower()
        assert exc.error_code == "E-DATA-001"
