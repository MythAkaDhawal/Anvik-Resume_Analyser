"""Logging configuration and PII-masking filters for Resume Analyzer.

Provides structured UTC formatting, file rotation, and defense-in-depth
redaction of e-mail and phone numbers from all log output.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from resume_analyzer.config.settings import LoggingSettings, Settings

# Regular expressions for PII detection and masking
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)

# Common international and national phone number patterns (at least 7 digits)
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,4}[-.\s]?)?(?:\(?\d{2,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{3,5}\b"
)


class PIIMaskingFilter(logging.Filter):
    """Logging filter that scrubs e-mail addresses and phone numbers from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize message and arguments to remove personal contact information."""
        if isinstance(record.msg, str):
            record.msg = self.mask_text(record.msg)

        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self.mask_text(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (self.mask_text(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }

        return True

    @classmethod
    def mask_text(cls, text: str) -> str:
        """Replace emails and phone numbers with redaction placeholders.

        Args:
            text: Raw input text.

        Returns:
            Sanitized text with [EMAIL_REDACTED] and [PHONE_REDACTED].
        """
        text = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
        text = PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
        return text


class UTCFormatter(logging.Formatter):
    """Formatter that outputs timestamps in UTC."""

    converter = time.gmtime


def setup_logging(
    settings: Settings | LoggingSettings | None = None,
) -> logging.Logger:
    """Configure structured logging for resume_analyzer with rotation and PII masking.

    Args:
        settings: Settings or LoggingSettings instance. If omitted, uses defaults.

    Returns:
        Configured logger instance for 'resume_analyzer'.
    """
    log_settings: LoggingSettings
    if isinstance(settings, Settings):
        log_settings = settings.logging
    elif isinstance(settings, LoggingSettings):
        log_settings = settings
    else:
        log_settings = LoggingSettings()

    log_level = getattr(logging, log_settings.level.upper(), logging.INFO)
    logger = logging.getLogger("resume_analyzer")
    logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if logger.handlers:
        logger.handlers.clear()

    formatter = UTCFormatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    pii_filter = PIIMaskingFilter()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(pii_filter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    try:
        log_dir = Path(log_settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / log_settings.file_name

        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=log_settings.max_bytes,
            backupCount=log_settings.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(pii_filter)
        logger.addHandler(file_handler)
    except OSError as err:
        logger.warning(
            "Could not set up file logging to %s: %s", log_settings.log_dir, err
        )

    # Do not propagate to root to avoid duplicate messages in application logs
    logger.propagate = False
    return logger
