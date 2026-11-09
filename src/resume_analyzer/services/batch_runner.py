"""Batch runner executing isolated multi-resume processing with progress tracking.

Enforces per-file failure isolation (FR-30) so that invalid or corrupt files
never abort processing of the remaining batch.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from resume_analyzer.exceptions import ResumeAnalyzerError
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


class FileFailure(BaseModel):
    """Failure record for a single file within a batch run.

    Attributes:
        display_name: Neutral filename of the rejected resume.
        error_code: Machine-readable error code (e.g. 'E-FILE-001').
        user_message: Safe user-facing error message without PII.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str
    error_code: str
    user_message: str


class BatchResult(BaseModel):
    """Aggregated batch execution outcome containing reports and failure records.

    Attributes:
        reports: Successfully analyzed reports, sorted by score descending.
        failures: Per-file error records for any files that failed processing.
    """

    model_config = ConfigDict(extra="forbid")

    reports: list[AnalysisReport] = Field(default_factory=list)
    failures: list[FileFailure] = Field(default_factory=list)


def _safe_display_name(filename: str) -> str:
    """Extract safe basename without paths or control characters."""
    try:
        clean = Path(filename).name.strip()
        return clean or "unnamed_file"
    except Exception:
        return "unnamed_file"


class BatchRunner:
    """Batch coordinator executing resume analysis with isolation and progress."""

    def __init__(self, analysis_service: AnalysisService) -> None:
        """Initialize batch runner with an AnalysisService instance."""
        self.analysis_service = analysis_service

    def run(
        self,
        files: Sequence[tuple[str, bytes]],
        job: JobRequirements,
        options: AnalysisOptions | None = None,
        progress: ProgressCallback | None = None,
    ) -> BatchResult:
        """Run batch analysis across a collection of (filename, file_bytes) pairs.

        Args:
            files: Sequence of (filename, byte payload) tuples.
            job: Validated job requirements.
            options: Optional analysis options.
            progress: Optional callback invoked as progress(done, total, current_file).

        Returns:
            BatchResult with successfully produced reports and failure diagnostics.
        """
        opts = options or AnalysisOptions()
        reports: list[AnalysisReport] = []
        failures: list[FileFailure] = []
        total = len(files)

        for idx, (filename, data) in enumerate(files, start=1):
            display_name = _safe_display_name(filename)
            try:
                report = self.analysis_service.analyze(
                    filename=display_name,
                    data=data,
                    job=job,
                    options=opts,
                )
                reports.append(report)
            except ResumeAnalyzerError as e:
                logger.warning(
                    "Batch item '%s' failed with %s: %s", display_name, e.error_code, e
                )
                failures.append(
                    FileFailure(
                        display_name=display_name,
                        error_code=e.error_code,
                        user_message=e.user_message or str(e),
                    )
                )
            except Exception as e:
                logger.exception(
                    "Unexpected error processing batch item '%s': %s", display_name, e
                )
                failures.append(
                    FileFailure(
                        display_name=display_name,
                        error_code="E-GEN-001",
                        user_message="An unexpected error occurred while processing this file.",
                    )
                )
            finally:
                if progress is not None:
                    try:
                        progress(idx, total, display_name)
                    except Exception as pe:
                        logger.warning("Progress callback raised exception: %s", pe)

        # Rank reports: Total score desc, required_credit desc, candidate_id asc
        reports.sort(
            key=lambda r: (
                -r.score.total_score,
                -r.match.required_credit,
                r.candidate.candidate_id,
            )
        )

        return BatchResult(reports=reports, failures=failures)

    def run_paths(
        self,
        paths: Sequence[Path | str],
        job: JobRequirements,
        options: AnalysisOptions | None = None,
        progress: ProgressCallback | None = None,
    ) -> BatchResult:
        """Read files from disk paths and execute batch analysis with isolation."""
        file_payloads: list[tuple[str, bytes]] = []
        path_failures: list[FileFailure] = []

        for p in paths:
            path_obj = Path(p)
            try:
                data = path_obj.read_bytes()
                file_payloads.append((path_obj.name, data))
            except Exception as e:
                logger.warning("Failed to read batch file '%s': %s", path_obj.name, e)
                path_failures.append(
                    FileFailure(
                        display_name=_safe_display_name(path_obj.name),
                        error_code="E-FILE-001",
                        user_message=f"Could not read file from disk: {e}",
                    )
                )

        batch_res = self.run(file_payloads, job=job, options=options, progress=progress)
        # Combine disk-read failures with runner failures
        combined_failures = path_failures + batch_res.failures
        return BatchResult(reports=batch_res.reports, failures=combined_failures)
