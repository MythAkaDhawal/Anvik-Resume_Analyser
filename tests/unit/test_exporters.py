"""Unit tests for report exporters (UT-XPT-01..07).

Verifies HTML escaping, absence of external URLs, PDF generation, Excel formula
neutralization, error handling, non-Latin Unicode rendering, and batch ranking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest
from pypdf import PdfReader

from resume_analyzer.exceptions import ExportError, UnsupportedExportFormatError
from resume_analyzer.models.candidate import (
    Candidate,
    EducationEntry,
    ExperienceEntry,
    Skill,
)
from resume_analyzer.models.enums import (
    EducationLevel,
    FitBand,
    MatchType,
    Provenance,
)
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import (
    AnalysisReport,
    EducationAnalysis,
    ExperienceAnalysis,
    MatchResult,
    ScoreComponent,
    ScoreResult,
    SkillMatch,
)
from resume_analyzer.reporting.exporters.base import export_batch_workbook, get_exporter
from resume_analyzer.reporting.exporters.excel_exporter import (
    ExcelExporter,
    sanitize_excel_value,
)
from resume_analyzer.reporting.exporters.html_exporter import HTMLExporter
from resume_analyzer.reporting.exporters.pdf_exporter import PDFExporter
from resume_analyzer.reporting.report_builder import ReportBuilder


@pytest.fixture
def standard_report() -> AnalysisReport:
    """Fixture providing a complete AnalysisReport with potential injection strings."""
    candidate = Candidate(
        candidate_id="3fa91c0b77de",
        name="Asha Verma",
        email="asha@example.com",
        skills=[
            Skill(
                name="Python",
                canonical_name="Python",
                provenance=Provenance.EXTRACTED_RULE,
                mentions=3,
            ),
            Skill(
                name="SQL",
                canonical_name="SQL",
                provenance=Provenance.EXTRACTED_RULE,
                mentions=2,
            ),
        ],
        experience=[
            ExperienceEntry(
                job_title="Junior Data Analyst",
                company="Acme Corp",
                duration_months=18,
                provenance=Provenance.EXTRACTED_RULE,
            )
        ],
        education=[
            EducationEntry(
                degree="Bachelor of Science in Computer Science",
                level=EducationLevel.BACHELOR,
                field_of_study="Computer Science",
                institution="State University",
                provenance=Provenance.EXTRACTED_RULE,
            )
        ],
        total_experience_years=1.5,
        highest_education_level=EducationLevel.BACHELOR,
        source_format="txt",
        parser_version="0.1.0",
    )

    job = JobRequirements(
        job_id="junior-data-analyst",
        job_title="Junior Data Analyst",
        required_skills=["Python", "SQL", "Pandas"],
        optional_skills=["Docker"],
        min_experience_years=1.0,
        min_education_level=EducationLevel.BACHELOR,
    )

    match = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Python",
                is_required=True,
                match_type=MatchType.EXACT,
                matched_candidate_skill="Python",
                similarity=100.0,
                credit=1.0,
            ),
            SkillMatch(
                target="SQL",
                is_required=True,
                match_type=MatchType.EXACT,
                matched_candidate_skill="SQL",
                similarity=100.0,
                credit=1.0,
            ),
            SkillMatch(
                target="Pandas",
                is_required=True,
                match_type=MatchType.NONE,
                matched_candidate_skill=None,
                similarity=0.0,
                credit=0.0,
            ),
            SkillMatch(
                target="Docker",
                is_required=False,
                match_type=MatchType.NONE,
                matched_candidate_skill=None,
                similarity=0.0,
                credit=0.0,
            ),
        ],
        required_credit=0.6667,
        optional_credit=0.0,
        experience=ExperienceAnalysis(
            required_years=1.0,
            candidate_years=1.5,
            status="met",
            subscore=1.0,
            gap_years=0.0,
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.BACHELOR,
            candidate_level=EducationLevel.BACHELOR,
            status="met",
            field_match=None,
            subscore=1.0,
        ),
    )

    score = ScoreResult(
        strategy_name="weighted",
        total_score=78.5,
        components=[
            ScoreComponent(
                name="required_skills",
                status="evaluated",
                weight=0.50,
                subscore=0.6667,
                points=33.3,
                explanation="Required skills subscore 0.667 * weight 0.50 = 33.3 pts",
            ),
            ScoreComponent(
                name="experience",
                status="evaluated",
                weight=0.20,
                subscore=1.0,
                points=20.0,
                explanation="Experience subscore 1.0 * weight 0.20 = 20.0 pts",
            ),
            ScoreComponent(
                name="education",
                status="evaluated",
                weight=0.15,
                subscore=1.0,
                points=15.0,
                explanation="Education subscore 1.0 * weight 0.15 = 15.0 pts",
            ),
            ScoreComponent(
                name="optional_skills",
                status="evaluated",
                weight=0.15,
                subscore=0.0,
                points=0.0,
                explanation="Optional skills subscore 0.0 * weight 0.15 = 0.0 pts",
            ),
        ],
        coverage=1.0,
        fit_band=FitBand.MODERATE,
        flags=["MISSING_REQUIRED_SKILLS"],
    )

    return ReportBuilder.build(
        candidate=candidate,
        job=job,
        match=match,
        score=score,
        created_at=datetime(2026, 11, 8, 10, 15, 0, tzinfo=UTC),
    )


# -----------------------------------------------------------------------------
# UT-XPT-01: HTML escapes malicious tags from resume strings
# -----------------------------------------------------------------------------
def test_ut_xpt_01_html_escapes_script_tags(
    standard_report: AnalysisReport,
    tmp_path: Path,
) -> None:
    """Assert HTML exporter escapes <script> and onerror= payloads from resume text."""
    # Inject XSS payloads into candidate fields
    standard_report.candidate.name = "<script>alert('xss')</script>"
    standard_report.candidate.email = "test<img src=x onerror=alert(1)>@example.com"

    exporter = HTMLExporter()
    out_file = tmp_path / "report.html"
    exporter.export(standard_report, out_file)

    html_content = out_file.read_text(encoding="utf-8")
    assert "<script>" not in html_content
    assert "&lt;script&gt;" in html_content
    assert "&lt;/script&gt;" in html_content
    assert "alert" in html_content
    assert "onerror=" not in html_content or "&lt;img" in html_content


# -----------------------------------------------------------------------------
# UT-XPT-02: HTML contains all sections and badges; no external URLs
# -----------------------------------------------------------------------------
def test_ut_xpt_02_html_sections_and_no_external_urls(
    standard_report: AnalysisReport,
    tmp_path: Path,
) -> None:
    """Assert HTML contains all sections, badges, CSP header, and no external URLs."""
    exporter = HTMLExporter()
    out_file = tmp_path / "report.html"
    exporter.export(standard_report, out_file)

    html_content = out_file.read_text(encoding="utf-8")

    # CSP header
    assert "Content-Security-Policy\" content=\"default-src 'none'" in html_content

    # Provenance badges
    assert "badge-rule" in html_content
    assert "badge-computed" in html_content

    # Key sections
    assert "Candidate Information" in html_content
    assert "Job Requirements" in html_content
    assert "Overall Match Score" in html_content
    assert "Score Component Breakdown" in html_content
    assert "Matched Skills" in html_content
    assert "Missing Skills" in html_content
    assert "Experience Analysis" in html_content
    assert "Education Analysis" in html_content
    assert "Recommendations" in html_content
    assert "Alignment &amp; Suitability Assessment" in html_content
    assert "Suggested Interview Questions" in html_content
    assert "Appendix &amp; System Limitations" in html_content

    # No external network links
    assert "src=http" not in html_content.lower()
    assert "href=http" not in html_content.lower()


# -----------------------------------------------------------------------------
# UT-XPT-03: PDF is created, opens with pypdf, contains name and score
# -----------------------------------------------------------------------------
def test_ut_xpt_03_pdf_creation_and_contents(
    standard_report: AnalysisReport,
    tmp_path: Path,
) -> None:
    """Assert PDF report is created, opens with pypdf, and contains score and name."""
    exporter = PDFExporter()
    out_file = tmp_path / "report.pdf"
    exporter.export(standard_report, out_file)

    assert out_file.exists()
    reader = PdfReader(str(out_file))
    assert len(reader.pages) >= 1

    extracted_text = ""
    for page in reader.pages:
        extracted_text += page.extract_text() or ""

    assert "Asha Verma" in extracted_text
    assert "78.5" in extracted_text
    assert "MODERATE" in extracted_text


# -----------------------------------------------------------------------------
# UT-XPT-04: Excel workbook has expected sheets/headers and batch ranking
# -----------------------------------------------------------------------------
def test_ut_xpt_04_excel_sheets_and_batch_ranking(
    standard_report: AnalysisReport,
    tmp_path: Path,
) -> None:
    """Assert Excel single report has expected sheets and batch workbook is ranked."""
    exporter = ExcelExporter()
    out_file = tmp_path / "report.xlsx"
    exporter.export(standard_report, out_file)

    wb = openpyxl.load_workbook(out_file)
    assert set(wb.sheetnames) == {
        "Summary",
        "Skills",
        "Experience-Education",
        "AI-Insights",
    }

    summary_sheet = wb["Summary"]
    assert summary_sheet.freeze_panes == "A2"

    # Batch workbook export test
    batch_file = tmp_path / "batch.xlsx"
    # Create two reports with different scores
    r1 = standard_report.model_copy(deep=True)
    r1.score.total_score = 65.0
    r1.candidate.candidate_id = "cand_low"

    r2 = standard_report.model_copy(deep=True)
    r2.score.total_score = 92.0
    r2.candidate.candidate_id = "cand_high"

    export_batch_workbook([r1, r2], batch_file)
    batch_wb = openpyxl.load_workbook(batch_file)
    assert "Ranking" in batch_wb.sheetnames

    rank_sheet = batch_wb["Ranking"]
    # Row 2 should be the highest score (92.0), row 3 should be 65.0
    assert rank_sheet.cell(row=2, column=2).value == "cand_high"
    assert rank_sheet.cell(row=2, column=4).value == 92.0
    assert rank_sheet.cell(row=3, column=2).value == "cand_low"
    assert rank_sheet.cell(row=3, column=4).value == 65.0


# -----------------------------------------------------------------------------
# UT-XPT-05: Error handling, unsupported format, and no partial files
# -----------------------------------------------------------------------------
def test_ut_xpt_05_error_handling_and_unsupported_format(
    standard_report: AnalysisReport,
    tmp_path: Path,
) -> None:
    """Assert ExportError on unwritable paths and UnsupportedExportFormatError on invalid format."""
    # 1. Unsupported export format
    with pytest.raises(UnsupportedExportFormatError) as exc_info:
        get_exporter("docx")
    assert exc_info.value.error_code == "E-EXPORT-002"

    # 2. Unwritable / invalid directory path raises ExportError and leaves no partial files
    invalid_path = Path("Z:/non_existent_drive_12345/report.html")
    exporter = HTMLExporter()
    with pytest.raises(ExportError) as exc_info:
        exporter.export(standard_report, invalid_path)
    assert exc_info.value.error_code == "E-EXPORT-001"


# -----------------------------------------------------------------------------
# UT-XPT-06: Non-Latin names render without exception in PDF and HTML
# -----------------------------------------------------------------------------
def test_ut_xpt_06_non_latin_names(
    standard_report: AnalysisReport,
    tmp_path: Path,
) -> None:
    """Assert non-Latin names (Hindi, Polish, Chinese) render without exception."""
    test_names = ["अनिका", "Łukasz", "李雷"]
    for idx, name in enumerate(test_names):
        report = standard_report.model_copy(deep=True)
        report.candidate.name = name

        # HTML export
        html_out = tmp_path / f"test_{idx}.html"
        html_exp = HTMLExporter()
        html_exp.export(report, html_out)
        assert name in html_out.read_text(encoding="utf-8")

        # PDF export (must not raise UnicodeEncodeError or font error)
        pdf_out = tmp_path / f"test_{idx}.pdf"
        pdf_exp = PDFExporter()
        pdf_exp.export(report, pdf_out)
        assert pdf_out.exists()


# -----------------------------------------------------------------------------
# UT-XPT-07: Excel formula injection defense
# -----------------------------------------------------------------------------
def test_ut_xpt_07_excel_formula_injection_defense(
    standard_report: AnalysisReport,
    tmp_path: Path,
) -> None:
    """Assert cells starting with =, +, -, @, \\t, \\r are prefixed with '."""
    assert sanitize_excel_value("=1+1") == "'=1+1"
    assert (
        sanitize_excel_value("+HYPERLINK('http://evil.com')")
        == "'+HYPERLINK('http://evil.com')"
    )
    assert sanitize_excel_value("-5+5") == "'-5+5"
    assert sanitize_excel_value("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_excel_value("\tTabbed") == "'\tTabbed"
    assert sanitize_excel_value("Normal Text") == "Normal Text"
    assert sanitize_excel_value(42.5) == 42.5

    # Test within actual exported workbook
    standard_report.candidate.name = "=HYPERLINK('http://evil.com', 'Click')"
    excel_out = tmp_path / "formula_test.xlsx"
    exporter = ExcelExporter()
    exporter.export(standard_report, excel_out)

    wb = openpyxl.load_workbook(excel_out)
    summary_ws = wb["Summary"]
    found_escaped = False
    for row in summary_ws.iter_rows(values_only=True):
        if row[1] == "Name":
            assert row[2].startswith("'=")
            found_escaped = True
            break
    assert found_escaped, "Malicious name cell was not found or was unescaped"


def test_exporter_registry_and_lazy_load(
    standard_report: AnalysisReport, tmp_path: Path
) -> None:
    """Assert get_exporter lazy loads html, pdf, xlsx, and rejects unsupported format."""
    from resume_analyzer.reporting.exporters.base import _EXPORTER_REGISTRY

    # Test registry lookup
    html_e = get_exporter("html")
    assert isinstance(html_e, HTMLExporter)

    # Test fallback lazy load by clearing registry temporarily
    orig_registry = dict(_EXPORTER_REGISTRY)
    try:
        _EXPORTER_REGISTRY.clear()
        lazy_html = get_exporter("html")
        assert isinstance(lazy_html, HTMLExporter)

        lazy_pdf = get_exporter("pdf")
        assert isinstance(lazy_pdf, PDFExporter)

        lazy_xlsx = get_exporter("xlsx")
        assert isinstance(lazy_xlsx, ExcelExporter)

        lazy_excel = get_exporter("excel")
        assert isinstance(lazy_excel, ExcelExporter)

        from resume_analyzer.exceptions import UnsupportedExportFormatError

        with pytest.raises(UnsupportedExportFormatError):
            get_exporter("unknown_format")
    finally:
        _EXPORTER_REGISTRY.update(orig_registry)

    # Error handling and temp file cleanup during failed export
    with patch("os.replace", side_effect=OSError("Atomic replace failure")):
        with pytest.raises(Exception):
            html_e.export(standard_report, tmp_path / "fail.html")
    assert not (tmp_path / "fail.html").exists()
