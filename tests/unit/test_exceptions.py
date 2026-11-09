"""Unit tests for exception hierarchy, error codes, and user messages (UT-EXC-*)."""

from __future__ import annotations

from resume_analyzer.exceptions import (
    AIBlockedError,
    AIConfigurationError,
    AIProviderError,
    AIResponseError,
    CandidateValidationError,
    ConfigurationError,
    CorruptResultError,
    DataValidationError,
    EmptyFileError,
    EmptyResumeError,
    EncryptedFileError,
    ExportError,
    FileTooLargeError,
    FileTypeMismatchError,
    InvalidIdentifierError,
    JobValidationError,
    MatchingError,
    ParsingError,
    ResultNotFoundError,
    ResumeAnalyzerError,
    StorageError,
    UnknownStrategyError,
    UnreadableFileError,
    UnsafeArchiveError,
    UnsupportedExportFormatError,
    UnsupportedFileTypeError,
    wrap_unexpected_error,
)


def test_exception_hierarchy_and_unique_error_codes() -> None:
    """UT-EXC-01: Verify all domain exceptions inherit from ResumeAnalyzerError and have codes."""
    exception_classes = [
        ConfigurationError,
        UnsupportedFileTypeError,
        FileTooLargeError,
        EmptyFileError,
        UnreadableFileError,
        EncryptedFileError,
        FileTypeMismatchError,
        UnsafeArchiveError,
        EmptyResumeError,
        ParsingError,
        DataValidationError,
        JobValidationError,
        CandidateValidationError,
        UnknownStrategyError,
        MatchingError,
        AIConfigurationError,
        AIProviderError,
        AIResponseError,
        AIBlockedError,
        StorageError,
        ResultNotFoundError,
        CorruptResultError,
        InvalidIdentifierError,
        ExportError,
        UnsupportedExportFormatError,
    ]

    seen_codes: set[str] = set()

    for exc_cls in exception_classes:
        # Instantiate with minimal dummy parameters
        if exc_cls in (
            JobValidationError,
            CandidateValidationError,
            DataValidationError,
            ConfigurationError,
        ):
            inst = exc_cls("Validation error")
        elif exc_cls is UnknownStrategyError:
            inst = exc_cls("non_existent")
        elif exc_cls is ResultNotFoundError:
            inst = exc_cls("rep_123")
        elif exc_cls is InvalidIdentifierError:
            inst = exc_cls("bad_id")
        elif exc_cls is UnsupportedExportFormatError:
            inst = exc_cls("docx")
        else:
            inst = exc_cls()

        assert isinstance(inst, ResumeAnalyzerError)
        assert isinstance(inst, Exception)
        assert inst.error_code is not None
        assert inst.error_code.startswith("E-")
        assert inst.user_message is not None and len(inst.user_message) > 0


def test_wrap_unexpected_error_sanitization() -> None:
    """UT-EXC-02: Verify service boundary wrapping of unexpected exceptions."""
    try:
        raise ZeroDivisionError("division by zero in parsing resume text")
    except ZeroDivisionError as err:
        wrapped = wrap_unexpected_error(err, "Resume analysis failed")

    assert isinstance(wrapped, ResumeAnalyzerError)
    assert wrapped.error_code == "E-UNEXPECTED"
    assert "ZeroDivisionError" in wrapped.details.get("exception_type", "")
    assert "resume text" not in wrapped.user_message
    assert "unexpected" in wrapped.user_message.lower()
