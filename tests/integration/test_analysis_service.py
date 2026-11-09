"""Integration tests for AnalysisService (IT-01, IT-02, IT-03).

Verifies end-to-end analysis across sample resumes with deterministic core,
golden FakeProvider AI insights, and resilience to AI failures (FR-32).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from resume_analyzer.ai.ai_service import AIService
from resume_analyzer.ai.providers.fake import FakeProvider
from resume_analyzer.config.settings import get_settings
from resume_analyzer.exceptions import AIProviderUnavailableError
from resume_analyzer.models.enums import EducationLevel, FeatureStatus, Provenance
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService
from resume_analyzer.services.batch_runner import BatchRunner
from resume_analyzer.skills.skill_index import get_skill_index


@pytest.fixture
def sample_job() -> JobRequirements:
    """Standard test job requirement."""
    return JobRequirements(
        job_id="junior-data-analyst",
        job_title="Junior Data Analyst",
        required_skills=["Python", "SQL"],
        optional_skills=["Docker", "AWS", "Git"],
        min_experience_years=1.0,
        min_education_level=EducationLevel.BACHELOR,
    )


# -----------------------------------------------------------------------------
# IT-01: End-to-end deterministic analysis across sample resumes
# -----------------------------------------------------------------------------
def test_it_01_deterministic_analysis_sample_resumes(
    sample_job: JobRequirements,
    reference_date: date,
) -> None:
    """Assert deterministic analysis runs on sample resumes with both strategies (FR-15, IT-01).

    Ensures valid schemas, scores within [0, 100], and exact repeatability.
    """
    settings = get_settings()
    skill_index = get_skill_index("config/skills_taxonomy.json")
    service = AnalysisService(settings=settings, skill_index=skill_index)

    resume_dir = Path("tests/data/resumes")
    sample_resumes = sorted(list(resume_dir.glob("cand_*.txt")))
    assert len(sample_resumes) >= 10, "At least 10 sample resumes required for IT-01"

    for resume_path in sample_resumes[:5]:  # Test representative sample of resumes
        content = resume_path.read_bytes()

        # Run 1: Weighted Strategy
        opts_weighted = AnalysisOptions(strategy="weighted", ai_features=set())
        report_w1 = service.analyze(
            filename=resume_path.name,
            data=content,
            job=sample_job,
            options=opts_weighted,
            reference_date=reference_date,
        )

        assert isinstance(report_w1, AnalysisReport)
        assert 0.0 <= report_w1.score.total_score <= 100.0
        assert report_w1.score.strategy_name == "weighted"
        assert report_w1.candidate.candidate_id is not None
        assert report_w1.score.fit_band is not None

        # Repeatability check: second run must produce exact same score
        report_w2 = service.analyze(
            filename=resume_path.name,
            data=content,
            job=sample_job,
            options=opts_weighted,
            reference_date=reference_date,
        )
        assert report_w1.score.total_score == report_w2.score.total_score
        assert report_w1.match.required_credit == report_w2.match.required_credit

        # Run 2: Basic Strategy
        opts_basic = AnalysisOptions(strategy="basic", ai_features=set())
        report_b = service.analyze(
            filename=resume_path.name,
            data=content,
            job=sample_job,
            options=opts_basic,
            reference_date=reference_date,
        )
        assert isinstance(report_b, AnalysisReport)
        assert 0.0 <= report_b.score.total_score <= 100.0
        assert report_b.score.strategy_name == "basic"


# -----------------------------------------------------------------------------
# IT-02: End-to-end with FakeProvider returning golden P1-P5 outputs
# -----------------------------------------------------------------------------
def test_it_02_e2e_with_fake_provider(
    sample_job: JobRequirements,
    reference_date: date,
) -> None:
    """Assert end-to-end pipeline with FakeProvider successfully augments report with AI insights."""
    # Scripted golden responses for P1 through P5
    p1_response = (
        '{"schema_version": "1.0", "name": "Asha Verma", "email": "asha@example.com", '
        '"skills": [{"name": "Python", "mentions": 3}, {"name": "Pandas", "mentions": 1}], '
        '"experience": [], "education": []}'
    )
    p2_response = (
        '{"schema_version": "1.0", "categories": ['
        '{"skill": "Pandas", "category": "Libraries & Frameworks", "reasoning": "Data science library"}]}'
    )
    p3_response = (
        '{"schema_version": "1.0", "summary": "Good match for junior data analyst role.", '
        '"strengths": [{"point": "Has Python experience.", "evidence": ["fact_req_Python"]}], '
        '"concerns": [{"point": "Lacks SQL experience.", "evidence": ["fact_gap_SQL"]}], '
        '"suggested_review_focus": ["Review hands-on experience."], "limitations": []}'
    )
    p4_response = (
        '{"schema_version": "1.0", "recommendations": ['
        '{"gap_id": "gap_skill_SQL", "action": "Complete a course on SQL fundamentals.", '
        '"resource_type": "course", "priority": "high", "rationale": "Essential for database querying."}]}'
    )
    p5_response = (
        '{"schema_version": "1.0", "questions": ['
        '{"target_skill": "Python", "question": "Explain list comprehensions in Python and when to use them.", '
        '"category": "technical", "difficulty": "intermediate", "rationale": "Verify basic Python data structures.", '
        '"what_to_listen_for": ["Readability", "Performance"]}]}'
    )

    provider = FakeProvider(
        responses=[p1_response, p2_response, p3_response, p4_response, p5_response]
    )
    settings = get_settings()
    settings.ai.enabled = True
    settings.ai.features.recommendations = True
    settings.ai.features.interview_questions = True
    ai_service = AIService(settings=settings.ai, provider=provider)

    service = AnalysisService(settings=settings, ai_service=ai_service)
    resume_path = Path("tests/data/resumes/cand_01_asha_verma.txt")

    opts = AnalysisOptions(
        strategy="weighted",
        ai_features={
            "extraction",
            "categorization",
            "explanation",
            "recommendations",
            "interview_questions",
        },
    )
    report = service.analyze(
        filename=resume_path.name,
        data=resume_path.read_bytes(),
        job=sample_job,
        options=opts,
        reference_date=reference_date,
    )

    # Deterministic sections are intact and valid
    assert report.score.total_score > 0
    assert report.candidate.name == "Asha Verma"

    # AI sections are populated with OK status
    assert report.ai.explanation is not None
    assert report.ai.explanation.status == FeatureStatus.OK
    assert report.ai.explanation.provenance == Provenance.AI_GENERATED

    assert report.ai.recommendations is not None
    assert report.ai.recommendations.status == FeatureStatus.OK
    assert report.ai.interview_questions is not None
    assert report.ai.interview_questions.status == FeatureStatus.OK


# -----------------------------------------------------------------------------
# IT-03: AI failure matrix (FR-32)
# -----------------------------------------------------------------------------
def test_it_03_ai_failure_matrix(
    sample_job: JobRequirements,
    reference_date: date,
) -> None:
    """Assert AI provider errors never crash analysis; report is produced with UNAVAILABLE status."""
    failing_provider = FakeProvider(
        error=AIProviderUnavailableError(
            "Upstream timeout connecting to AI model", details={"provider": "fake"}
        )
    )
    settings = get_settings()
    settings.ai.enabled = True
    settings.ai.features.extraction = True
    settings.ai.features.categorization = True
    settings.ai.features.explanation = True
    settings.ai.features.recommendations = True
    settings.ai.features.interview_questions = True
    ai_service = AIService(settings=settings.ai, provider=failing_provider)

    service = AnalysisService(settings=settings, ai_service=ai_service)
    resume_path = Path("tests/data/resumes/cand_01_asha_verma.txt")

    opts = AnalysisOptions(
        strategy="weighted",
        ai_features={
            "extraction",
            "categorization",
            "explanation",
            "recommendations",
            "interview_questions",
        },
    )
    report = service.analyze(
        filename=resume_path.name,
        data=resume_path.read_bytes(),
        job=sample_job,
        options=opts,
        reference_date=reference_date,
    )

    # Core deterministic report is successfully generated!
    assert report.report_id is not None
    assert 0.0 <= report.score.total_score <= 100.0

    # AI sections show UNAVAILABLE
    assert report.ai.explanation is not None
    assert report.ai.explanation.status == FeatureStatus.UNAVAILABLE
    assert report.ai.recommendations is not None
    assert report.ai.recommendations.status == FeatureStatus.UNAVAILABLE

    # Flag AI_UNAVAILABLE is attached
    flag_codes = [f.code for f in report.flags]
    assert "AI_UNAVAILABLE" in flag_codes


def test_batch_runner_isolation_and_ranking(
    sample_job: JobRequirements,
    reference_date: date,
) -> None:
    """Assert BatchRunner processes files with error isolation and descending score ranking."""
    settings = get_settings()
    service = AnalysisService(settings=settings)
    runner = BatchRunner(analysis_service=service)

    cand1 = Path("tests/data/resumes/cand_01_asha_verma.txt").read_bytes()
    cand2 = Path("tests/data/resumes/cand_02_marcus_chen.txt").read_bytes()
    corrupt = b"Corrupt data that cannot be parsed as a valid document\x00\x01\x02"

    files = [
        ("asha.txt", cand1),
        ("corrupt.pdf", corrupt),
        ("marcus.txt", cand2),
    ]

    progress_calls: list[tuple[int, int, str]] = []

    def on_progress(done: int, total: int, current: str) -> None:
        progress_calls.append((done, total, current))

    batch_result = runner.run(files, sample_job, progress=on_progress)

    # Verify progress callback was invoked for all files
    assert len(progress_calls) == 3
    assert progress_calls[-1][0] == 3
    assert progress_calls[-1][1] == 3

    # Corrupt file was isolated into failures without aborting the batch
    assert len(batch_result.failures) == 1
    assert batch_result.failures[0].display_name == "corrupt.pdf"

    # Successful reports were sorted by score descending
    assert len(batch_result.reports) == 2
    assert (
        batch_result.reports[0].score.total_score
        >= batch_result.reports[1].score.total_score
    )
