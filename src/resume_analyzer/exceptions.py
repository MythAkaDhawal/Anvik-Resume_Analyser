"""Exception hierarchy and error codes for Intelligent Resume Analyzer.

All domain, validation, ingestion, matching, AI, storage, and export errors
subclass ResumeAnalyzerError with a unique error code and user-facing message.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ResumeAnalyzerError(Exception):
    """Base class for all domain and operational errors in Resume Analyzer.

    Attributes:
        message: Detailed technical description of the error.
        error_code: Unique system-wide error code.
        user_message: Human-safe explanation suitable for UI presentation.
        details: Diagnostic dictionary. Must never contain raw resume text.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "E-UNEXPECTED",
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the base error."""
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.user_message = user_message or message
        self.details = details or {}

    def __str__(self) -> str:
        """Return formatted error string."""
        return f"[{self.error_code}] {self.message}"


# --- Configuration ---


class ConfigurationError(ResumeAnalyzerError):
    """Raised when configuration validation or loading fails."""

    def __init__(
        self,
        message: str,
        *,
        key: str | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ConfigurationError."""
        details_dict = details or {}
        if key:
            details_dict["key"] = key
        default_user_msg = (
            f"The application configuration is invalid: {key}."
            if key
            else "The application configuration is invalid."
        )
        super().__init__(
            message,
            error_code="E-CFG-001",
            user_message=user_message or default_user_msg,
            details=details_dict,
        )


# --- File Validation & Ingestion ---


class FileValidationError(ResumeAnalyzerError):
    """Base exception for file validation failures during upload/ingestion."""


