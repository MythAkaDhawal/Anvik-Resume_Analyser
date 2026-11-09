"""Integration test for batch processing pipeline (IT-04).

Verifies mixed batch processing with valid resumes, corrupt files, encrypted PDFs,
empty files, and oversize payloads. Ensures strict failure isolation, ranking correctness,
and accurate progress callback tracking (FR-30).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resume_analyzer.config.settings import get_settings
from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService
from resume_analyzer.services.batch_runner import BatchRunner
from resume_analyzer.skills.skill_index import get_skill_index
from tests.data.generate_fixtures import create_encrypted_pdf


@pytest.fixture
def it04_job() -> JobRequirements:
    """Standard test job requirement for batch pipeline."""
    return JobRequirements(
        title="Full Stack Software Engineer",
        required_skills=["Python", "SQL", "Git"],
        optional_skills=["Docker", "AWS", "FastAPI"],
        min_experience_years=2.0,
        education_level=EducationLevel.BACHELOR,
    )


def test_it_04_mixed_files_batch_pipeline(it04_job: JobRequirements) -> None:
    """Run batch across valid, corrupt, encrypted, empty, and oversize files (IT-04)."""
    settings = get_settings()
    skill_index = get_skill_index("config/skills_taxonomy.json")
    service = AnalysisService(settings=settings, skill_index=skill_index)
    runner = BatchRunner(analysis_service=service)

    # 1. Valid resumes (PDF, DOCX, TXT)
    valid_pdf = Path("tests/data/resumes/valid_resume.pdf").read_bytes()
    valid_docx = Path("tests/data/resumes/valid_resume.docx").read_bytes()
    valid_txt = Path("tests/data/resumes/cand_01_asha_verma.txt").read_bytes()

    # 2. Problematic files
    encrypted_pdf = create_encrypted_pdf()
    corrupt_docx = b"PK\x03\x04" + b"Corrupted broken zip headers"
    empty_txt = b""
    oversize_txt = b"A" * (6 * 1024 * 1024)  # 6 MB > 5 MB limit (E-FILE-002)

    files = [
        ("valid_1.pdf", valid_pdf),
        ("encrypted_2.pdf", encrypted_pdf),
        ("valid_3.docx", valid_docx),
        ("corrupt_4.docx", corrupt_docx),
        ("valid_5.txt", valid_txt),
        ("empty_6.txt", empty_txt),
        ("oversize_7.txt", oversize_txt),
    ]

    progress_log: list[tuple[int, int, str]] = []

    def on_progress(done: int, total: int, fname: str) -> None:
        progress_log.append((done, total, fname))

    opts = AnalysisOptions(strategy="weighted", ai_enabled=False)
    batch_result = runner.run(files, job=it04_job, options=opts, progress=on_progress)

    # 1. Total progress calls must equal total files
    assert len(progress_log) == len(files)
    assert [p[0] for p in progress_log] == list(range(1, len(files) + 1))
    assert all(p[1] == len(files) for p in progress_log)

    # 2. Successful reports must include the 3 valid resumes
    assert len(batch_result.reports) == 3, (
        f"Expected 3 valid reports, got {len(batch_result.reports)}"
    )
    # Reports must be sorted descending by total score
    scores = [r.score.total_score for r in batch_result.reports]
    assert scores == sorted(scores, reverse=True)

    # 3. Failures must isolate the 4 invalid files
    assert len(batch_result.failures) == 4, (
        f"Expected 4 failures, got {len(batch_result.failures)}"
    )
    failed_filenames = {f.display_name for f in batch_result.failures}
    expected_failures = {
        "encrypted_2.pdf",
        "corrupt_4.docx",
        "empty_6.txt",
        "oversize_7.txt",
    }
    assert failed_filenames == expected_failures

    # Each failure must have a standardized error code and safe message
    for f in batch_result.failures:
        assert f.error_code.startswith("E-"), (
            f"Failure error code {f.error_code} does not start with E-"
        )
        assert f.user_message, f"Failure user_message is empty for {f.display_name}"
