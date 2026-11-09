"""Unit tests for the command-line interface (cli.py).

Verifies command dispatch, argument validation, exit codes (0, 1, 2, 3),
and analyze, batch, benchmark subcommands.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resume_analyzer import cli
from resume_analyzer.models.job import JobRequirements


@pytest.fixture
def cli_job_file(tmp_path: Path) -> Path:
    """Create a temporary job requirements JSON file."""
    job_data = {
        "job_title": "Backend Software Engineer",
        "required_skills": ["Python", "SQL"],
        "optional_skills": ["Docker", "AWS"],
        "min_experience_years": 2.0,
        "min_education_level": "BACHELOR",
    }
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps(job_data), encoding="utf-8")
    return job_file


def test_cli_load_job_file(cli_job_file: Path) -> None:
    """Verify loading job from JSON/YAML file."""
    job = cli.load_job_file(cli_job_file)
    assert isinstance(job, JobRequirements)
    assert job.job_title == "Backend Software Engineer"


def test_cli_load_job_file_not_found(tmp_path: Path) -> None:
    """Verify loading nonexistent job file raises error."""
    with pytest.raises(cli.DataValidationError):
        cli.load_job_file(tmp_path / "nonexistent_job.json")


def test_cli_analyze_success(
    cli_job_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify analyze command executes and returns exit code 0."""
    valid_resume = Path("tests/data/resumes/cand_01_asha_verma.txt")
    out_dir = tmp_path / "reports"

    argv = [
        "analyze",
        "--resume",
        str(valid_resume),
        "--job",
        str(cli_job_file),
        "--strategy",
        "weighted",
        "--ai",
        "off",
        "--format",
        "html",
        "--output-dir",
        str(out_dir),
    ]

    exit_code = cli.main(argv)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "RESUME ANALYSIS SUMMARY" in captured.out
    assert "Overall Score" in captured.out
    assert any(f.name.endswith(".html") for f in out_dir.glob("*.html"))


def test_cli_analyze_missing_resume(cli_job_file: Path, tmp_path: Path) -> None:
    """Verify analyze with missing resume file returns exit code 2."""
    argv = [
        "analyze",
        "--resume",
        str(tmp_path / "missing_resume.pdf"),
        "--job",
        str(cli_job_file),
    ]
    exit_code = cli.main(argv)
    assert exit_code == 2


def test_cli_batch_command(
    cli_job_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify batch command processes directory and outputs rankings."""
    # Create directory with 1 valid and 1 empty resume
    batch_dir = tmp_path / "resumes"
    batch_dir.mkdir()
    valid_src = Path("tests/data/resumes/cand_01_asha_verma.txt").read_bytes()
    (batch_dir / "valid.txt").write_bytes(valid_src)
    (batch_dir / "empty.txt").write_bytes(b"")

    out_dir = tmp_path / "exports"

    argv = [
        "batch",
        "--resumes-dir",
        str(batch_dir),
        "--job",
        str(cli_job_file),
        "--output-dir",
        str(out_dir),
        "--format",
        "xlsx",
    ]

    exit_code = cli.main(argv)
    # Exit code 1 because 1 file failed in batch
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "BATCH FAILURES" in captured.out
    assert "CANDIDATE RANKINGS" in captured.out
    assert (out_dir / "batch_ranking_summary.xlsx").is_file()


def test_cli_benchmark_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify benchmark command measures deterministic pipeline throughput."""
    bench_dir = tmp_path / "bench_resumes"
    bench_dir.mkdir()
    sample = Path("tests/data/resumes/cand_01_asha_verma.txt").read_bytes()
    for i in range(3):
        (bench_dir / f"resume_{i}.txt").write_bytes(sample)

    argv = [
        "benchmark",
        "--resumes-dir",
        str(bench_dir),
        "--runs",
        "1",
    ]

    exit_code = cli.main(argv)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "BENCHMARK RESULTS" in captured.out
    assert "Throughput:" in captured.out


def test_cli_invalid_command() -> None:
    """Verify invalid CLI command returns code 2."""
    assert cli.main(["invalid_command"]) == 2


def test_cli_list_command(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify list command returns exit code 0."""
    exit_code = cli.main(["list"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert (
        "saved analyses" in captured.out.lower()
        or "no saved analyses" in captured.out.lower()
    )


def test_cli_feedback_summary_command(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify feedback-summary command returns exit code 0."""
    exit_code = cli.main(["feedback-summary"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "feedback" in captured.out.lower()


def test_cli_purge_command(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify purge command executes with --yes flag and returns code 0."""
    exit_code = cli.main(["purge", "--days", "90", "--yes"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "purged" in captured.out.lower()


def test_cli_export_missing_record(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify export command returns code 2 when report ID does not exist."""
    exit_code = cli.main(["export", "--id", "20261108T120000Z_11112222_3333"])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "not found" in captured.err.lower()
