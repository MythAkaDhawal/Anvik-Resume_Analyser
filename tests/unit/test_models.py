"""Unit tests for data models, enums, forbidden fields, and JSON serialization."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

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
    MatchResult,
    ReportFlag,
    ScoreComponent,
    ScoreResult,
    SkillMatch,
)


def test_candidate_forbidden_fields_absence() -> None:
    """Verify that demographic and proxy fields are deliberately absent from Candidate (NFR-14)."""
    forbidden_attributes = [
        "dob",
        "date_of_birth",
        "birth_date",
        "age",
        "gender",
        "sex",
        "marital_status",
        "nationality",
        "citizenship",
        "religion",
        "photo",
        "image",
        "street_address",
        "address",
        "phone",
        "phone_number",
        "telephone",
        "graduation_year",
        "social_media",
        "linkedin",
        "github",
    ]
    candidate_fields = Candidate.model_fields.keys()
    for attr in forbidden_attributes:
        assert attr not in candidate_fields, (
            f"Forbidden attribute '{attr}' found on Candidate model"
        )


def test_extra_forbid_on_models() -> None:
    """Verify extra='forbid' prevents extraneous arbitrary attributes."""
    with pytest.raises(ValidationError):
        Skill(name="Python", extra_field="forbidden")

    with pytest.raises(ValidationError):
        Candidate(
            candidate_id="0123456789ab",
            source_format="txt",
            parser_version="0.1.0",
            unauthorized_data="should_fail",
        )


def test_candidate_json_round_trip() -> None:
    """Verify Candidate model serialization and deserialization round-trip."""
    cand = Candidate(
        candidate_id="3fa91c0b77de",
        name="Asha Verma",
        email="asha@example.com",
        skills=[
            Skill(
                name="Python",
                canonical_name="Python",
                category="Languages",
                provenance=Provenance.EXTRACTED_RULE,
                mentions=3,
            ),
            Skill(
                name="PostgreSQL",
                canonical_name="PostgreSQL",
                category="Databases",
                provenance=Provenance.EXTRACTED_RULE,
                mentions=1,
            ),
        ],
        experience=[
            ExperienceEntry(
                job_title="Junior Analyst",
                company="Tech Corp",
                start=date(2023, 1, 1),
                end=date(2024, 6, 1),
                is_current=False,
                duration_months=17,
                provenance=Provenance.EXTRACTED_RULE,
            )
        ],
        education=[
            EducationEntry(
                degree="Bachelor of Science in Computer Science",
                level=EducationLevel.BACHELOR,
                field_of_study="Computer Science",
                institution="State University",
                provenance=Provenance.EXTRACTED_RULE,
            )
        ],
        total_experience_years=1.4,
        highest_education_level=EducationLevel.BACHELOR,
        source_format="txt",
        parse_warnings=[
            ParseWarning(code="TEST_WARN", message="Informational warning")
        ],
        injection_indicators=[],
        parser_version="0.1.0",
    )

    json_str = cand.model_dump_json()
    reloaded = Candidate.model_validate_json(json_str)

    assert reloaded.candidate_id == cand.candidate_id
    assert reloaded.name == cand.name
    assert len(reloaded.skills) == 2
    assert reloaded.skills[0].name == "Python"
    assert reloaded.highest_education_level == EducationLevel.BACHELOR
    assert reloaded.experience[0].duration_months == 17


def test_sample_jobs_json_loading() -> None:
    """Verify that all sample job JSON files load and validate into JobRequirements."""
    samples_dir = Path("samples/jobs")
    job_files = list(samples_dir.glob("*.json"))
    assert len(job_files) >= 3

    for job_file in job_files:
        content = job_file.read_text(encoding="utf-8")
        job = JobRequirements.model_validate_json(content)
        assert len(job.job_title) > 0
        assert len(job.required_skills) >= 1
        assert job.min_experience_years >= 0


def test_analysis_report_json_round_trip() -> None:
    """Verify complete AnalysisReport model serialization and deserialization."""
    cand = Candidate(
        candidate_id="3fa91c0b77de",
        name="Asha Verma",
        email="asha@example.com",
        source_format="pdf",
        parser_version="0.1.0",
    )
    job = JobRequirements(
        job_id="junior-data-analyst",
        job_title="Junior Data Analyst",
        required_skills=["Python", "SQL"],
        min_experience_years=2.0,
    )
    match_result = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Python",
                target_canonical="Python",
                is_required=True,
                matched_candidate_skill="Python",
                match_type=MatchType.EXACT,
                similarity=100.0,
                credit=1.0,
            ),
            SkillMatch(
                target="SQL",
                target_canonical="SQL",
                is_required=True,
                matched_candidate_skill=None,
                match_type=MatchType.NONE,
                similarity=0.0,
                credit=0.0,
            ),
        ],
        required_credit=0.5,
        optional_credit=None,
        experience=ExperienceAnalysis(
            required_years=2.0,
            candidate_years=1.0,
            status="partial",
            subscore=0.5,
            gap_years=1.0,
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.BACHELOR,
            candidate_level=EducationLevel.BACHELOR,
            status="met",
            subscore=1.0,
        ),
    )
    score_result = ScoreResult(
        strategy_name="weighted",
        total_score=65.0,
        components=[
            ScoreComponent(
                name="required_skills",
                status=ComponentStatus.EVALUATED,
                weight=0.5,
                subscore=0.5,
                points=25.0,
                explanation="1 of 2 required skills matched",
            )
        ],
        coverage=1.0,
        fit_band=FitBand.MODERATE,
        flags=["MISSING_REQUIRED_SKILLS"],
    )
    report = AnalysisReport(
        schema_version="1.0",
        report_id="20261107T120000Z_3fa91c0b_a1b2",
        created_at=datetime.now(UTC),
        app_version="0.1.0",
        config_snapshot={"strategy": "weighted", "weights": {"required_skills": 0.5}},
        candidate=cand,
        job=job,
        match=match_result,
        score=score_result,
        ai=AIInsights(),
        flags=[
            ReportFlag(
                code="MISSING_REQUIRED_SKILLS", message="Missing 1 required skill"
            )
        ],
    )

    json_str = report.model_dump_json()
    reloaded = AnalysisReport.model_validate_json(json_str)

    assert reloaded.report_id == "20261107T120000Z_3fa91c0b_a1b2"
    assert reloaded.score.total_score == 65.0
    assert reloaded.score.fit_band == FitBand.MODERATE
    assert reloaded.human_review_notice == DEFAULT_HUMAN_REVIEW_NOTICE
