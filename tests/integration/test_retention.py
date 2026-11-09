"""Integration test for data retention, purging, and feedback file isolation (IT-08, NFR-19)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from resume_analyzer.models.candidate import (
    Candidate,
    EducationEntry,
    ExperienceEntry,
    Skill,
)
from resume_analyzer.models.enums import EducationLevel, FitBand, MatchType, Provenance
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import (
    AnalysisReport,
    EducationAnalysis,
    ExperienceAnalysis,
    MatchResult,
    ScoreComponent,
    ScoreResult,
    SkillMatch,
)
from resume_analyzer.reporting.report_builder import ReportBuilder
from resume_analyzer.storage.feedback_store import FeedbackRecord, FeedbackStore
from resume_analyzer.storage.result_store import ResultStore


def _build_dummy_report(
    cand_id: str, name: str, created_at: datetime
) -> AnalysisReport:
    """Helper to assemble a minimal valid AnalysisReport."""
    cand = Candidate(
        candidate_id=cand_id,
        name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        skills=[
            Skill(
                name="Python",
                canonical_name="Python",
                provenance=Provenance.EXTRACTED_RULE,
                mentions=1,
            )
        ],
        experience=[
            ExperienceEntry(
                job_title="Engineer",
                duration_months=12,
                provenance=Provenance.EXTRACTED_RULE,
            )
        ],
        education=[
            EducationEntry(
                degree="BS CS",
                level=EducationLevel.BACHELOR,
                provenance=Provenance.EXTRACTED_RULE,
            )
        ],
        total_experience_years=1.0,
        highest_education_level=EducationLevel.BACHELOR,
        source_format="txt",
        parser_version="1.0.0",
    )
    job = JobRequirements(
        job_title="Engineer",
        required_skills=["Python"],
        min_experience_years=1.0,
        min_education_level=EducationLevel.BACHELOR,
    )
    match = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Python",
                is_required=True,
                match_type=MatchType.EXACT,
                matched_candidate_skill="Python",
                similarity=100.0,
                credit=1.0,
            )
        ],
        required_credit=1.0,
        experience=ExperienceAnalysis(
            required_years=1.0, candidate_years=1.0, status="met", subscore=1.0
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.BACHELOR,
            candidate_level=EducationLevel.BACHELOR,
            status="met",
            subscore=1.0,
        ),
    )
    score = ScoreResult(
        strategy_name="weighted",
        total_score=80.0,
        components=[
            ScoreComponent(
                name="required_skills",
                status="evaluated",
                weight=1.0,
                subscore=1.0,
                points=80.0,
                explanation="All required skills matched",
            )
        ],
        coverage=1.0,
        fit_band=FitBand.STRONG,
        flags=[],
    )
    return ReportBuilder.build(
        candidate=cand, job=job, match=match, score=score, created_at=created_at
    )


def test_it_08_retention_purge_and_feedback_isolation(tmp_path: Path) -> None:
    """Assert retention purge deletes back-dated reports and leaves feedback completely untouched (IT-08, NFR-19)."""
    results_dir = tmp_path / "results"
    feedback_file = tmp_path / "feedback.jsonl"
    results_dir.mkdir(parents=True, exist_ok=True)

    result_store = ResultStore(base_dir=results_dir)
    feedback_store = FeedbackStore(feedback_path=feedback_file)

    now = datetime.now(UTC)
    dt_old1 = now - timedelta(days=60)
    dt_old2 = now - timedelta(days=45)
    dt_recent = now - timedelta(days=2)

    # 1. Create and save 3 reports
    rep_old1 = _build_dummy_report("111111111111", "Candidate 60d", dt_old1)
    rep_old2 = _build_dummy_report("222222222222", "Candidate 45d", dt_old2)
    rep_recent = _build_dummy_report("333333333333", "Candidate 2d", dt_recent)

    result_store.save(rep_old1)
    result_store.save(rep_old2)
    result_store.save(rep_recent)

    assert len(result_store.list()) == 3

    # 2. Append feedback records for candidate reports
    fb1 = FeedbackRecord(
        report_id=rep_old1.report_id,
        rating=5,
        comment="Old report feedback",
        section_feedback={"skills": True},
    )
    fb2 = FeedbackRecord(
        report_id=rep_recent.report_id,
        rating=4,
        comment="Recent report feedback",
        section_feedback={"skills": True},
    )
    feedback_store.append(fb1)
    feedback_store.append(fb2)

    assert feedback_file.is_file()
    assert feedback_store.summarize().total_submissions == 2

    # 3. Execute retention purge for reports older than 30 days
    purged_count = result_store.purge_older_than(days=30)
    assert purged_count == 2

    # 4. Verify only the recent report remains in result store
    active_summaries = result_store.list()
    assert len(active_summaries) == 1
    assert active_summaries[0].report_id == rep_recent.report_id

    # 5. Verify feedback store file is completely untouched
    assert feedback_file.is_file()
    feedback_summary = feedback_store.summarize()
    assert feedback_summary.total_submissions == 2
    assert feedback_summary.average_rating == 4.5
    records = feedback_store.list_records()
    assert len(records) == 2
    assert records[0].report_id == rep_old1.report_id
    assert records[1].report_id == rep_recent.report_id
