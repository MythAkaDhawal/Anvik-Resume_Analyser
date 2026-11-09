"""Integration test for storage pipeline: Analyze -> Save -> List -> Load -> Re-export (IT-07, FR-27, FR-28)."""

from __future__ import annotations

from pathlib import Path

from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.reporting.exporters.excel_exporter import ExcelExporter
from resume_analyzer.reporting.exporters.html_exporter import HTMLExporter
from resume_analyzer.reporting.exporters.pdf_exporter import PDFExporter
from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService
from resume_analyzer.storage.result_store import ResultStore

SAMPLE_RESUME_TEXT = """
Alex Morgan
alex.morgan@techmail.com | San Francisco, CA

PROFESSIONAL EXPERIENCE
Senior Data Engineer | CloudTech Solutions | 2021 - 2024
- Built large-scale ETL pipelines in Python and Apache Spark.
- Optimized relational databases and complex queries using PostgreSQL and SQL.
- Designed distributed workflows with Docker and AWS.

EDUCATION
Bachelor of Science in Computer Science
University of California, Berkeley | 2017 - 2021

SKILLS
Python, SQL, Apache Spark, PostgreSQL, Docker, AWS, Git
"""


def test_it_07_storage_pipeline_roundtrip(tmp_path: Path) -> None:
    """Execute end-to-end Analyze -> Save -> List -> Load -> Re-export pipeline (IT-07)."""
    results_dir = tmp_path / "results"
    exports_dir = tmp_path / "exports"
    results_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    store = ResultStore(base_dir=results_dir)
    service = AnalysisService()

    job = JobRequirements(
        job_title="Senior Data Engineer",
        required_skills=["Python", "SQL", "Apache Spark"],
        optional_skills=["Docker", "AWS"],
        min_experience_years=2.0,
        min_education_level=EducationLevel.BACHELOR,
    )

    # 1. Analyze
    report = service.analyze(
        filename="alex_morgan_resume.txt",
        data=SAMPLE_RESUME_TEXT.encode("utf-8"),
        job=job,
        options=AnalysisOptions(strategy="weighted", ai_enabled=False),
    )
    assert report.report_id is not None
    assert report.candidate.name == "Alex Morgan"

    # 2. Save
    saved_path = store.save(report)
    assert saved_path.is_file()
    assert saved_path.name == f"{report.report_id}.json"

    # 3. List
    summaries = store.list()
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.report_id == report.report_id
    assert summary.candidate_name == "Alex Morgan"
    assert summary.readable is True
    assert summary.total_score == report.score.total_score

    # 4. Load
    loaded_report = store.load(report.report_id)
    assert loaded_report.report_id == report.report_id
    assert loaded_report.candidate.name == report.candidate.name
    assert loaded_report.score.total_score == report.score.total_score
    assert loaded_report.score.fit_band == report.score.fit_band

    # 5. Re-export to HTML, PDF, and Excel
    html_out = exports_dir / f"report_{loaded_report.report_id}.html"
    pdf_out = exports_dir / f"report_{loaded_report.report_id}.pdf"
    xlsx_out = exports_dir / f"report_{loaded_report.report_id}.xlsx"

    html_exp = HTMLExporter()
    pdf_exp = PDFExporter()
    xlsx_exp = ExcelExporter()

    html_exp.export_to_file(loaded_report, html_out)
    pdf_exp.export_to_file(loaded_report, pdf_out)
    xlsx_exp.export_to_file(loaded_report, xlsx_out)

    assert html_out.is_file() and html_out.stat().st_size > 0
    assert pdf_out.is_file() and pdf_out.stat().st_size > 0
    assert xlsx_out.is_file() and xlsx_out.stat().st_size > 0

    # Verify content in exported HTML
    html_content = html_out.read_text(encoding="utf-8")
    assert "Alex Morgan" in html_content
    assert loaded_report.report_id in html_content
