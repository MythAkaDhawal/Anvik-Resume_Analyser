"""Persistent storage and retrieval for AnalysisReport models (TECHNICAL_SPECIFICATION §5.10).

Provides atomic file persistence (FR-27), schema validation, path traversal defense,
safe listing with corruption isolation, single report deletion, and retention-based purging (FR-28, NFR-19).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from resume_analyzer.config.settings import Settings, get_settings
from resume_analyzer.exceptions import (
    CorruptResultError,
    ResultNotFoundError,
    StorageError,
)
from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.storage.paths import safe_join, validate_report_id

logger = logging.getLogger(__name__)


class ReportSummary(BaseModel):
    """Metadata summary for browsing and listing saved analysis reports."""

    model_config = ConfigDict(extra="forbid")

    report_id: str
    candidate_name: str | None = None
    created_at: datetime | None = None
    total_score: float | None = None
    fit_band: str | None = None
    strategy: str | None = None
    readable: bool = True
    path: str | None = None


class ResultStore:
    """Filesystem repository for saving, loading, listing, and purging analysis reports."""

    def __init__(
        self,
        base_dir: Path | str | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize ResultStore with base storage directory."""
        cfg = settings or get_settings()
        target_dir = base_dir or getattr(cfg.storage, "results_dir", "data/results")
        self.base_dir = Path(target_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, report: AnalysisReport) -> Path:
        """Atomically persist AnalysisReport as JSON with safe permissions (FR-27).

        Args:
            report: Validated AnalysisReport object.

        Returns:
            Resolved destination Path to the saved JSON file.

        Raises:
            InvalidIdentifierError: If report.report_id is malformed.
            StorageError: If directory cannot be created or write fails.
        """
        valid_id = validate_report_id(report.report_id)
        target = safe_join(self.base_dir, f"{valid_id}.json")
        parent_dir = target.parent

        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(
                f"Failed to create results directory '{parent_dir}': {e}",
                user_message="Could not write the result.",
                details={"path": str(parent_dir), "error": str(e)},
            ) from e

        temp_file = parent_dir / f"{target.stem}.{uuid.uuid4().hex[:8]}.tmp"

        try:
            # Serialize report to JSON string
            payload = report.model_dump_json(indent=2)
            temp_file.write_text(payload, encoding="utf-8")

            # Apply 0600 file mode where supported (POSIX)
            try:
                os.chmod(temp_file, 0o600)
            except (OSError, NotImplementedError):
                pass

            # Atomic replace
            os.replace(temp_file, target)
            logger.info("Saved report id=%s path=%s", valid_id, target)
            return target
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            logger.error("Failed to write report id=%s: %s", valid_id, e)
            raise StorageError(
                f"Failed to persist report '{valid_id}' to '{target}': {e}",
                user_message="Could not write the result.",
                details={"report_id": valid_id, "path": str(target), "error": str(e)},
            ) from e

    def load(self, report_id: str) -> AnalysisReport:
        """Load and validate an AnalysisReport from disk by ID (FR-28).

        Args:
            report_id: Canonical report identifier string.

        Returns:
            Loaded and validated AnalysisReport model.

        Raises:
            InvalidIdentifierError: If report_id fails regex validation.
            ResultNotFoundError: If analysis file does not exist.
            CorruptResultError: If file is malformed JSON or has incompatible schema_version.
        """
        valid_id = validate_report_id(report_id)
        target = safe_join(self.base_dir, f"{valid_id}.json")

        if not target.is_file():
            raise ResultNotFoundError(valid_id, details={"path": str(target)})

        try:
            raw = target.read_text(encoding="utf-8")
        except OSError as e:
            raise CorruptResultError(
                f"Cannot read report file '{target}': {e}",
                details={"report_id": valid_id, "error": str(e)},
            ) from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as jde:
            raise CorruptResultError(
                f"Report '{valid_id}' contains malformed JSON: {jde}",
                details={"report_id": valid_id, "error": str(jde)},
            ) from jde

        if not isinstance(data, dict):
            raise CorruptResultError(
                f"Report '{valid_id}' root must be an object.",
                details={"report_id": valid_id},
            )

        # Check schema version compatibility (UT-STORE-05)
        schema_ver = data.get("schema_version")
        if schema_ver != "1.0":
            raise CorruptResultError(
                f"Incompatible report schema_version '{schema_ver}' for report '{valid_id}'. Expected '1.0'.",
                details={"report_id": valid_id, "schema_version": schema_ver},
            )

        try:
            return AnalysisReport.model_validate(data)
        except ValidationError as ve:
            raise CorruptResultError(
                f"Report '{valid_id}' failed schema validation: {ve}",
                details={"report_id": valid_id, "error": str(ve)},
            ) from ve

    def list(self) -> list[ReportSummary]:
        """List all saved analysis reports ordered newest first (FR-28).

        Corrupt or unreadable files are recorded with readable=False to prevent
        crashes in UI or listing workflows.

        Returns:
            List of ReportSummary objects, sorted by created_at descending.
        """
        summaries: list[ReportSummary] = []
        if not self.base_dir.is_dir():
            return summaries

        json_files = list(self.base_dir.glob("*.json"))

        for f in json_files:
            file_id = f.stem
            try:
                raw = f.read_text(encoding="utf-8")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("Root is not a JSON object")

                cand = data.get("candidate", {})
                score = data.get("score", {})
                created_raw = data.get("created_at")

                created_dt: datetime | None = None
                if created_raw:
                    try:
                        created_dt = datetime.fromisoformat(created_raw)
                    except Exception:
                        created_dt = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
                else:
                    created_dt = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)

                fit_band_val = score.get("fit_band")
                if isinstance(fit_band_val, dict):
                    fit_band_str = fit_band_val.get("value")
                else:
                    fit_band_str = str(fit_band_val) if fit_band_val else None

                summaries.append(
                    ReportSummary(
                        report_id=file_id,
                        candidate_name=cand.get("name"),
                        created_at=created_dt,
                        total_score=score.get("total_score"),
                        fit_band=fit_band_str,
                        strategy=score.get("strategy_name"),
                        readable=True,
                        path=str(f),
                    )
                )
            except Exception as e:
                logger.warning("Unreadable analysis file in store '%s': %s", f.name, e)
                file_dt = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
                summaries.append(
                    ReportSummary(
                        report_id=file_id,
                        candidate_name="Unreadable",
                        created_at=file_dt,
                        readable=False,
                        path=str(f),
                    )
                )

        # Sort newest first by created_at descending
        summaries.sort(
            key=lambda s: s.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return summaries

    def delete(self, report_id: str) -> None:
        """Delete an individual report by identifier (FR-28, NFR-19).

        Args:
            report_id: Canonical report identifier.

        Raises:
            InvalidIdentifierError: If report_id fails regex validation.
            ResultNotFoundError: If analysis file does not exist.
            StorageError: If file deletion fails due to permission errors.
        """
        valid_id = validate_report_id(report_id)
        target = safe_join(self.base_dir, f"{valid_id}.json")

        if not target.is_file():
            raise ResultNotFoundError(valid_id, details={"path": str(target)})

        try:
            target.unlink()
            logger.info("Deleted analysis record id=%s", valid_id)
        except OSError as e:
            raise StorageError(
                f"Failed to delete analysis file '{target}': {e}",
                user_message="Could not delete the saved analysis.",
                details={"report_id": valid_id, "error": str(e)},
            ) from e

    def purge_older_than(self, days: int) -> int:
        """Purge saved reports older than specified days based on created_at (FR-28, NFR-19).

        Guaranteed not to delete non-report files or other directories.

        Args:
            days: Age threshold in days.

        Returns:
            Count of successfully deleted report files.
        """
        if days < 0:
            return 0

        cutoff_sec = datetime.now(UTC).timestamp() - (days * 86400)
        deleted = 0

        for f in self.base_dir.glob("*.json"):
            # Check created_at inside json if readable, otherwise stat mtime
            file_ts = f.stat().st_mtime
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                created_str = data.get("created_at")
                if created_str:
                    file_ts = datetime.fromisoformat(created_str).timestamp()
            except Exception:
                logger.debug(
                    "Failed to parse created_at timestamp from %s; using stat mtime", f
                )

            if file_ts < cutoff_sec:
                try:
                    f.unlink()
                    deleted += 1
                except OSError as e:
                    logger.warning(
                        "Failed to purge old report file '%s': %s", f.name, e
                    )

        logger.info("Purged %d old analysis records (>%d days)", deleted, days)
        return deleted

    def delete_all(self) -> int:
        """Delete all saved report JSON files in base_dir.

        Returns:
            Count of deleted files.
        """
        deleted = 0
        for f in self.base_dir.glob("*.json"):
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
        return deleted
