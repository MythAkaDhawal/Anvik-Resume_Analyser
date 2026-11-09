"""Unit tests for job and candidate validation and parse-quality assessment (UT-VAL-01..06)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from resume_analyzer.config.settings import get_settings
from resume_analyzer.exceptions import DataValidationError, JobValidationError
from resume_analyzer.ingestion.file_loader import load_resume
from resume_analyzer.models.candidate import (
    Candidate,
    ExperienceEntry,
    Skill,
)
from resume_analyzer.models.enums import EducationLevel, Provenance
from resume_analyzer.parsing.resume_parser import ResumeParser
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import SkillTaxonomy
from resume_analyzer.validation.validators import (
    assess_parse_quality,
    validate_candidate,
    validate_job,
)

REF_DATE = date(2024, 6, 1)


def test_ut_val_01_valid_job_accepted_whitespace_trimmed():
    """UT-VAL-01: Valid job specification is accepted and all string fields are trimmed."""
    raw_job = {
        "job_title": "  Senior Backend Engineer   ",
        "description": "  Build scalable systems.  ",
        "required_skills": ["  Python  ", "PostgreSQL", " Docker "],
        "optional_skills": [" Kubernetes ", "AWS "],
        "min_experience_years": 4.0,
        "min_education_level": "BACHELOR",
        "preferred_fields": [" Computer Science "],
    }
    validated = validate_job(raw_job)
    assert validated.job_title == "Senior Backend Engineer"
    assert validated.description == "Build scalable systems."
    assert validated.required_skills == ["Python", "PostgreSQL", "Docker"]
    assert validated.optional_skills == ["Kubernetes", "AWS"]
    assert validated.preferred_fields == ["Computer Science"]
    assert validated.min_experience_years == 4.0
    assert validated.min_education_level == EducationLevel.BACHELOR


def test_ut_val_02_job_with_several_problems_single_aggregated_error():
    """UT-VAL-02: Job with multiple problems raises single JobValidationError listing all."""
    raw_job = {
        "job_title": "",  # Problem 1: empty title
        "required_skills": [],  # Problem 2: no required skills
        "min_experience_years": -5.0,  # Problem 3: negative years
        "optional_skills": [
            f"Skill_{i}" for i in range(60)
        ],  # Problem 4: >50 optional skills
    }
    with pytest.raises(JobValidationError) as exc_info:
        validate_job(raw_job)

    err = exc_info.value
    assert err.error_code == "E-DATA-001"
    details = err.details.get("errors", [])
    # Must list all distinct problems accumulated
    assert any("title" in msg.lower() for msg in details)
    assert any("required" in msg.lower() for msg in details)
    assert any("experience" in msg.lower() for msg in details)
    assert any("50" in msg for msg in details)
    assert len(details) >= 3


def test_ut_val_03_deduplication_and_cross_collision():
    """UT-VAL-03: Case-insensitive deduplication and collision detection between required and optional."""
    # Deduplication within required skills
    raw_job = {
        "job_title": "Software Engineer",
        "required_skills": ["Python", "python", "PYTHON", "FastAPI"],
        "optional_skills": ["Docker", "docker"],
    }
    job = validate_job(raw_job)
    assert job.required_skills == ["Python", "FastAPI"]
    assert job.optional_skills == ["Docker"]

    # Collision across required and optional skills
    colliding_job = {
        "job_title": "Software Engineer",
        "required_skills": ["Python", "PostgreSQL"],
        "optional_skills": ["Docker", "python"],  # 'python' collides with required
    }
    with pytest.raises(JobValidationError) as exc_info:
        validate_job(colliding_job)

    assert any(
        "appears in both required and optional" in msg
        for msg in exc_info.value.details.get("errors", [])
    )


def test_ut_val_04_candidate_sanity_checks():
    """UT-VAL-04: Candidate sanity checks (impossible dates raise E-DATA-002; bounds issue warnings)."""
    # Structurally impossible: invalid/empty candidate_id
    bad_candidate_0 = Candidate.model_construct(
        candidate_id="invalid_id",
        source_format="txt",
        parser_version="0.1.0",
    )
    with pytest.raises(DataValidationError) as exc_info_0:
        validate_candidate(bad_candidate_0, reference_date=REF_DATE)
    assert exc_info_0.value.error_code == "E-DATA-002"

    # Structurally impossible: negative total experience
    bad_candidate_1 = Candidate.model_construct(
        candidate_id="0123456789ab",
        source_format="txt",
        parser_version="0.1.0",
        total_experience_years=-2.5,
    )
    with pytest.raises(DataValidationError) as exc_info_1:
        validate_candidate(bad_candidate_1, reference_date=REF_DATE)
    assert exc_info_1.value.error_code == "E-DATA-002"

    # Structurally impossible: negative experience entry duration
    bad_candidate_2 = Candidate.model_construct(
        candidate_id="0123456789ab",
        source_format="txt",
        parser_version="0.1.0",
        experience=[
            ExperienceEntry.model_construct(
                job_title="Engineer",
                duration_months=-10,
                provenance=Provenance.EXTRACTED_RULE,
            )
        ],
    )
    with pytest.raises(DataValidationError) as exc_info_2:
        validate_candidate(bad_candidate_2, reference_date=REF_DATE)
    assert exc_info_2.value.error_code == "E-DATA-002"

    # Non-fatal sanity checks issuing warnings (future date, too long name, etc.)
    candidate_with_warnings = Candidate(
        candidate_id="0123456789ab",
        name="A" * 120,  # Name too long
        email="invalid-email-format",
        skills=[Skill(name=f"Skill_{i}") for i in range(350)],  # >300 skills
        experience=[
            ExperienceEntry(
                job_title="Future Engineer",
                start=date(2028, 1, 1),  # Future date
                provenance=Provenance.EXTRACTED_RULE,
            ),
            ExperienceEntry(
                job_title="Inverted Range",
                start=date(2022, 1, 1),
                end=date(2020, 1, 1),  # End precedes start
                provenance=Provenance.EXTRACTED_RULE,
            ),
        ],
        source_format="txt",
        parser_version="0.1.0",
    )
    warnings = validate_candidate(candidate_with_warnings, reference_date=REF_DATE)
    warn_codes = {w.code for w in warnings}
    assert "NAME_TOO_LONG" in warn_codes
    assert "INVALID_EMAIL" in warn_codes
    assert "SKILL_LIST_TRUNCATED" in warn_codes
    assert "FUTURE_DATE" in warn_codes
    assert "INVALID_DATE_RANGE" in warn_codes


def test_ut_val_05_assess_parse_quality_sparse_resume():
    """UT-VAL-05: assess_parse_quality emits appropriate warnings for sparse candidate fixture."""
    # Build parser and load sparse resume fixture
    settings = get_settings()
    tax = SkillTaxonomy.from_file("config/skills_taxonomy.json")
    index = SkillIndex(tax)
    parser = ResumeParser(index)

    sparse_path = Path("tests/data/resumes/cand_15_sparse_candidate.txt")
    loaded = load_resume(
        sparse_path.name, sparse_path.read_bytes(), settings=settings.files
    )
    candidate = parser.parse(loaded, reference_date=REF_DATE)

    quality_warnings = assess_parse_quality(candidate)
    quality_codes = {w.code for w in quality_warnings}

    # cand_15_sparse_candidate has no name, no email, no experience dates, and no education qualifications
    assert "NO_NAME" in quality_codes
    assert "NO_EMAIL" in quality_codes
    assert "NO_EXPERIENCE_DATES" in quality_codes
    assert "NO_EDUCATION" in quality_codes
    # Skills ARE present in sparse candidate, so NO_SKILLS should NOT be emitted
    assert "NO_SKILLS" not in quality_codes


def test_ut_val_06_validation_messages_never_echo_resume_content():
    """UT-VAL-06: Verification that validation warnings and messages never contain PII or resume text."""
    secret_candidate_text = (
        "Private Confidential Content John Secret 555-1234 secret@confidential.com"
    )
    candidate = Candidate(
        candidate_id="0123456789ab",
        name=secret_candidate_text,  # Excessively long name
        email="invalid-secret-email",
        source_format="txt",
        parser_version="0.1.0",
    )
    warnings = validate_candidate(candidate, reference_date=REF_DATE)
    quality_warnings = assess_parse_quality(candidate)

    all_warnings = warnings + quality_warnings
    for w in all_warnings:
        assert secret_candidate_text not in w.message
        assert "secret@confidential.com" not in w.message
        assert "555-1234" not in w.message
        assert "John Secret" not in w.message
