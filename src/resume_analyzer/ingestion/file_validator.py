"""File validation and security checks for resume ingestion (FR-01, NFR-10).

Validates file extensions, size bounds, magic bytes, archive decompression ratios,
macro exclusion, and PDF encryption without persisting files to disk.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from resume_analyzer.config.settings import FileSettings
from resume_analyzer.exceptions import (
    EmptyFileError,
    EncryptedFileError,
    FileTooLargeError,
    FileTypeMismatchError,
    UnreadableFileError,
    UnsafeArchiveError,
    UnsupportedFileTypeError,
)

logger = logging.getLogger(__name__)


class ValidatedFile(BaseModel):
    """Immutable metadata descriptor representing a safely validated file.

    Attributes:
        format: Normalized file format ('pdf', 'docx', 'txt').
        sha256: 64-character SHA-256 cryptographic digest of raw file bytes.
        candidate_id: First 12 hexadecimal characters of SHA-256 digest.
        size_bytes: Total size of file in bytes.
        safe_display_name: Neutral filename in format 'candidate-<sha12>.<ext>'.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    format: Literal["pdf", "docx", "txt"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: str = Field(pattern=r"^[0-9a-f]{12}$")
    size_bytes: int = Field(gt=0)
    safe_display_name: str


def validate_upload(
    filename: str,
    data: bytes,
    settings: FileSettings,
) -> ValidatedFile:
    """Validate raw file bytes against format, size, magic bytes, and safety limits.

    The original filename is only used to extract the declared extension and is
    never logged or persisted.

    Args:
        filename: Declared upload filename (untrusted user input).
        data: Raw file byte payload in memory.
        settings: Active file constraints and safety configuration.

    Returns:
        ValidatedFile containing safe metadata and derived identifier.

    Raises:
        EmptyFileError: If byte payload is empty (0 bytes).
        FileTooLargeError: If payload exceeds configured max_size_mb or PDF page limit.
        UnsupportedFileTypeError: If extension is not permitted.
        FileTypeMismatchError: If magic bytes or file internals contradict extension.
        EncryptedFileError: If PDF document is password-protected.
        UnsafeArchiveError: If DOCX structure exceeds zip-bomb safety thresholds.
        UnreadableFileError: If file is corrupted or structurally broken.
    """
    # 1. Non-empty check
    if not data or len(data) == 0:
        raise EmptyFileError("Uploaded file is empty (0 bytes).")

    # 2. File size bound check
    max_bytes = settings.max_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise FileTooLargeError(
            f"File size ({len(data)} bytes) exceeds limit of {settings.max_size_mb} MB.",
            max_size_mb=settings.max_size_mb,
        )

    # 3. Extension allow-list check (inspect only the final suffix)
    path_obj = Path(filename)
    raw_suffix = path_obj.suffix.lower()
    allowed = {ext.lower() for ext in settings.allowed_extensions}

    if not raw_suffix or raw_suffix not in allowed:
        raise UnsupportedFileTypeError(
            f"File extension '{raw_suffix}' is not permitted. Allowed: {sorted(allowed)}."
        )

    fmt_map = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}
    fmt = fmt_map[raw_suffix]

    # 4. Content and magic byte verification per format
    if fmt == "pdf":
        _validate_pdf(data, settings)
    elif fmt == "docx":
        _validate_docx(data, settings)
    elif fmt == "txt":
        _validate_txt(data)

    # 5. Compute cryptographic hash and neutral display name
    sha256_hex = hashlib.sha256(data).hexdigest()
    candidate_id = sha256_hex[:12]
    safe_name = f"candidate-{candidate_id}{raw_suffix}"

    logger.debug(
        "Validated upload successfully: cid=%s fmt=%s size=%d",
        candidate_id,
        fmt,
        len(data),
    )

    return ValidatedFile(
        format=fmt,  # type: ignore[arg-type]
        sha256=sha256_hex,
        candidate_id=candidate_id,
        size_bytes=len(data),
        safe_display_name=safe_name,
    )


def _validate_pdf(data: bytes, settings: FileSettings) -> None:
    """Validate PDF magic bytes, encryption state, and page limits."""
    # Magic bytes check: %PDF- within the first 1024 bytes
    header_window = data[:1024]
    if b"%PDF-" not in header_window:
        raise FileTypeMismatchError("PDF header magic bytes '%PDF-' not found in file.")

    # Try validating via pypdf if installed
    try:
        import pypdf

        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise EncryptedFileError("PDF file is password-protected or encrypted.")

            page_count = len(reader.pages)
            if page_count > settings.max_pdf_pages:
                raise FileTooLargeError(
                    f"PDF contains {page_count} pages, exceeding limit of {settings.max_pdf_pages} pages.",
                    max_size_mb=settings.max_size_mb,
                )
            return
        except EncryptedFileError:
            raise
        except FileTooLargeError:
            raise
        except Exception as err:
            raise UnreadableFileError(
                f"Corrupted or invalid PDF document: {err}"
            ) from err
    except ImportError:
        # Fallback inspection without external library
        _fallback_validate_pdf(data, settings)


