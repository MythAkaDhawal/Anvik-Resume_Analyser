"""Unit tests for BatchRunner and rate limiter (UT-BATCH-01..03).

Verifies per-file error isolation, progress tracking, ranking tie-breaking, and rate-limiting.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from resume_analyzer.ai.rate_limiter import AIRateLimiter
from resume_analyzer.config.settings import get_settings
from resume_analyzer.exceptions import AIRateLimitError
from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.services.analysis_service import AnalysisService
from resume_analyzer.services.batch_runner import BatchResult, BatchRunner
from resume_analyzer.skills.skill_index import get_skill_index


@pytest.fixture
def batch_job() -> JobRequirements:
    """Standard test job requirement."""
    return JobRequirements(
        title="Software Engineer",
        required_skills=["Python", "SQL"],
        optional_skills=["Docker", "AWS"],
        min_experience_years=2.0,
        education_level=EducationLevel.BACHELOR,
    )


@pytest.fixture
def batch_service() -> AnalysisService:
    """Configured AnalysisService instance with deterministic settings."""
    settings = get_settings()
    skill_index = get_skill_index("config/skills_taxonomy.json")
    return AnalysisService(settings=settings, skill_index=skill_index)


# -----------------------------------------------------------------------------
# UT-BATCH-01: Per-file failure isolation
# -----------------------------------------------------------------------------
def test_ut_batch_01_failure_isolation(
    batch_service: AnalysisService, batch_job: JobRequirements
) -> None:
    """Assert that a corrupt or empty file does not crash the batch and is recorded (FR-30, UT-BATCH-01)."""
    runner = BatchRunner(analysis_service=batch_service)

    valid_content = Path("tests/data/resumes/cand_01_asha_verma.txt").read_bytes()
    corrupt_content = b"%PDF-1.4 Corrupted unreadable PDF body"
    empty_content = b""

    files = [
        ("asha_verma.txt", valid_content),
        ("corrupt.pdf", corrupt_content),
        ("empty.txt", empty_content),
    ]

    result = runner.run(files, job=batch_job)

    assert isinstance(result, BatchResult)
    # Exactly 1 success, 2 failures
    assert len(result.reports) == 1
    assert len(result.failures) == 2

    # Verify failure record details
    failed_names = {f.display_name for f in result.failures}
    assert "corrupt.pdf" in failed_names
    assert "empty.txt" in failed_names

    for failure in result.failures:
        assert failure.error_code.startswith("E-")
        assert len(failure.user_message) > 0
        assert failure.display_name != ""


# -----------------------------------------------------------------------------
# UT-BATCH-02: Progress callback and stable ranking order
# -----------------------------------------------------------------------------
def test_ut_batch_02_progress_and_ranking(
    batch_service: AnalysisService, batch_job: JobRequirements
) -> None:
    """Assert progress callback invocation count, monotonicity, and stable ranking order (UT-BATCH-02)."""
    runner = BatchRunner(analysis_service=batch_service)

    c1 = Path("tests/data/resumes/cand_01_asha_verma.txt").read_bytes()
    c2 = Path("tests/data/resumes/cand_02_marcus_chen.txt").read_bytes()
    c3 = Path("tests/data/resumes/cand_03_sarah_connor.txt").read_bytes()

    files = [
        ("cand_01.txt", c1),
        ("cand_02.txt", c2),
        ("cand_03.txt", c3),
    ]

    progress_events: list[tuple[int, int, str]] = []

    def on_progress(done: int, total: int, filename: str) -> None:
        progress_events.append((done, total, filename))

    result = runner.run(files, job=batch_job, progress=on_progress)

    # 1. Progress events check
    assert len(progress_events) == 3
    assert [e[0] for e in progress_events] == [1, 2, 3]
    assert all(e[1] == 3 for e in progress_events)
    assert [e[2] for e in progress_events] == [
        "cand_01.txt",
        "cand_02.txt",
        "cand_03.txt",
    ]

    # 2. Ranking check (scores sorted descending)
    assert len(result.reports) == 3
    scores = [r.score.total_score for r in result.reports]
    assert scores == sorted(scores, reverse=True), (
        f"Reports not sorted by score descending: {scores}"
    )

    # 3. Tie-break stability check: equal scores sort by required_credit desc, then candidate_id asc
    for i in range(len(result.reports) - 1):
        r_curr = result.reports[i]
        r_next = result.reports[i + 1]
        if r_curr.score.total_score == r_next.score.total_score:
            assert r_curr.match.required_credit >= r_next.match.required_credit


# -----------------------------------------------------------------------------
# UT-BATCH-03: Rate limiter configuration and behavior
# -----------------------------------------------------------------------------
def test_ut_batch_03_rate_limiter_clock() -> None:
    """Assert rate limiter respects configured requests per minute and throws on limit (UT-BATCH-03)."""
    limiter = AIRateLimiter(requests_per_minute=2)

    # Mock time
    fake_time = 1000.0

    def mock_time() -> float:
        return fake_time

    with patch("time.time", side_effect=lambda: fake_time):
        # 1st and 2nd calls succeed immediately
        limiter.acquire(blocking=False)
        limiter.acquire(blocking=False)

        # 3rd call in the same window (without advancing time) must raise AIRateLimitError
        with pytest.raises(AIRateLimitError) as exc_info:
            limiter.acquire(blocking=False)
        assert exc_info.value.retry_after_s > 0

        # Advance fake time by 61 seconds: window slides, new call succeeds
        fake_time += 61.0
        limiter.acquire(blocking=False)
