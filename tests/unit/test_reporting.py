"""Unit tests for reporting engine and provenance tagging (UT-REP-01..05).

Verifies report assembly, provenance integrity, absence of verdict language,
AI unavailability handling, report flags, and JSON round-trip serialization.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from resume_analyzer.models.candidate import (
    Candidate,
    EducationEntry,
    ExperienceEntry,
    ParseWarning,
    Skill,
)
from resume_analyzer.models.enums import (
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
    ScoreComponent,
    ScoreResult,
    SkillMatch,
)
from resume_analyzer.reporting.provenance import (
    AI_UNVERIFIED_NOTICE,
    HUMAN_REVIEW_NOTICE,
    contains_verdict_language,
    get_badge_css_class,
    get_provenance_display,
    validate_no_verdict_language,
)
from resume_analyzer.reporting.report_builder import ReportBuilder


@pytest.fixture
def sample_candidate() -> Candidate:
    """Fixture providing a standard parsed candidate."""
    return Candidate(
        candidate_id="3fa91c0b77de",
        name="Asha Verma",
        email="asha@example.com",
        skills=[
            Skill(
                name="Python",
                canonical_name="Python",
                category="Programming Languages",
                provenance=Provenance.EXTRACTED_RULE,
                mentions=3,
            ),
            Skill(
                name="SQL",
                canonical_name="SQL",
                category="Databases",
                provenance=Provenance.EXTRACTED_RULE,
                mentions=2,
            ),
        ],
        experience=[
            ExperienceEntry(
                job_title="Junior Data Analyst",
                company="Acme Corp",
                duration_months=18,
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
        total_experience_years=1.5,
        highest_education_level=EducationLevel.BACHELOR,
        source_format="txt",
        parser_version="0.1.0",
    )


@pytest.fixture
def sample_job() -> JobRequirements:
    """Fixture providing a standard job specification."""
    return JobRequirements(
        job_id="junior-data-analyst",
        job_title="Junior Data Analyst",
        required_skills=["Python", "SQL", "Pandas"],
        optional_skills=["Docker"],
        min_experience_years=1.0,
        min_education_level=EducationLevel.BACHELOR,
    )


@pytest.fixture
def sample_match_result() -> MatchResult:
    """Fixture providing a deterministic match result."""
    return MatchResult(
        skill_matches=[
            SkillMatch(
                target="Python",
                is_required=True,
                match_type=MatchType.EXACT,
                matched_candidate_skill="Python",
                similarity=100.0,
                credit=1.0,
            ),
            SkillMatch(
                target="SQL",
                is_required=True,
                match_type=MatchType.EXACT,
                matched_candidate_skill="SQL",
                similarity=100.0,
                credit=1.0,
            ),
            SkillMatch(
                target="Pandas",
                is_required=True,
                match_type=MatchType.NONE,
                matched_candidate_skill=None,
                similarity=0.0,
                credit=0.0,
            ),
            SkillMatch(
                target="Docker",
                is_required=False,
                match_type=MatchType.NONE,
                matched_candidate_skill=None,
                similarity=0.0,
                credit=0.0,
            ),
        ],
        required_credit=0.6667,
        optional_credit=0.0,
        experience=ExperienceAnalysis(
            required_years=1.0,
            candidate_years=1.5,
            status="met",
            subscore=1.0,
            gap_years=0.0,
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.BACHELOR,
            candidate_level=EducationLevel.BACHELOR,
            status="met",
            field_match=None,
            subscore=1.0,
        ),
    )


@pytest.fixture
def sample_score_result() -> ScoreResult:
    """Fixture providing a deterministic score result."""
    return ScoreResult(
        strategy_name="weighted",
        total_score=78.5,
        components=[
            ScoreComponent(
                name="required_skills",
                status="evaluated",
                weight=0.50,
                subscore=0.6667,
                points=33.3,
                explanation="Required skills subscore 0.667 * weight 0.50 = 33.3 pts",
            ),
            ScoreComponent(
                name="experience",
                status="evaluated",
                weight=0.20,
                subscore=1.0,
                points=20.0,
                explanation="Experience subscore 1.0 * weight 0.20 = 20.0 pts",
            ),
            ScoreComponent(
                name="education",
                status="evaluated",
                weight=0.15,
                subscore=1.0,
                points=15.0,
                explanation="Education subscore 1.0 * weight 0.15 = 15.0 pts",
            ),
            ScoreComponent(
                name="optional_skills",
                status="evaluated",
                weight=0.15,
                subscore=0.0,
                points=0.0,
                explanation="Optional skills subscore 0.0 * weight 0.15 = 0.0 pts",
            ),
        ],
        coverage=1.0,
        fit_band=FitBand.MODERATE,
        flags=["MISSING_REQUIRED_SKILLS"],
    )


# -----------------------------------------------------------------------------
# UT-REP-01: Report contains all required sections
# -----------------------------------------------------------------------------
def test_ut_rep_01_all_required_sections(
    sample_candidate: Candidate,
    sample_job: JobRequirements,
    sample_match_result: MatchResult,
    sample_score_result: ScoreResult,
) -> None:
    """Assert report contains all required sections as per TECHNICAL_SPECIFICATION §11.1."""
    report = ReportBuilder.build(
        candidate=sample_candidate,
        job=sample_job,
        match=sample_match_result,
        score=sample_score_result,
    )

    # 0. Header metadata
    assert report.report_id is not None
    assert report.created_at is not None
    assert report.human_review_notice == DEFAULT_HUMAN_REVIEW_NOTICE

    # 1. Candidate information
    assert report.candidate.candidate_id == "3fa91c0b77de"
    assert report.candidate.name == "Asha Verma"
    assert report.candidate.email == "asha@example.com"
    assert len(report.candidate.skills) == 2

    # 2. Job information
    assert report.job.job_title == "Junior Data Analyst"
    assert "Python" in report.job.required_skills

    # 3. Overall match score
    assert report.score.total_score == 78.5
    assert report.score.fit_band == FitBand.MODERATE
    assert report.score.coverage == 1.0

    # 4. Score breakdown
    assert len(report.score.components) == 4

    # 5 & 6. Matched and missing skills
    matched = ReportBuilder.get_matched_skills(report)
    missing = ReportBuilder.get_missing_skills(report)
    assert len(matched) == 2
    assert len(missing) == 2
    # Missing required skills should come before optional
    assert missing[0].target == "Pandas" and missing[0].is_required

    # 7. Experience analysis
    assert report.match.experience.status == "met"
    assert report.match.experience.candidate_years == 1.5

    # 8. Education analysis
    assert report.match.education.status == "met"
    assert report.match.education.candidate_level == EducationLevel.BACHELOR

    # 9, 10, 11. AI Insights & Suitability
    assert report.ai is not None

    # Flags
    assert any(f.code == "MISSING_REQUIRED_SKILLS" for f in report.flags)


# -----------------------------------------------------------------------------
# UT-REP-02: Provenance tagging verification
# -----------------------------------------------------------------------------
def test_ut_rep_02_provenance_tagging(
    sample_candidate: Candidate,
    sample_job: JobRequirements,
    sample_match_result: MatchResult,
    sample_score_result: ScoreResult,
) -> None:
    """Assert each datum carries correct provenance and AI content is marked unverified."""
    # Add an AI-extracted skill to verify mixed provenance
    sample_candidate.skills.append(
        Skill(
            name="NumPy",
            canonical_name="NumPy",
            category="Libraries",
            provenance=Provenance.EXTRACTED_AI,
            mentions=1,
        )
    )

    ai_insights = AIInsights(
        interview_questions=FeatureResult(
            feature="interview_questions",
            status=FeatureStatus.OK,
            data=[{"question": "How do you use SQL indexing?", "target_skill": "SQL"}],
            provenance=Provenance.AI_GENERATED,
        )
    )

    report = ReportBuilder.build(
        candidate=sample_candidate,
        job=sample_job,
        match=sample_match_result,
        score=sample_score_result,
        ai=ai_insights,
    )

    # Check skill provenances
    rule_skills = [
        s for s in report.candidate.skills if s.provenance == Provenance.EXTRACTED_RULE
    ]
    ai_skills = [
        s for s in report.candidate.skills if s.provenance == Provenance.EXTRACTED_AI
    ]
    assert len(rule_skills) == 2
    assert len(ai_skills) == 1

    # Check match and score provenances are COMPUTED
    assert report.score.provenance == Provenance.COMPUTED
    assert report.match.experience.provenance == Provenance.COMPUTED
    assert report.match.education.provenance == Provenance.COMPUTED

    # Check AI insights provenance
    assert report.ai.interview_questions is not None
    assert report.ai.interview_questions.provenance == Provenance.AI_GENERATED

    # Check display labels
    assert get_provenance_display(Provenance.AI_GENERATED) == AI_UNVERIFIED_NOTICE
    assert "not verified" in AI_UNVERIFIED_NOTICE.lower()
    assert get_badge_css_class(Provenance.AI_GENERATED) == "badge-ai-generated"
    assert get_badge_css_class(Provenance.COMPUTED) == "badge-computed"


# -----------------------------------------------------------------------------
# UT-REP-03: Human review notice and no verdict language
# -----------------------------------------------------------------------------
def test_ut_rep_03_human_review_notice_and_no_verdict_language(
    sample_candidate: Candidate,
    sample_job: JobRequirements,
    sample_match_result: MatchResult,
    sample_score_result: ScoreResult,
) -> None:
    """Assert human-review notice is present verbatim and no verdict language exists."""
    report = ReportBuilder.build(
        candidate=sample_candidate,
        job=sample_job,
        match=sample_match_result,
        score=sample_score_result,
    )

    # Human review notice exact wording
    expected_notice = (
        "This report supports, and does not replace, human judgement. "
        "Scores reflect alignment between stated requirements and information extracted from the resume. "
        "AI-generated sections are interpretations that have not been verified. "
        "Do not use this report as the sole basis for any employment decision."
    )
    assert report.human_review_notice == expected_notice
    assert report.human_review_notice == HUMAN_REVIEW_NOTICE

    # Dump to JSON string and verify absence of employment verdicts
    report_json = report.model_dump_json()

    # Verdict checker validator
    assert not contains_verdict_language("Strong candidate with good Python skills")
    assert contains_verdict_language("Recommend we hire this person immediately")
    assert contains_verdict_language("Reject candidate due to low score")

    # Full report text must not contain automated verdicts
    validate_no_verdict_language(
        report_json, context="AnalysisReport JSON serialization"
    )


# -----------------------------------------------------------------------------
# UT-REP-04: AI unavailable handling
# -----------------------------------------------------------------------------
def test_ut_rep_04_ai_unavailable_handling(
    sample_candidate: Candidate,
    sample_job: JobRequirements,
    sample_match_result: MatchResult,
    sample_score_result: ScoreResult,
) -> None:
    """Assert AI unavailable yields UNAVAILABLE status, AI_UNAVAILABLE flag, unaffected score."""
    ai_insights = AIInsights(
        explanation=FeatureResult(
            feature="explanation",
            status=FeatureStatus.UNAVAILABLE,
            error_code="E-AI-002",
        ),
        recommendations=FeatureResult(
            feature="recommendations",
            status=FeatureStatus.UNAVAILABLE,
            error_code="E-AI-002",
        ),
    )

    report = ReportBuilder.build(
        candidate=sample_candidate,
        job=sample_job,
        match=sample_match_result,
        score=sample_score_result,
        ai=ai_insights,
    )

    # Deterministic sections remain completely valid and untouched
    assert report.score.total_score == 78.5
    assert report.score.fit_band == FitBand.MODERATE
    assert report.match.required_credit == 0.6667

    # AI sections hold UNAVAILABLE status
    assert report.ai.explanation is not None
    assert report.ai.explanation.status == FeatureStatus.UNAVAILABLE
    assert report.ai.recommendations is not None
    assert report.ai.recommendations.status == FeatureStatus.UNAVAILABLE

    # Report flags include AI_UNAVAILABLE
    flag_codes = [f.code for f in report.flags]
    assert "AI_UNAVAILABLE" in flag_codes


# -----------------------------------------------------------------------------
# UT-REP-05: AnalysisReport JSON round-trip equality & report_id format
# -----------------------------------------------------------------------------
def test_ut_rep_05_json_roundtrip_and_report_id(
    sample_candidate: Candidate,
    sample_job: JobRequirements,
    sample_match_result: MatchResult,
    sample_score_result: ScoreResult,
) -> None:
    """Assert AnalysisReport passes JSON round-trip serialization and matches report_id format."""
    report = ReportBuilder.build(
        candidate=sample_candidate,
        job=sample_job,
        match=sample_match_result,
        score=sample_score_result,
        created_at=datetime(2026, 11, 8, 10, 15, 0, tzinfo=UTC),
    )

    # Check report_id format: ^\d{8}T\d{6}Z_[0-9a-f]{8}_[0-9a-f]{4}$
    id_pattern = re.compile(r"^\d{8}T\d{6}Z_[0-9a-f]{8}_[0-9a-f]{4}$")
    assert id_pattern.match(report.report_id) is not None
    assert report.report_id.startswith("20261108T101500Z_3fa91c0b_")

    # Serialize to JSON and deserialize back
    json_bytes = report.model_dump_json(indent=2)
    deserialized = AnalysisReport.model_validate_json(json_bytes)

    assert deserialized.report_id == report.report_id
    assert deserialized.candidate.candidate_id == report.candidate.candidate_id
    assert deserialized.score.total_score == report.score.total_score
    assert deserialized.score.fit_band == report.score.fit_band
    assert deserialized.flags == report.flags
    assert deserialized.human_review_notice == report.human_review_notice
    assert deserialized.config_snapshot == report.config_snapshot


def test_report_builder_injection_and_quality_flags(
    sample_candidate: Candidate,
    sample_job: JobRequirements,
    sample_match_result: MatchResult,
    sample_score_result: ScoreResult,
) -> None:
    """Assert report builder accurately converts injection and parser warnings into flags."""
    sample_candidate.injection_indicators = [
        "IGNORE_INSTRUCTIONS",
        "SCORE_MANIPULATION",
    ]
    sample_candidate.parse_warnings.append(
        ParseWarning(code="LOW_TEXT_QUALITY", message="Garbled characters detected")
    )

    report = ReportBuilder.build(
        candidate=sample_candidate,
        job=sample_job,
        match=sample_match_result,
        score=sample_score_result,
    )

    flag_codes = {f.code for f in report.flags}
    assert "INJECTION_INDICATORS" in flag_codes
    assert "LOW_PARSE_QUALITY" in flag_codes
    assert "MISSING_REQUIRED_SKILLS" in flag_codes