def _fallback_validate_pdf(data: bytes, settings: FileSettings) -> None:
    """Fallback standard-library validator for PDF when pypdf is not installed."""
    # Check for /Encrypt entry in trailer / catalog
    # Regex checks for /Encrypt followed by object reference or dict
    if re.search(rb"/Encrypt\s+(\d+\s+\d+\s+R|<<)", data):
        raise EncryptedFileError("PDF file is password-protected or encrypted.")

    # Page count check via /Type /Page entries
    # Match /Type /Page\b but not /Type /Pages
    page_matches = re.findall(rb"/Type\s*/Page\b", data)
    page_count = len(page_matches)
    if page_count > settings.max_pdf_pages:
        raise FileTooLargeError(
            f"PDF contains {page_count} pages, exceeding limit of {settings.max_pdf_pages} pages.",
            max_size_mb=settings.max_size_mb,
        )


def _check_docx_infolist_safety(
    infolist: list[zipfile.ZipInfo],
    max_uncompressed_bytes: int,
    max_uncompressed_mb: int,
) -> None:
    """Validate archive member counts, individual compression ratios, and total size."""
    if len(infolist) > 2000:
        raise UnsafeArchiveError(
            f"Archive member count ({len(infolist)}) exceeds safety limit of 2000 entries."
        )

    total_uncompressed = 0
    for info in infolist:
        total_uncompressed += info.file_size
        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > 100:
                raise UnsafeArchiveError(
                    f"Archive member '{info.filename}' compression ratio ({ratio:.1f}:1) exceeds safety limit of 100:1."
                )
        elif info.file_size > 1024:
            raise UnsafeArchiveError(
                f"Archive member '{info.filename}' has excessive uncompressed size with zero compression."
            )

    if total_uncompressed > max_uncompressed_bytes:
        raise UnsafeArchiveError(
            f"Total uncompressed size ({total_uncompressed / (1024 * 1024):.1f} MB) "
            f"exceeds limit of {max_uncompressed_mb} MB."
        )


def _validate_docx(data: bytes, settings: FileSettings) -> None:
    """Validate DOCX zip archive safety, structure, and compression ratios."""
    # Check ZIP local file header signature PK\x03\x04
    if not data.startswith(b"PK\x03\x04"):
        raise FileTypeMismatchError(
            "DOCX file does not begin with ZIP signature PK\\x03\\x04."
        )

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())

            # Structure check: Must contain word/document.xml
            if "word/document.xml" not in names:
                raise FileTypeMismatchError(
                    "ZIP archive is not a valid DOCX (missing word/document.xml)."
                )

            # Security check: Macro-enabled rejection
            for name in names:
                if name.endswith("vbaProject.bin") or "vba" in name.lower():
                    raise UnsafeArchiveError(
                        "Macro-enabled DOCX files (vbaProject.bin) are not permitted."
                    )

            max_uncompressed = settings.max_docx_uncompressed_mb * 1024 * 1024
            _check_docx_infolist_safety(
                zf.infolist(),
                max_uncompressed,
                settings.max_docx_uncompressed_mb,
            )

    except (zipfile.BadZipFile, zipfile.LargeZipFile) as err:
        raise UnreadableFileError(f"Corrupted or invalid DOCX archive: {err}") from err
    except (UnsafeArchiveError, FileTypeMismatchError):
        raise
    except Exception as err:
        raise UnreadableFileError(f"Error inspecting DOCX structure: {err}") from err


def _validate_txt(data: bytes) -> None:
    """Validate TXT file for absence of binary NUL bytes and decode capability."""
    # Fast binary check: NUL byte in the first 8 KB
    if b"\x00" in data[:8192]:
        raise FileTypeMismatchError(
            "Binary NUL bytes detected in TXT file; binary files are not supported."
        )

    # Verification of decodability across supported standard encodings
    decoded = False
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            data.decode(encoding)
            decoded = True
            break
        except UnicodeDecodeError:
            continue

    if not decoded:
        raise FileTypeMismatchError(
            "TXT file could not be decoded with standard text encodings."
        )