class UnsupportedFileTypeError(FileValidationError):
    """Raised when an uploaded file is not among allowed extensions."""

    def __init__(
        self,
        message: str = "Unsupported file type.",
        *,
        user_message: str = "Only PDF, DOCX and TXT files are supported.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize UnsupportedFileTypeError."""
        super().__init__(
            message,
            error_code="E-FILE-001",
            user_message=user_message,
            details=details,
        )


class FileTooLargeError(FileValidationError):
    """Raised when an uploaded file exceeds the configured size limit."""

    def __init__(
        self,
        message: str = "File exceeds maximum allowed size.",
        *,
        max_size_mb: int | None = None,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize FileTooLargeError."""
        default_user_msg = (
            f"The file exceeds the size limit of {max_size_mb} MB."
            if max_size_mb
            else "The file exceeds the configured size limit."
        )
        super().__init__(
            message,
            error_code="E-FILE-002",
            user_message=user_message or default_user_msg,
            details=details,
        )


class EmptyFileError(FileValidationError):
    """Raised when an uploaded file contains zero bytes."""

    def __init__(
        self,
        message: str = "File is empty.",
        *,
        user_message: str = "The file is empty.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize EmptyFileError."""
        super().__init__(
            message,
            error_code="E-FILE-003",
            user_message=user_message,
            details=details,
        )


class UnreadableFileError(FileValidationError):
    """Raised when an uploaded file cannot be parsed or read."""

    def __init__(
        self,
        message: str = "File could not be read or is corrupted.",
        *,
        user_message: str = "The file could not be read; it may be corrupted.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize UnreadableFileError."""
        super().__init__(
            message,
            error_code="E-FILE-004",
            user_message=user_message,
            details=details,
        )


class EncryptedFileError(FileValidationError):
    """Raised when a PDF or document is password-protected."""

    def __init__(
        self,
        message: str = "File is password protected.",
        *,
        user_message: str = "Password-protected files are not supported.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize EncryptedFileError."""
        super().__init__(
            message,
            error_code="E-FILE-005",
            user_message=user_message,
            details=details,
        )


class FileTypeMismatchError(FileValidationError):
    """Raised when magic bytes do not match the declared file extension."""

    def __init__(
        self,
        message: str = "File content does not match its extension.",
        *,
        user_message: str = "The file content does not match its extension.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize FileTypeMismatchError."""
        super().__init__(
            message,
            error_code="E-FILE-006",
            user_message=user_message,
            details=details,
        )


class UnsafeArchiveError(FileValidationError):
    """Raised when DOCX archive structure exceeds decompression limits."""

    def __init__(
        self,
        message: str = "File structure is unsafe or exceeds archive decompression limits.",
        *,
        user_message: str = "The file structure is unsafe or exceeds limits.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize UnsafeArchiveError."""
        super().__init__(
            message,
            error_code="E-FILE-007",
            user_message=user_message,
            details=details,
        )


# --- Parsing ---


class ParsingError(ResumeAnalyzerError):
    """Base exception for parsing errors."""

    def __init__(
        self,
        message: str = "The resume could not be parsed.",
        *,
        error_code: str = "E-PARSE-002",
        user_message: str = "The resume could not be parsed.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ParsingError."""
        super().__init__(
            message,
            error_code=error_code,
            user_message=user_message,
            details=details,
        )


class EmptyResumeError(ParsingError):
    """Raised when extracted resume text is empty or below minimum character threshold."""

    def __init__(
        self,
        message: str = "No readable text extracted from resume.",
        *,
        user_message: str = "No readable text found. Scanned documents are not supported (no OCR).",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize EmptyResumeError."""
        super().__init__(
            message,
            error_code="E-PARSE-001",
            user_message=user_message,
            details=details,
        )


# --- Data Validation ---


class DataValidationError(ResumeAnalyzerError):
    """Raised when domain entities fail semantic validation."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "E-DATA-001",
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize DataValidationError."""
        super().__init__(
            message,
            error_code=error_code,
            user_message=user_message or "Data validation failed.",
            details=details,
        )


class JobValidationError(DataValidationError):
    """Raised when job requirements specification is invalid."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize JobValidationError."""
        details_dict = details or {}
        if errors:
            details_dict["errors"] = errors
        err_list = "; ".join(errors) if errors else message
        super().__init__(
            message,
            error_code="E-DATA-001",
            user_message=f"Job requirements are invalid: {err_list}.",
            details=details_dict,
        )


class CandidateValidationError(DataValidationError):
    """Raised when parsed candidate data violates domain integrity."""

    def __init__(
        self,
        message: str,
        *,
        user_message: str = "Parsed data failed validation.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CandidateValidationError."""
        super().__init__(
            message,
            error_code="E-DATA-002",
            user_message=user_message,
            details=details,
        )


# --- Matching & Scoring ---


class MatchingError(ResumeAnalyzerError):
    """Raised when candidate-job matching encounters an unexpected failure."""

    def __init__(
        self,
        message: str = "Matching failed unexpectedly.",
        *,
        error_code: str = "E-MATCH-002",
        user_message: str = "Matching failed unexpectedly.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize MatchingError."""
        super().__init__(
            message,
            error_code=error_code,
            user_message=user_message,
            details=details,
        )


class UnknownStrategyError(MatchingError):
    """Raised when an unregistered scoring strategy is requested."""

    def __init__(
        self,
        strategy_name: str,
        available: list[str] | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize UnknownStrategyError."""
        avail_str = ", ".join(available) if available else "basic, weighted"
        message = f"Unknown scoring strategy '{strategy_name}'. Available: {avail_str}."
        user_message = f"Unknown scoring strategy. Available: {avail_str}."
        details_dict = details or {}
        details_dict["requested"] = strategy_name
        details_dict["available"] = available or ["basic", "weighted"]
        super().__init__(
            message,
            error_code="E-MATCH-001",
            user_message=user_message,
            details=details_dict,
        )


# --- AI Provider ---


class AIError(ResumeAnalyzerError):
    """Base exception for AI provider integration failures."""


class AIConfigurationError(AIError):
    """Raised when AI is enabled but API keys or configuration is missing."""

    def __init__(
        self,
        message: str = "AI is not configured (missing key or provider).",
        *,
        user_message: str = "AI is not configured (missing key or provider).",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize AIConfigurationError."""
        super().__init__(
            message,
            error_code="E-AI-001",
            user_message=user_message,
            details=details,
        )


class AIProviderError(AIError):
    """Raised when provider call times out, returns HTTP 5xx, or network fails."""

    def __init__(
        self,
        message: str = "The AI service is unavailable or timed out.",
        *,
        user_message: str = "The AI service is unavailable or timed out.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize AIProviderError."""
        super().__init__(
            message,
            error_code="E-AI-002",
            user_message=user_message,
            details=details,
        )


class AIResponseError(AIError):
    """Raised when AI returns an unparseable or schema-violating response."""

    def __init__(
        self,
        message: str = "The AI returned an unusable response.",
        *,
        user_message: str = "The AI returned an unusable response.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize AIResponseError."""
        super().__init__(
            message,
            error_code="E-AI-003",
            user_message=user_message,
            details=details,
        )


class AIBlockedError(AIError):
    """Raised when an AI provider safety filter blocks the request."""

    def __init__(
        self,
        message: str = "The AI provider blocked this request.",
        *,
        user_message: str = "The AI provider blocked this request.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize AIBlockedError."""
        super().__init__(
            message,
            error_code="E-AI-004",
            user_message=user_message,
            details=details,
        )


# Backward-compatible convenience aliases & specialized AI exceptions
AIServiceError = AIResponseError


class AIProviderUnavailableError(AIProviderError):
    """Raised when an AI provider is unreachable or unavailable."""

    def __init__(
        self,
        message: str = "The AI service is unavailable or timed out.",
        *,
        provider: str | None = None,
        user_message: str = "The AI service is unavailable or timed out.",
        details: dict[str, Any] | None = None,
    ) -> None:
        det = dict(details or {})
        if provider:
            det["provider"] = provider
        super().__init__(
            message,
            user_message=user_message,
            details=det,
        )
        self.provider = provider


class AIRateLimitError(AIProviderError):
    """Raised when client-side or provider rate limit is encountered."""

    def __init__(
        self,
        message: str = "Rate limit reached.",
        *,
        provider: str | None = None,
        retry_after_s: float | None = None,
        user_message: str = "AI rate limit reached. Please retry shortly.",
        details: dict[str, Any] | None = None,
    ) -> None:
        det = dict(details or {})
        if provider:
            det["provider"] = provider
        if retry_after_s is not None:
            det["retry_after_s"] = retry_after_s
        super().__init__(
            message,
            user_message=user_message,
            details=det,
        )
        self.provider = provider
        self.retry_after_s = retry_after_s


# --- Storage ---


class StorageError(ResumeAnalyzerError):
    """Base exception for persistence failures."""

    def __init__(
        self,
        message: str = "Could not write or access the storage result.",
        *,
        error_code: str = "E-STORE-001",
        user_message: str = "Could not write the result.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize StorageError."""
        super().__init__(
            message,
            error_code=error_code,
            user_message=user_message,
            details=details,
        )


class ResultNotFoundError(StorageError):
    """Raised when a requested analysis report ID is not found in storage."""

    def __init__(
        self,
        report_id: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ResultNotFoundError."""
        details_dict = details or {}
        details_dict["report_id"] = report_id
        super().__init__(
            f"Saved analysis with ID '{report_id}' was not found.",
            error_code="E-STORE-002",
            user_message="Saved analysis not found.",
            details=details_dict,
        )


class CorruptResultError(StorageError):
    """Raised when a persisted JSON file is malformed or has incompatible version."""

    def __init__(
        self,
        message: str = "The saved analysis is unreadable or corrupted.",
        *,
        user_message: str = "The saved analysis is unreadable.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CorruptResultError."""
        super().__init__(
            message,
            error_code="E-STORE-003",
            user_message=user_message,
            details=details,
        )


class InvalidIdentifierError(StorageError):
    """Raised when an identifier fails validation or attempts path traversal."""

    def __init__(
        self,
        identifier: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize InvalidIdentifierError."""
        details_dict = details or {}
        details_dict["identifier"] = identifier
        super().__init__(
            f"Invalid analysis identifier '{identifier}'.",
            error_code="E-STORE-004",
            user_message="Invalid analysis identifier.",
            details=details_dict,
        )


# --- Export ---


class ExportError(ResumeAnalyzerError):
    """Base exception for export failures."""

    def __init__(
        self,
        message: str = "The report could not be exported.",
        *,
        error_code: str = "E-EXPORT-001",
        user_message: str = "The report could not be exported.",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ExportError."""
        super().__init__(
            message,
            error_code=error_code,
            user_message=user_message,
            details=details,
        )


class UnsupportedExportFormatError(ExportError):
    """Raised when an unknown export format is requested."""

    def __init__(
        self,
        fmt: str,
        available: list[str] | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize UnsupportedExportFormatError."""
        avail_str = ", ".join(available) if available else "html, pdf, xlsx"
        details_dict = details or {}
        details_dict["format"] = fmt
        super().__init__(
            f"Unsupported export format '{fmt}'. Available: {avail_str}.",
            error_code="E-EXPORT-002",
            user_message="Unsupported export format.",
            details=details_dict,
        )


# --- Unexpected Boundary Wrapping Helper ---


def wrap_unexpected_error(
    exc: Exception,
    context_message: str = "An unexpected error occurred.",
) -> ResumeAnalyzerError:
    """Log and wrap an unexpected exception at a service boundary.

    Guarantees that traceback and diagnostic details do not leak raw resume text.

    Args:
        exc: Caught unexpected exception.
        context_message: Contextual message describing the operation.

    Returns:
        ResumeAnalyzerError with code E-UNEXPECTED.
    """
    logger.exception("%s: %s", context_message, str(exc))
    return ResumeAnalyzerError(
        f"{context_message}: {exc}",
        error_code="E-UNEXPECTED",
        user_message="An unexpected system error occurred. Please consult the application logs.",
        details={"exception_type": type(exc).__name__},
    )
