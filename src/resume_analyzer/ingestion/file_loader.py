"""Resume file loader combining validation, extraction, and character bounds (FR-01, FR-02).

Enforces length limits, detects scanned PDFs (no text layer), and guarantees
in-memory processing without writing untrusted uploads to disk.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from resume_analyzer.config.settings import FileSettings
from resume_analyzer.exceptions import EmptyResumeError
from resume_analyzer.ingestion.file_validator import ValidatedFile, validate_upload
from resume_analyzer.ingestion.text_extractors import extract_text
from resume_analyzer.models.candidate import ParseWarning

logger = logging.getLogger(__name__)


class LoadedResume(BaseModel):
    """Container holding validated metadata, extracted raw text, and ingestion warnings.

    Attributes:
        validated_file: Cryptographically verified file descriptor.
        raw_text: Extracted plain text content.
        warnings: Ingestion-stage diagnostic warnings (e.g. TEXT_TRUNCATED).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    validated_file: ValidatedFile
    raw_text: str
    warnings: list[ParseWarning] = Field(default_factory=list)


def load_resume(
    filename: str,
    data: bytes,
    settings: FileSettings,
) -> LoadedResume:
    """Validate upload payload and extract raw resume text into memory.

    Never persists incoming files to disk.

    Args:
        filename: Declared upload filename (untrusted user input).
        data: Raw byte payload.
        settings: Active file constraints and safety configuration.

    Returns:
        LoadedResume with validated metadata and extracted raw text.

    Raises:
        EmptyFileError: If file is 0 bytes.
        FileTooLargeError: If file size or page count exceeds limits.
        UnsupportedFileTypeError: If file extension is disallowed.
        FileTypeMismatchError: If file header contradicts extension.
        EncryptedFileError: If file is password protected.
        UnsafeArchiveError: If archive bounds or compression ratios are violated.
        UnreadableFileError: If file is structurally corrupted.
        EmptyResumeError: If no text could be extracted or text is below min_text_chars.
    """
    # 1. Validate file extension, size, magic bytes, archive bounds, and encryption
    validated_file = validate_upload(filename, data, settings)

    # 2. Extract text across PDF, DOCX, or TXT
    raw_text = extract_text(validated_file, data, max_pages=settings.max_pdf_pages)
    stripped = raw_text.strip()

    # 3. Detect empty or scanned resumes (no OCR support)
    if not stripped:
        raise EmptyResumeError(
            "No readable text found. Scanned documents are not supported (no OCR)."
        )

    # 4. Enforce minimum character threshold
    if len(stripped) < settings.min_text_chars:
        raise EmptyResumeError(
            f"Extracted resume text is too short ({len(stripped)} chars; "
            f"minimum required: {settings.min_text_chars}). "
            "Scanned documents or documents with insufficient text are not supported."
        )

    warnings: list[ParseWarning] = []

    # 5. Enforce maximum character threshold (truncate with warning)
    if len(raw_text) > settings.max_text_chars:
        raw_text = raw_text[: settings.max_text_chars]
        warnings.append(
            ParseWarning(
                code="TEXT_TRUNCATED",
                message=f"Resume text truncated to {settings.max_text_chars} character limit.",
                field="raw_text",
            )
        )
        logger.warning(
            "Truncated text for cid=%s to %d characters.",
            validated_file.candidate_id,
            settings.max_text_chars,
        )

    return LoadedResume(
        validated_file=validated_file,
        raw_text=raw_text,
        warnings=warnings,
    )
