"""Unit tests for secure file handling, validation, and text extraction (UT-FILE-01..11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resume_analyzer.config.settings import FileSettings
from resume_analyzer.exceptions import (
    EmptyFileError,
    EmptyResumeError,
    EncryptedFileError,
    FileTooLargeError,
    FileTypeMismatchError,
    UnreadableFileError,
    UnsafeArchiveError,
    UnsupportedFileTypeError,
)
from resume_analyzer.ingestion.file_loader import load_resume
from resume_analyzer.ingestion.file_validator import validate_upload
from resume_analyzer.ingestion.text_extractors import (
    extract_txt_text,
)
from tests.data.generate_fixtures import (
    create_encrypted_pdf,
    create_macro_docx,
    create_scanned_image_pdf,
    create_zip_bomb_docx,
)


def test_valid_files_extraction_and_loading(tmp_path: Path) -> None:
    """UT-FILE-01: Valid PDF, DOCX, TXT files validate and yield expected text."""
    settings = FileSettings()

    # 1. Valid TXT
    txt_path = Path("tests/data/resumes/valid_resume.txt")
    txt_bytes = txt_path.read_bytes()
    loaded_txt = load_resume("candidate_verma.txt", txt_bytes, settings)
    assert loaded_txt.validated_file.format == "txt"
    assert "Asha Verma" in loaded_txt.raw_text
    assert "Python" in loaded_txt.raw_text
    assert len(loaded_txt.warnings) == 0

    # 2. Valid PDF
    pdf_path = Path("tests/data/resumes/valid_resume.pdf")
    pdf_bytes = pdf_path.read_bytes()
    loaded_pdf = load_resume("resume_upload.pdf", pdf_bytes, settings)
    assert loaded_pdf.validated_file.format == "pdf"
    assert "Asha Verma" in loaded_pdf.raw_text
    assert "SQL" in loaded_pdf.raw_text

    # 3. Valid DOCX
    docx_path = Path("tests/data/resumes/valid_resume.docx")
    docx_bytes = docx_path.read_bytes()
    loaded_docx = load_resume("profile.docx", docx_bytes, settings)
    assert loaded_docx.validated_file.format == "docx"
    assert "Asha Verma" in loaded_docx.raw_text
    assert "Docker" in loaded_docx.raw_text


def test_unsupported_file_types_rejected() -> None:
    """UT-FILE-02: Unsupported extensions and double extensions raise UnsupportedFileTypeError."""
    settings = FileSettings()
    dummy_bytes = b"Sample resume payload that is sufficiently long for testing."

    unsupported_names = [
        "resume.exe",
        "resume.doc",
        "resume.docm",
        "resume.png",
        "resume_no_extension",
        "cv.pdf.exe",
        "profile.txt.vbs",
    ]

    for name in unsupported_names:
        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            validate_upload(name, dummy_bytes, settings)
        assert exc_info.value.error_code == "E-FILE-001"


def test_content_and_extension_mismatch_rejected() -> None:
    """UT-FILE-03: Magic byte mismatches raise FileTypeMismatchError."""
    settings = FileSettings()
    pdf_bytes = Path("tests/data/resumes/valid_resume.pdf").read_bytes()

    # 1. PDF bytes disguised with .docx extension
    with pytest.raises(FileTypeMismatchError) as exc_info:
        validate_upload("resume.docx", pdf_bytes, settings)
    assert exc_info.value.error_code == "E-FILE-006"

    # 2. Generic ZIP disguised as .pdf
    fake_pdf = b"PK\x03\x04" + b"\x00" * 50
    with pytest.raises(FileTypeMismatchError) as exc_info:
        validate_upload("resume.pdf", fake_pdf, settings)
    assert exc_info.value.error_code == "E-FILE-006"

    # 3. Binary executable disguised as .txt
    binary_txt = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
    with pytest.raises(FileTypeMismatchError) as exc_info:
        validate_upload("resume.txt", binary_txt, settings)
    assert exc_info.value.error_code == "E-FILE-006"


def test_file_size_limits() -> None:
    """UT-FILE-04: Size exceeding max_size_mb raises FileTooLargeError; exactly at limit is accepted."""
    custom_settings = FileSettings(max_size_mb=1)  # 1 MB = 1048576 bytes
    limit = 1 * 1024 * 1024

    # Exactly at limit (valid TXT)
    exact_bytes = b"A" * limit
    val_file = validate_upload("test.txt", exact_bytes, custom_settings)
    assert val_file.size_bytes == limit

    # One byte over limit
    over_bytes = b"A" * (limit + 1)
    with pytest.raises(FileTooLargeError) as exc_info:
        validate_upload("test.txt", over_bytes, custom_settings)
    assert exc_info.value.error_code == "E-FILE-002"


def test_zero_byte_file_raises_empty_file_error() -> None:
    """UT-FILE-05: Empty zero-byte files raise EmptyFileError."""
    settings = FileSettings()
    with pytest.raises(EmptyFileError) as exc_info:
        validate_upload("empty.txt", b"", settings)
    assert exc_info.value.error_code == "E-FILE-003"


def test_encrypted_pdf_rejected() -> None:
    """UT-FILE-06: Password protected / encrypted PDF raises EncryptedFileError."""
    settings = FileSettings()
    enc_pdf = create_encrypted_pdf()
    with pytest.raises(EncryptedFileError) as exc_info:
        validate_upload("secret.pdf", enc_pdf, settings)
    assert exc_info.value.error_code == "E-FILE-005"


def test_corrupt_files_and_scanned_pdf() -> None:
    """UT-FILE-07: Corrupt files raise UnreadableFileError; scanned-image PDF raises EmptyResumeError."""
    settings = FileSettings()

    # 1. Corrupt PDF header / body
    corrupt_pdf = b"%PDF-1.4\nCorrupted data without any valid PDF trailer or structure"
    with pytest.raises((UnreadableFileError, EmptyResumeError)):
        load_resume("corrupt.pdf", corrupt_pdf, settings)

    # 2. Corrupt DOCX
    corrupt_docx = b"PK\x03\x04" + b"Corrupted broken zip bytes"
    with pytest.raises(UnreadableFileError) as exc_info:
        validate_upload("corrupt.docx", corrupt_docx, settings)
    assert exc_info.value.error_code == "E-FILE-004"

    # 3. Scanned PDF (valid structure, but image-only / zero extracted text)
    scanned_pdf = create_scanned_image_pdf()
    with pytest.raises(EmptyResumeError) as exc_info:
        load_resume("scanned.pdf", scanned_pdf, settings)
    assert exc_info.value.error_code == "E-PARSE-001"
    assert "scanned" in exc_info.value.user_message.lower()


def test_unsafe_docx_archive_rejected() -> None:
    """UT-FILE-08: DOCX with macro or excessive compression ratio raises UnsafeArchiveError."""
    settings = FileSettings()

    # 1. Macro-enabled file with vbaProject.bin
    macro_bytes = create_macro_docx()
    with pytest.raises(UnsafeArchiveError) as exc_info:
        validate_upload("macro.docx", macro_bytes, settings)
    assert exc_info.value.error_code == "E-FILE-007"
    assert (
        "macro" in exc_info.value.user_message.lower()
        or "macro" in str(exc_info.value).lower()
    )

    # 2. Synthetic zip bomb with ratio > 100:1
    bomb_bytes = create_zip_bomb_docx()
    with pytest.raises(UnsafeArchiveError) as exc_info:
        validate_upload("bomb.docx", bomb_bytes, settings)
    assert exc_info.value.error_code == "E-FILE-007"


def test_path_like_filenames_and_safe_display_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UT-FILE-09: Path traversal in filenames neutralized; safe_display_name used; no leak in logs."""
    settings = FileSettings()
    txt_bytes = Path("tests/data/resumes/valid_resume.txt").read_bytes()

    dangerous_name = "../../sensitive/super_secret_cv.txt"
    val = validate_upload(dangerous_name, txt_bytes, settings)

    assert val.safe_display_name.startswith("candidate-")
    assert val.safe_display_name.endswith(".txt")
    assert "sensitive" not in val.safe_display_name
    assert "super_secret" not in val.safe_display_name
    assert ".." not in val.safe_display_name

    # Ensure dangerous original filename was not logged
    assert dangerous_name not in caplog.text


