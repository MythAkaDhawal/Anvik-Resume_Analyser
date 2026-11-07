"""Raw text extractors for PDF, DOCX, and TXT resume files (FR-02).

Dispatches by validated file format and handles library errors and encoding fallbacks.
"""

from __future__ import annotations

import io
import logging
import re
from typing import TYPE_CHECKING
import xml.etree.ElementTree as ET
import zipfile
import zlib

from resume_analyzer.exceptions import UnreadableFileError

if TYPE_CHECKING:
    from resume_analyzer.ingestion.file_validator import ValidatedFile

logger = logging.getLogger(__name__)

# WordprocessingML XML namespace
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def extract_txt_text(data: bytes) -> str:
    """Extract raw string from TXT bytes using standard fallback encodings.

    Order of attempts: UTF-8 with BOM (utf-8-sig), UTF-8, CP-1252, Latin-1.

    Args:
        data: Raw text file bytes.

    Returns:
        Decoded string.
    """
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def extract_docx_text(data: bytes) -> str:
    """Extract text from DOCX body paragraphs and table cells.

    Uses python-docx if installed, with a robust zipfile + XML fallback.

    Args:
        data: Raw DOCX file bytes.

    Returns:
        Extracted body text in reading order.

    Raises:
        UnreadableFileError: If archive or XML structure cannot be parsed.
    """
    # 1. Try python-docx if available
    try:
        import docx

        try:
            doc = docx.Document(io.BytesIO(data))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells]
                    if any(row_cells):
                        tables_text.append("\t".join(row_cells))
            combined = "\n".join(paragraphs + tables_text)
            return combined
        except Exception as err:
            logger.warning("python-docx extraction failed, trying XML fallback: %s", err)
    except ImportError:
        pass

    # 2. Pure Python zipfile + ElementTree fallback
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml_bytes = zf.read("word/document.xml")
            root = ET.fromstring(xml_bytes)

            body = root.find(f"{{{W_NS}}}body")
            if body is None:
                return ""

            lines: list[str] = []
            for child in body:
                tag = child.tag
                if tag == f"{{{W_NS}}}p":
                    # Body paragraph
                    p_text = "".join(
                        elem.text
                        for elem in child.iter(f"{{{W_NS}}}t")
                        if elem.text
                    ).strip()
                    if p_text:
                        lines.append(p_text)
                elif tag == f"{{{W_NS}}}tbl":
                    # Table in document body
                    for row in child.iter(f"{{{W_NS}}}tr"):
                        row_cells = []
                        for cell in row.iter(f"{{{W_NS}}}tc"):
                            cell_text = " ".join(
                                elem.text
                                for elem in cell.iter(f"{{{W_NS}}}t")
                                if elem.text
                            ).strip()
                            row_cells.append(cell_text)
                        if any(row_cells):
                            lines.append("\t".join(row_cells))

            return "\n".join(lines)
    except Exception as err:
        raise UnreadableFileError(f"Could not parse DOCX contents: {err}") from err


def extract_pdf_text(data: bytes, max_pages: int = 20) -> str:
    """Extract text from PDF pages up to max_pages limit.

    Tries pdfplumber first, falls back to pypdf, and provides a pure-Python
    stream decoder when external libraries are not present.

    Args:
        data: Raw PDF file bytes.
        max_pages: Maximum number of pages to extract.

    Returns:
        Extracted text with pages delimited by double newlines.

    Raises:
        UnreadableFileError: If PDF structure is unreadable or corrupted.
    """
    # 1. Try pdfplumber
    try:
        import pdfplumber

        try:
            pages_text: list[str] = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages[:max_pages]:
                    pt = page.extract_text() or ""
                    pages_text.append(pt)
            return "\n\n".join(pages_text)
        except Exception as err:
            logger.warning("pdfplumber failed, falling back to pypdf: %s", err)
    except ImportError:
        pass

    # 2. Try pypdf fallback
    try:
        import pypdf

        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages_text = []
            for page in reader.pages[:max_pages]:
                pt = page.extract_text() or ""
                pages_text.append(pt)
            return "\n\n".join(pages_text)
        except Exception as err:
            logger.warning("pypdf extraction failed, falling back to stream decoder: %s", err)
    except ImportError:
        pass

    # 3. Pure Python PDF stream extractor
    try:
        return _fallback_extract_pdf_streams(data, max_pages)
    except Exception as err:
        raise UnreadableFileError(f"Failed to extract text from PDF: {err}") from err


def _fallback_extract_pdf_streams(data: bytes, max_pages: int = 20) -> str:
    """Extract text chunks from uncompressed or FlateDecode PDF stream objects."""
    extracted_chunks: list[str] = []

    # Find stream objects: "stream\r?\n(.*?)\r?\nendstream"
    stream_matches = list(re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL))

    for match in stream_matches[: max_pages * 5]:
        raw_stream = match.group(1)
        decompressed: bytes
        try:
            decompressed = zlib.decompress(raw_stream)
        except Exception:
            decompressed = raw_stream

        # Extract literal text operators: (string) Tj or ' or "
        tj_matches = re.findall(rb"\((.*?)\)\s*(?:Tj|'|\")", decompressed)
        for chunk in tj_matches:
            try:
                text_chunk = chunk.decode("utf-8")
            except UnicodeDecodeError:
                text_chunk = chunk.decode("latin-1", errors="replace")
            # Unescape PDF literal string escapes
            text_chunk = text_chunk.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
            if text_chunk.strip():
                extracted_chunks.append(text_chunk)

        # Extract array text operators: [(s1) 12 (s2)] TJ
        tj_array_matches = re.findall(rb"\[(.*?)\]\s*TJ", decompressed, re.DOTALL)
        for arr in tj_array_matches:
            elements = re.findall(rb"\((.*?)\)", arr)
            combined = "".join(
                elem.decode("latin-1", errors="replace").replace(r"\(", "(").replace(r"\)", ")")
                for elem in elements
            )
            if combined.strip():
                extracted_chunks.append(combined)

    return "\n".join(extracted_chunks)


def extract_text(
    file: ValidatedFile,
    data: bytes,
    max_pages: int = 20,
) -> str:
    """Dispatch text extraction to the appropriate parser for the validated format.

    Args:
        file: ValidatedFile descriptor containing detected format.
        data: Raw file byte content in memory.
        max_pages: Maximum pages to process for PDF documents.

    Returns:
        Extracted raw text.

    Raises:
        UnreadableFileError: If file extraction encounters a parsing error.
    """
    if file.format == "pdf":
        return extract_pdf_text(data, max_pages=max_pages)
    if file.format == "docx":
        return extract_docx_text(data)
    if file.format == "txt":
        return extract_txt_text(data)

    raise UnreadableFileError(f"Unsupported format '{file.format}' for text extraction.")
