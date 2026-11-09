"""Unit tests for logging configuration and PII masking filter (UT-LOG-*)."""

from __future__ import annotations

import logging
from pathlib import Path

from resume_analyzer.config.settings import LoggingSettings
from resume_analyzer.logging_setup import PIIMaskingFilter, setup_logging


def test_pii_masking_filter_masks_emails_and_phones() -> None:
    """UT-LOG-01: Verify PIIMaskingFilter masks email addresses and telephone numbers."""
    pii_filter = PIIMaskingFilter()

    # Test raw text masking
    masked = pii_filter.mask_text(
        "Contact candidate at john.doe@example.com or +1 (555) 123-4567."
    )
    assert "[EMAIL_REDACTED]" in masked
    assert "john.doe@example.com" not in masked
    assert "[PHONE_REDACTED]" in masked
    assert "555" not in masked

    # Test record filtering in msg and args
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Processing candidate email %s and phone %s",
        args=("candidate@domain.org", "+91 98765 43210"),
        exc_info=None,
    )
    pii_filter.filter(record)

    assert "candidate@domain.org" not in str(record.args)
    assert "[EMAIL_REDACTED]" in str(record.args)
    assert "[PHONE_REDACTED]" in str(record.args)


def test_setup_logging_and_levels(tmp_path: Path) -> None:
    """UT-LOG-02: Verify logger setup with rotating file handler and log levels."""
    log_dir = tmp_path / "logs"
    settings = LoggingSettings(
        level="WARNING",
        log_dir=log_dir,
        file_name="app.log",
        max_bytes=1024,
        backup_count=2,
    )
    logger = setup_logging(settings)

    assert logger.level == logging.WARNING
    assert len(logger.handlers) >= 1

    # Log an info message (should be ignored) and warning message (should be logged)
    logger.info("This is an info message: test@example.com")
    logger.warning("This is a warning message: alert@example.com")

    # Flush handlers
    for h in logger.handlers:
        h.flush()

    log_file = log_dir / "app.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")

    assert "warning message" in content
    assert "alert@example.com" not in content
    assert "[EMAIL_REDACTED]" in content
    assert "info message" not in content  # Level was WARNING


def test_logs_contain_no_resume_text(tmp_path: Path) -> None:
    """UT-LOG-03: Verify logging never leaks raw resume text or personal details."""
    log_dir = tmp_path / "logs"
    settings = LoggingSettings(
        level="INFO",
        log_dir=log_dir,
        file_name="security.log",
    )
    logger = setup_logging(settings)

    candidate_email = "secret_candidate_123@topcompany.com"
    candidate_phone = "555-890-1234"
    logger.info(
        "Candidate submitted with email %s, phone %s and unique token",
        candidate_email,
        candidate_phone,
    )

    for h in logger.handlers:
        h.flush()

    log_file = log_dir / "security.log"
    content = log_file.read_text(encoding="utf-8")
    assert candidate_email not in content
    assert candidate_phone not in content
    assert "[EMAIL_REDACTED]" in content
    assert "[PHONE_REDACTED]" in content
