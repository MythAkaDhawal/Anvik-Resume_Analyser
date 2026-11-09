"""HTML exporter rendering self-contained, offline-compatible analysis reports.

Enforces autoescaping against script/HTML injection (UT-XPT-01), inlines all CSS,
forbids external network requests (CSP default-src 'none'), and preserves Unicode names (UT-XPT-06).
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.reporting.exporters.base import Exporter, register_exporter
from resume_analyzer.reporting.report_builder import ReportBuilder

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


@register_exporter
class HTMLExporter(Exporter):
    """HTML exporter generating standalone escaped reports."""

    format = "html"

    def __init__(self, template_dir: Path | str | None = None) -> None:
        """Initialize Jinja2 environment with autoescape enabled."""
        td = Path(template_dir) if template_dir else TEMPLATES_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(td)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.template = self.env.get_template("report.html.j2")

    def render_bytes(self, report: AnalysisReport) -> bytes:
        """Render AnalysisReport to UTF-8 HTML byte string."""
        missing = ReportBuilder.get_missing_skills(report)
        matched = ReportBuilder.get_matched_skills(report)

        html_text = self.template.render(
            report=report,
            missing_skills=missing,
            matched_skills=matched,
        )
        return html_text.encode("utf-8")
