"""Abstract base class and registry for report exporters.

Enforces uniform export contracts, atomic file writes with cleanup on error,
and strict format validation (FR-24–FR-26).
"""

from __future__ import annotations

import logging
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Literal

from resume_analyzer.exceptions import ExportError, UnsupportedExportFormatError
from resume_analyzer.models.results import AnalysisReport

logger = logging.getLogger(__name__)


class Exporter(ABC):
    """Abstract base class for AnalysisReport document exporters."""

    format: ClassVar[str]

    @abstractmethod
    def render_bytes(self, report: AnalysisReport) -> bytes:
        """Render report into byte payload for this exporter's format."""
        ...

    def export_bytes(self, report: AnalysisReport) -> bytes:
        """Render report into byte payload (alias for render_bytes)."""
        return self.render_bytes(report)

    def export_to_file(self, report: AnalysisReport, out_path: Path | str) -> Path:
        """Export report to file path atomically (alias for export)."""
        return self.export(report, out_path)

    def export(self, report: AnalysisReport, out_path: Path | str) -> Path:
        """Export report to file path atomically with error handling.

        Writes output to a temporary file in the target directory, then replaces
        the target atomically. Cleans up temporary artifacts on failure.

        Args:
            report: Validated AnalysisReport instance.
            out_path: Destination file path.

        Returns:
            Resolved Path to the successfully written report file.

        Raises:
            ExportError: If directory cannot be created, write fails, or rendering errors.
        """
        target = Path(out_path).resolve()
        parent_dir = target.parent

        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ExportError(
                f"Failed to create target directory '{parent_dir}': {e}",
                details={"path": str(target), "format": self.format},
            ) from e

        temp_file = parent_dir / f"{target.stem}.{uuid.uuid4().hex[:8]}.tmp"

        try:
            content_bytes = self.render_bytes(report)
            with open(temp_file, "wb") as f:
                f.write(content_bytes)

            os.replace(temp_file, target)
            logger.info(
                "Export written fmt=%s cid=%s path=%s",
                self.format,
                report.candidate.candidate_id,
                target,
            )
            return target
        except Exception as e:
            # Guarantee no partial file left behind
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

            if isinstance(e, ExportError):
                raise
            raise ExportError(
                f"Failed to export {self.format.upper()} report to '{target}': {e}",
                details={"path": str(target), "format": self.format, "error": str(e)},
            ) from e


_EXPORTER_REGISTRY: dict[str, type[Exporter]] = {}


def register_exporter(exporter_cls: type[Exporter]) -> type[Exporter]:
    """Register an exporter implementation class by its declared format."""
    _EXPORTER_REGISTRY[exporter_cls.format.lower()] = exporter_cls
    return exporter_cls


def get_exporter(fmt: Literal["html", "pdf", "xlsx"] | str) -> Exporter:
    """Retrieve an instantiated Exporter for the specified format.

    Args:
        fmt: Format identifier ('html', 'pdf', 'xlsx').

    Returns:
        Instantiated Exporter.

    Raises:
        UnsupportedExportFormatError: If format is not supported.
    """
    clean_fmt = fmt.strip().lower()
    if clean_fmt not in _EXPORTER_REGISTRY:
        # Lazy load implementations to avoid circular imports
        if clean_fmt == "html":
            from resume_analyzer.reporting.exporters.html_exporter import HTMLExporter

            return HTMLExporter()
        elif clean_fmt == "pdf":
            from resume_analyzer.reporting.exporters.pdf_exporter import PDFExporter

            return PDFExporter()
        elif clean_fmt in ("xlsx", "excel"):
            from resume_analyzer.reporting.exporters.excel_exporter import ExcelExporter

            return ExcelExporter()
        else:
            raise UnsupportedExportFormatError(
                clean_fmt,
                available=list(_EXPORTER_REGISTRY.keys()) or ["html", "pdf", "xlsx"],
            )

    return _EXPORTER_REGISTRY[clean_fmt]()


def export_batch_workbook(
    reports: list[AnalysisReport], out_path: Path | str | None = None
) -> Path | bytes:
    """Export aggregated multi-candidate ranking workbook.

    Args:
        reports: List of analyzed candidate reports.
        out_path: Optional output Excel destination path. If None, returns bytes.

    Returns:
        Path to exported workbook, or raw bytes if out_path was None.
    """
    from resume_analyzer.reporting.exporters.excel_exporter import ExcelExporter

    exporter = ExcelExporter()
    if out_path is None:
        return exporter.export_batch_bytes(reports)
    return exporter.export_batch(reports, out_path)
