"""Unit tests for storage, atomic persistence, path traversal defense, and purging (Phase 12, FR-27, FR-28, NFR-19).

Tests UT-STORE-01 through UT-STORE-08 per TESTING_STRATEGY §5.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from resume_analyzer.exceptions import (
    CorruptResultError,
    InvalidIdentifierError,
    ResultNotFoundError,
    StorageError,
)
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
from resume_analyzer.storage.paths import safe_join, validate_report_id
from resume_analyzer.storage.result_store import ResultStore


@pytest.fixture
def make_report():
    """Factory fixture for creating sample AnalysisReport instances with distinct parameters."""

    def _factory(
        cand_id: str = "3fa91c0b77de",
        name: str = "Asha Verma",
        created_at: datetime | None = None,
        total_score: float = 85.0,
    ) -> AnalysisReport:
        dt = created_at or datetime(2026, 11, 8, 12, 0, 0, tzinfo=UTC)
        cand = Candidate(
            candidate_id=cand_id,
            name=name,
            email=f"{name.lower().replace(' ', '.')}@example.com",
            skills=[
                Skill(
                    name="Python",
                    canonical_name="Python",
                    provenance=Provenance.EXTRACTED_RULE,
                    mentions=2,
                ),
                Skill(
                    name="SQL",
                    canonical_name="SQL",
                    provenance=Provenance.EXTRACTED_RULE,
                    mentions=1,
                ),
            ],
            experience=[
                ExperienceEntry(
                    job_title="Software Developer",
                    duration_months=24,
                    provenance=Provenance.EXTRACTED_RULE,
                )
            ],
            education=[
                EducationEntry(
                    degree="BS Computer Science",
                    level=EducationLevel.BACHELOR,
                    provenance=Provenance.EXTRACTED_RULE,
                )
            ],
            total_experience_years=2.0,
            highest_education_level=EducationLevel.BACHELOR,
            source_format="txt",
            parser_version="1.0.0",
        )
        job = JobRequirements(
            job_title="Software Engineer",
            required_skills=["Python", "SQL"],
            min_experience_years=2.0,
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
                ),
                SkillMatch(
                    target="SQL",
                    is_required=True,
                    match_type=MatchType.EXACT,
                    matched_candidate_skill="SQL",
                    similarity=100.0,
                    credit=1.0,
                ),
            ],
            required_credit=1.0,
            experience=ExperienceAnalysis(
                required_years=2.0,
                candidate_years=2.0,
                status="met",
                subscore=1.0,
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
            total_score=total_score,
            components=[
                ScoreComponent(
                    name="required_skills",
                    status="evaluated",
                    weight=0.5,
                    subscore=1.0,
                    points=50.0,
                    explanation="All skills met",
                ),
                ScoreComponent(
                    name="experience",
                    status="evaluated",
                    weight=0.3,
                    subscore=1.0,
                    points=30.0,
                    explanation="Experience met",
                ),
            ],
            coverage=1.0,
            fit_band=FitBand.STRONG if total_score >= 80 else FitBand.MODERATE,
            flags=[],
        )
        return ReportBuilder.build(
            candidate=cand,
            job=job,
            match=match,
            score=score,
            created_at=dt,
        )

    return _factory


# -----------------------------------------------------------------------------
# UT-STORE-01: Save -> load round trip equality
# -----------------------------------------------------------------------------
def test_ut_store_01_save_load_equality(tmp_path: Path, make_report) -> None:
    """Assert saved report reloads with exact model equivalence (FR-27)."""
    store = ResultStore(base_dir=tmp_path)
    report = make_report()

    saved_path = store.save(report)
    assert saved_path.is_file()
    assert saved_path.suffix == ".json"

    loaded = store.load(report.report_id)
    assert loaded.report_id == report.report_id
    assert loaded.candidate.name == report.candidate.name
    assert loaded.candidate.email == report.candidate.email
    assert loaded.score.total_score == report.score.total_score
    assert loaded.score.fit_band == report.score.fit_band
    assert loaded.model_dump() == report.model_dump()


# -----------------------------------------------------------------------------
# UT-STORE-02: Atomic write resilience: simulated failure leaves target intact
# -----------------------------------------------------------------------------
def test_ut_store_02_atomic_write_failure_resilience(
    tmp_path: Path, make_report
) -> None:
    """Assert interrupted write never corrupts existing record and leaves no .tmp residue (FR-27)."""
    store = ResultStore(base_dir=tmp_path)
    original_report = make_report(total_score=80.0)
    store.save(original_report)

    # Verify initial save succeeded and no temp files exist
    assert len(list(tmp_path.glob("*.tmp"))) == 0

    # Simulate crash/failure during atomic replace of updated report
    updated_report = make_report(total_score=95.0)
    # Monkeypatch os.replace to simulate an abrupt failure
    with patch(
        "os.replace", side_effect=OSError("Disk write error during atomic move")
    ):
        with pytest.raises(StorageError) as exc_info:
            store.save(updated_report)

        assert "Disk write error" in str(exc_info.value)
        assert exc_info.value.user_message == "Could not write the result."

    # Verify no orphaned .tmp files remain
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0

    # Verify existing saved file was untouched and remains valid with original data
    reloaded = store.load(original_report.report_id)
    assert reloaded.score.total_score == 80.0


# -----------------------------------------------------------------------------
# UT-STORE-03: Corrupt/partial JSON handling
# -----------------------------------------------------------------------------
def test_ut_store_03_corrupt_partial_json_handling(tmp_path: Path, make_report) -> None:
    """Assert corrupt or truncated JSON raises CorruptResultError and listing isolates it (FR-28)."""
    store = ResultStore(base_dir=tmp_path)

    # 1. Valid report
    valid_report = make_report(cand_id="aaaaaaaaaaaa", name="Valid Candidate")
    store.save(valid_report)

    # 2. Corrupt partial JSON file with a valid report_id filename
    corrupt_id = "20261108T120000Z_bbbbbbbb_cccc"
    corrupt_file = tmp_path / f"{corrupt_id}.json"
    corrupt_file.write_text(
        '{"report_id": "' + corrupt_id + '", "candidate": {"name": "Broken", ',
        encoding="utf-8",
    )

    # Direct load must raise CorruptResultError
    with pytest.raises(CorruptResultError) as exc_info:
        store.load(corrupt_id)
    assert "malformed JSON" in str(exc_info.value)

    # Listing must NOT crash; must list the corrupt file with readable=False
    summaries = store.list()
    assert len(summaries) == 2

    valid_sum = next(s for s in summaries if s.report_id == valid_report.report_id)
    assert valid_sum.readable is True
    assert valid_sum.candidate_name == "Valid Candidate"

    corrupt_sum = next(s for s in summaries if s.report_id == corrupt_id)
    assert corrupt_sum.readable is False
    assert corrupt_sum.candidate_name == "Unreadable"


# -----------------------------------------------------------------------------
# UT-STORE-04: Path traversal and invalid identifiers defense
# -----------------------------------------------------------------------------
def test_ut_store_04_invalid_identifiers_and_path_traversal(tmp_path: Path) -> None:
    """Assert path traversal attempts and invalid IDs raise InvalidIdentifierError (NFR-05)."""
    store = ResultStore(base_dir=tmp_path)

    # Test validate_report_id
    invalid_ids = [
        "../etc/passwd",
        "..\\windows\\system32",
        "invalid_id",
        "20261108T120000Z_invalid",
        "20261108T120000Z_12345678_12345",  # 5 hex instead of 4
        "",
        "   ",
        "/absolute/path",
        "C:\\Windows\\cmd.exe",
    ]
    for bad_id in invalid_ids:
        with pytest.raises(InvalidIdentifierError):
            validate_report_id(bad_id)

        with pytest.raises(InvalidIdentifierError):
            store.load(bad_id)

        with pytest.raises(InvalidIdentifierError):
            store.delete(bad_id)

    # Test safe_join boundary confinement
    with pytest.raises(InvalidIdentifierError):
        safe_join(tmp_path, "../outside.json")

    with pytest.raises(InvalidIdentifierError):
        safe_join(tmp_path, "sub/dir.json")

    with pytest.raises(InvalidIdentifierError):
        safe_join(tmp_path, "/etc/shadow")

    # Valid name stays inside tmp_path
    safe_path = safe_join(tmp_path, "report_123.json")
    assert safe_path.parent == tmp_path.resolve()


# -----------------------------------------------------------------------------
# UT-STORE-05: Incompatible schema_version handling
# -----------------------------------------------------------------------------
def test_ut_store_05_incompatible_schema_version(tmp_path: Path, make_report) -> None:
    """Assert reports with incompatible schema_version raise CorruptResultError (FR-27)."""
    store = ResultStore(base_dir=tmp_path)
    report = make_report()
    saved_path = store.save(report)

    # Overwrite file with schema_version '2.0'
    raw_data = json.loads(saved_path.read_text(encoding="utf-8"))
    raw_data["schema_version"] = "2.0"
    saved_path.write_text(json.dumps(raw_data), encoding="utf-8")

    with pytest.raises(CorruptResultError) as exc_info:
        store.load(report.report_id)

    assert "Incompatible report schema_version '2.0'" in str(exc_info.value)
    assert exc_info.value.details.get("schema_version") == "2.0"


# -----------------------------------------------------------------------------
# UT-STORE-06: Listing order newest-first and complete
# -----------------------------------------------------------------------------
def test_ut_store_06_listing_order_newest_first(tmp_path: Path, make_report) -> None:
    """Assert store.list() orders results by created_at descending (FR-28)."""
    store = ResultStore(base_dir=tmp_path)

    # Create 3 reports with distinct creation dates
    dt1 = datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)
    dt2 = datetime(2026, 11, 8, 15, 30, 0, tzinfo=UTC)
    dt3 = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    r1 = make_report(cand_id="111111111111", name="Nov 1 Candidate", created_at=dt1)
    r2 = make_report(cand_id="222222222222", name="Nov 8 Candidate", created_at=dt2)
    r3 = make_report(cand_id="333333333333", name="Nov 5 Candidate", created_at=dt3)

    store.save(r1)
    store.save(r2)
    store.save(r3)

    summaries = store.list()
    assert len(summaries) == 3

    # Expected order: r2 (Nov 8), r3 (Nov 5), r1 (Nov 1)
    assert summaries[0].report_id == r2.report_id
    assert summaries[0].candidate_name == "Nov 8 Candidate"
    assert summaries[1].report_id == r3.report_id
    assert summaries[1].candidate_name == "Nov 5 Candidate"
    assert summaries[2].report_id == r1.report_id
    assert summaries[2].candidate_name == "Nov 1 Candidate"


# -----------------------------------------------------------------------------
# UT-STORE-07: Purge older than and single report deletion
# -----------------------------------------------------------------------------
def test_ut_store_07_purge_older_than_and_delete(tmp_path: Path, make_report) -> None:
    """Assert purge_older_than deletes only expired records and delete() removes single item (FR-28, NFR-19)."""
    store = ResultStore(base_dir=tmp_path)

    now = datetime.now(UTC)
    old_dt = now - timedelta(days=45)
    recent_dt = now - timedelta(days=5)

    old_report = make_report(
        cand_id="aaaaaaaaaaaa", name="Old Candidate", created_at=old_dt
    )
    recent_report = make_report(
        cand_id="bbbbbbbbbbbb", name="Recent Candidate", created_at=recent_dt
    )

    store.save(old_report)
    store.save(recent_report)

    assert len(store.list()) == 2

    # Purge records older than 30 days
    purged_count = store.purge_older_than(days=30)
    assert purged_count == 1

    # Only recent report remains
    remaining = store.list()
    assert len(remaining) == 1
    assert remaining[0].report_id == recent_report.report_id

    # Old report must raise ResultNotFoundError
    with pytest.raises(ResultNotFoundError):
        store.load(old_report.report_id)

    # Delete the recent report individually
    store.delete(recent_report.report_id)
    assert len(store.list()) == 0

    # Second delete raises ResultNotFoundError
    with pytest.raises(ResultNotFoundError):
        store.delete(recent_report.report_id)


# -----------------------------------------------------------------------------
# UT-STORE-08: Storage permission and write error mapping
# -----------------------------------------------------------------------------
def test_ut_store_08_permission_error_mapping(tmp_path: Path, make_report) -> None:
    """Assert write or filesystem permission failure maps to StorageError with safe user message (NFR-06)."""
    store = ResultStore(base_dir=tmp_path)
    report = make_report()

    # Simulate filesystem permission failure on temp file creation
    with patch(
        "pathlib.Path.write_text",
        side_effect=PermissionError("EACCES: permission denied"),
    ):
        with pytest.raises(StorageError) as exc_info:
            store.save(report)

        err = exc_info.value
        assert err.error_code == "E-STORE-001"
        assert err.user_message == "Could not write the result."
        assert "EACCES: permission denied" in str(err)


def test_ut_store_edge_cases(tmp_path: Path, make_report) -> None:
    """Test store edge cases: negative purge days, delete_all, unparseable date."""
    store = ResultStore(base_dir=tmp_path)

    # Negative purge days returns 0
    assert store.purge_older_than(-1) == 0

    # delete_all on multiple reports
    r1 = make_report(cand_id="111111111111")
    r2 = make_report(cand_id="222222222222")
    store.save(r1)
    store.save(r2)
    assert len(store.list()) == 2

    count = store.delete_all()
    assert count == 2
    assert len(store.list()) == 0

    # Non-dict JSON file handling in load
    bad_root_id = "20261108T120000Z_99999999_9999"
    bad_root_file = tmp_path / f"{bad_root_id}.json"
    bad_root_file.write_text('["not an object"]', encoding="utf-8")
    with pytest.raises(CorruptResultError) as exc:
        store.load(bad_root_id)
    assert "root must be an object" in str(exc.value)