def test_txt_encodings_support() -> None:
    """UT-FILE-10: TXT with UTF-8, UTF-8-BOM, CP-1252, and Latin-1 decodes without error."""
    text_sample = "Candidate: Renée Dupont — Expert in C++ & Python."

    # UTF-8 with BOM
    bom_bytes = text_sample.encode("utf-8-sig")
    assert extract_txt_text(bom_bytes) == text_sample

    # Standard UTF-8
    utf8_bytes = text_sample.encode("utf-8")
    assert extract_txt_text(utf8_bytes) == text_sample

    # CP-1252 (supports em-dash \u2014)
    cp1252_bytes = text_sample.encode("cp1252")
    assert "Renée Dupont" in extract_txt_text(cp1252_bytes)

    # Latin-1 (standard ISO-8859-1 range)
    latin_sample = "Candidate: Renée Dupont - Expert in C++ & Python."
    latin_bytes = latin_sample.encode("latin-1")
    assert "Renée Dupont" in extract_txt_text(latin_bytes)


def test_character_limits_and_no_disk_writes(tmp_path: Path) -> None:
    """UT-FILE-11: Length limits enforced (truncation & min chars); no files written during load."""
    settings = FileSettings(min_text_chars=50, max_text_chars=100)

    # 1. Text below min_text_chars -> EmptyResumeError
    short_text = "Too short resume."
    with pytest.raises(EmptyResumeError) as exc_info:
        load_resume("short.txt", short_text.encode("utf-8"), settings)
    assert exc_info.value.error_code == "E-PARSE-001"

    # 2. Text above max_text_chars -> Truncated with TEXT_TRUNCATED warning
    long_text = "Python Developer " * 20  # ~340 characters
    loaded = load_resume("long.txt", long_text.encode("utf-8"), settings)
    assert len(loaded.raw_text) == 100
    assert len(loaded.warnings) == 1
    assert loaded.warnings[0].code == "TEXT_TRUNCATED"

    # 3. Assert no files were written to disk
    # We inspect the current workspace and tmp_path; load_resume must not create files
    files_before = list(tmp_path.glob("**/*"))
    load_resume("in_memory.txt", ("Asha Verma " * 10).encode("utf-8"), settings)
    files_after = list(tmp_path.glob("**/*"))
    assert files_before == files_after
