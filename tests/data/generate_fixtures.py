"""Utility script to generate realistic synthetic PDF and DOCX resume fixtures."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path


def create_minimal_pdf(text_lines: list[str]) -> bytes:
    """Generate a minimal valid PDF containing the given lines of text."""
    stream_content = "BT\n/F1 12 Tf\n72 712 Td\n"
    for line in text_lines:
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_content += f"({safe_line}) Tj\n0 -20 Td\n"
    stream_content += "ET\n"
    stream_bytes = stream_content.encode("latin-1")

    obj5 = (
        b"5 0 obj\n<< /Length "
        + str(len(stream_bytes)).encode("ascii")
        + b" >>\nstream\n"
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )

    header = b"%PDF-1.4\n"
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n"
    )
    obj4 = b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    body = header
    offsets = []
    for obj in (obj1, obj2, obj3, obj4, obj5):
        offsets.append(len(body))
        body += obj

    startxref = len(body)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode("ascii")
    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(startxref).encode("ascii")
        + b"\n%%EOF\n"
    )
    return body + xref + trailer


def create_minimal_docx(paragraphs: list[str]) -> bytes:
    """Generate a minimal valid DOCX containing the given paragraphs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
            "</Relationships>",
        )
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '<Default Extension="xml" ContentType="application/xml"/>\n'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
            "</Types>",
        )
        p_xml = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
            f"<w:body>{p_xml}</w:body>\n"
            "</w:document>"
        )
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


def create_encrypted_pdf() -> bytes:
    """Generate a valid PDF encrypted with a password."""
    try:
        import pypdf

        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.encrypt("secret_password")
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    except Exception:
        content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"trailer\n<< /Size 4 /Root 1 0 R /Encrypt << /Filter /Standard /V 1 /R 2 /P -4 >> >>\n"
            b"%%EOF\n"
        )
        return content


def create_scanned_image_pdf() -> bytes:
    """Generate a valid PDF containing no text streams (image only)."""
    try:
        import pypdf

        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception:
        content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
            b"%%EOF\n"
        )
        return content


def create_macro_docx() -> bytes:
    """Generate a DOCX archive containing a forbidden vbaProject.bin macro."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "<w:document><w:body/></w:document>")
        zf.writestr("word/vbaProject.bin", b"DUMMY_MACRO_PAYLOAD")
    return buf.getvalue()


def create_zip_bomb_docx() -> bytes:
    """Generate a small synthetic DOCX with an abnormal decompression ratio (> 100:1)."""
    buf = io.BytesIO()
    # 200 KB of zeros compresses to ~200 bytes (ratio ~ 1000:1)
    large_zeros = b"0" * 250000
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "<w:document><w:body/></w:document>")
        zf.writestr("word/padding.xml", large_zeros)
    return buf.getvalue()


if __name__ == "__main__":
    resumes_dir = Path("tests/data/resumes")
    resumes_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "Asha Verma",
        "Email: asha.verma@example.com",
        "Summary: Junior Data Analyst with 2 years experience in Python, SQL, and data reporting.",
        "Skills: Python, SQL, Pandas, Tableau, Docker, AWS",
        "Experience: Data Analyst Intern at DataCorp Inc (June 2023 - Present)",
        "Education: Bachelor of Science in Computer Science, State University",
    ]

    pdf_bytes = create_minimal_pdf(lines)
    (resumes_dir / "valid_resume.pdf").write_bytes(pdf_bytes)

    docx_bytes = create_minimal_docx(lines)
    (resumes_dir / "valid_resume.docx").write_bytes(docx_bytes)

    (resumes_dir / "empty_resume.txt").write_bytes(b"")

    print("Fixtures generated in tests/data/resumes/")
