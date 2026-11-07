"""Secure file ingestion, validation, and text extraction package."""

from __future__ import annotations

from resume_analyzer.ingestion.file_loader import LoadedResume, load_resume
from resume_analyzer.ingestion.file_validator import ValidatedFile, validate_upload
from resume_analyzer.ingestion.text_extractors import (
    extract_docx_text,
    extract_pdf_text,
    extract_text,
    extract_txt_text,
)

__all__ = [
    "LoadedResume",
    "ValidatedFile",
    "extract_docx_text",
    "extract_pdf_text",
    "extract_text",
    "extract_txt_text",
    "load_resume",
    "validate_upload",
]
