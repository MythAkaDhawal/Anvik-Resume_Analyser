"""Integration tests for exporters (IT-05).

Runs end-to-end analysis on a sample resume, exports HTML, PDF, and Excel,
and re-opens each generated file to assert that scores, candidates, and matched skills match.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import openpyxl
from pypdf import PdfReader

from resume_analyzer.config.settings import get_settings
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.reporting.exporters.base import get_exporter
from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService


def test_it_05_export_all_formats_and_verify(
    tmp_path: Path,
    reference_date: date,
) -> None:
    """Assert all 3 formats (HTML, PDF, Excel) are produced and match analysis report values (IT-05)."""
    settings = get_settings()
    service = AnalysisService(settings=settings)

    job = JobRequirements(
        job_id="junior-data-analyst",
        job_title="Junior Data Analyst",
        required_skills=["Python", "SQL"],
        optional_skills=["Docker", "AWS"],
        min_experience_years=1.0,
    )

    resume_path = Path("tests/data/resumes/cand_01_asha_verma.txt")
    opts = AnalysisOptions(strategy="weighted", ai_features=set())
    report = service.analyze(
        filename=resume_path.name,
        data=resume_path.read_bytes(),
        job=job,
        options=opts,
        reference_date=reference_date,
    )

    score_str = f"{report.score.total_score:.1f}"
    cand_name = report.candidate.name or "Asha Verma"

    # 1. HTML Export & Verification
    html_exporter = get_exporter("html")
    html_path = tmp_path / "analysis_report.html"
    html_exporter.export(report, html_path)
    assert html_path.exists()
    html_text = html_path.read_text(encoding="utf-8")
    assert cand_name in html_text
    assert score_str in html_text
    assert "Python" in html_text
    assert "SQL" in html_text

    # 2. PDF Export & Verification
    pdf_exporter = get_exporter("pdf")
    pdf_path = tmp_path / "analysis_report.pdf"
    pdf_exporter.export(report, pdf_path)
    assert pdf_path.exists()
    pdf_reader = PdfReader(str(pdf_path))
    assert len(pdf_reader.pages) >= 1
    pdf_text = ""
    for p in pdf_reader.pages:
        pdf_text += p.extract_text() or ""
    assert cand_name in pdf_text
    assert score_str in pdf_text

    # 3. Excel Export & Verification
    excel_exporter = get_exporter("xlsx")
    excel_path = tmp_path / "analysis_report.xlsx"
    excel_exporter.export(report, excel_path)
    assert excel_path.exists()
    wb = openpyxl.load_workbook(excel_path)
    assert "Summary" in wb.sheetnames
    assert "Skills" in wb.sheetnames

    summary_sheet = wb["Summary"]
    found_score = False
    for row in summary_sheet.iter_rows(values_only=True):
        if row[1] == "Total Score":
            assert abs(float(row[2]) - report.score.total_score) < 0.01
            found_score = True
            break
    assert found_score, "Score value was not found in Excel Summary sheet"

    skills_sheet = wb["Skills"]
    skills_found = [row[0] for row in skills_sheet.iter_rows(values_only=True)]
    assert "Python" in skills_found
    assert "SQL" in skills_found
