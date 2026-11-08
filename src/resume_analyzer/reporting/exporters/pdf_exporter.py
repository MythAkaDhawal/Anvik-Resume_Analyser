"""PDF exporter generating print-ready Platypus document reports (FR-25).

Enforces strict XML escaping of dynamic strings, registers Unicode TTF fonts for
non-Latin character support (UT-XPT-06), adds page-numbered footers, and renders all §11.1 sections.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any
import xml.sax.saxutils as saxutils

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.reporting.exporters.base import Exporter, register_exporter
from resume_analyzer.reporting.provenance import get_provenance_display
from resume_analyzer.reporting.report_builder import ReportBuilder

logger = logging.getLogger(__name__)


def _escape(text: Any) -> str:
    """Safely escape text for inclusion in ReportLab Paragraph markup."""
    if text is None:
        return ""
    return saxutils.escape(str(text))


def _register_unicode_font() -> str:
    """Register system or bundled Unicode TTF font for non-Latin name rendering."""
    font_candidates = [
        ("Arial", "C:/Windows/Fonts/arial.ttf"),
        ("SegoeUI", "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for font_name, path_str in font_candidates:
        if os.path.exists(path_str):
            if font_name not in pdfmetrics.getRegisteredFontNames():
                try:
                    pdfmetrics.registerFont(TTFont(font_name, path_str))
                    return font_name
                except Exception as e:
                    logger.debug("Could not register font %s: %e", font_name, e)
            else:
                return font_name

    return "Helvetica"


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas drawing dynamic page numbers and report ID in footer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []
        self.report_id_str = ""

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Footer text
        left_text = f"Report ID: {self.report_id_str}" if self.report_id_str else ""
        right_text = f"Page {self._pageNumber} of {page_count}"

        self.drawString(36, 20, left_text)
        self.drawRightString(A4[0] - 36, 20, right_text)
        self.restoreState()


@register_exporter
class PDFExporter(Exporter):
    """PDF exporter creating multi-section analysis documents."""

    format = "pdf"

    def __init__(self) -> None:
        """Initialize PDF exporter and ensure Unicode font is registered."""
        self.font_name = _register_unicode_font()

    def render_bytes(self, report: AnalysisReport) -> bytes:
        """Render AnalysisReport to PDF byte buffer."""
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontName=self.font_name,
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1e3a8a"),
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontName=self.font_name,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748b"),
        )
        h2_style = ParagraphStyle(
            "SectionH2",
            parent=styles["Heading2"],
            fontName=self.font_name,
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1e3a8a"),
            spaceBefore=12,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName=self.font_name,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#0f172a"),
        )
        bold_style = ParagraphStyle(
            "BodyBold",
            parent=body_style,
            fontName=self.font_name,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#0f172a"),
        )
        notice_style = ParagraphStyle(
            "NoticeStyle",
            parent=body_style,
            fontName=self.font_name,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1e40af"),
        )
        alert_style = ParagraphStyle(
            "AlertStyle",
            parent=body_style,
            fontName=self.font_name,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#92400e"),
        )

        story: list[Any] = []

        # Header: Title & Metadata
        cand_display = report.candidate.name or report.candidate.candidate_id
        story.append(Paragraph(f"Resume Analysis Report: {_escape(cand_display)}", title_style))
        created_str = report.created_at.strftime("%Y-%m-%d %H:%M UTC")
        meta_line = f"Report ID: {report.report_id}  &bull;  Date: {created_str}  &bull;  App Version: {report.app_version}"
        story.append(Paragraph(meta_line, subtitle_style))
        story.append(Spacer(1, 8))

        # Legal / Human-Review Notice box
        notice_table = Table(
            [[Paragraph(f"<b>Notice:</b> {_escape(report.human_review_notice)}", notice_style)]],
            colWidths=[A4[0] - 72],
        )
        notice_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#bfdbfe")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(notice_table)
        story.append(Spacer(1, 8))

        # 1. Candidate Information
        story.append(Paragraph("1. Candidate Information", h2_style))
        cand_data = [
            [Paragraph("<b>Candidate ID:</b>", body_style), Paragraph(report.candidate.candidate_id, body_style)],
            [Paragraph("<b>Candidate Name:</b>", body_style), Paragraph(_escape(report.candidate.name or "Not detected"), body_style)],
            [Paragraph("<b>Email:</b>", body_style), Paragraph(_escape(report.candidate.email or "Not detected"), body_style)],
            [Paragraph("<b>Source Format:</b>", body_style), Paragraph(report.candidate.source_format.upper(), body_style)],
        ]
        cand_table = Table(cand_data, colWidths=[120, A4[0] - 72 - 120])
        cand_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(cand_table)

        # 2. Job Requirements
        story.append(Paragraph("2. Job Requirements", h2_style))
        req_skills_str = ", ".join(report.job.required_skills)
        opt_skills_str = ", ".join(report.job.optional_skills) if report.job.optional_skills else "None"
        job_data = [
            [Paragraph("<b>Position Title:</b>", body_style), Paragraph(_escape(report.job.job_title), body_style)],
            [Paragraph("<b>Required Skills:</b>", body_style), Paragraph(_escape(req_skills_str), body_style)],
            [Paragraph("<b>Optional Skills:</b>", body_style), Paragraph(_escape(opt_skills_str), body_style)],
            [Paragraph("<b>Min Experience:</b>", body_style), Paragraph(f"{report.job.min_experience_years} year(s)", body_style)],
            [Paragraph("<b>Min Education:</b>", body_style), Paragraph(report.job.min_education_level.name, body_style)],
            [Paragraph("<b>Strategy:</b>", body_style), Paragraph(report.score.strategy_name, body_style)],
        ]
        job_table = Table(job_data, colWidths=[120, A4[0] - 72 - 120])
        job_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(job_table)

        # 3. Overall Match Score
        story.append(Paragraph("3. Overall Match Score", h2_style))
        score_data = [
            [
                Paragraph("<b>Total Score:</b>", body_style),
                Paragraph(f"<b>{report.score.total_score:.1f} / 100</b>", body_style),
                Paragraph("<b>Fit Band:</b>", body_style),
                Paragraph(f"<b>{report.score.fit_band.value.upper()}</b>", body_style),
                Paragraph("<b>Coverage:</b>", body_style),
                Paragraph(f"{report.score.coverage * 100:.0f}%", body_style),
            ]
        ]
        col_w = (A4[0] - 72) / 6
        score_table = Table(score_data, colWidths=[col_w] * 6)
        score_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(score_table)

        if report.flags:
            flag_items = "<br/>".join([f"&bull; <b>{_escape(f.code)}:</b> {_escape(f.message)}" for f in report.flags])
            flags_table = Table(
                [[Paragraph(f"<b>Review Flags:</b><br/>{flag_items}", alert_style)]],
                colWidths=[A4[0] - 72],
            )
            flags_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fcd34d")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(Spacer(1, 4))
            story.append(flags_table)

        # 4. Score Component Breakdown
        story.append(Paragraph("4. Score Breakdown", h2_style))
        comp_rows: list[list[Any]] = [
            [
                Paragraph("<b>Component</b>", body_style),
                Paragraph("<b>Weight</b>", body_style),
                Paragraph("<b>Subscore</b>", body_style),
                Paragraph("<b>Points</b>", body_style),
                Paragraph("<b>Calculation Details</b>", body_style),
            ]
        ]
        for c in report.score.components:
            sub = f"{c.subscore:.2f}" if c.subscore is not None else "N/A"
            pts = f"{c.points:.1f}" if c.points is not None else "0.0"
            comp_rows.append([
                Paragraph(_escape(c.name), body_style),
                Paragraph(f"{c.weight * 100:.0f}%", body_style),
                Paragraph(sub, body_style),
                Paragraph(pts, body_style),
                Paragraph(_escape(c.explanation), body_style),
            ])
        comp_table = Table(comp_rows, colWidths=[85, 45, 50, 45, A4[0] - 72 - 225])
        comp_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(comp_table)

        # 5. Matched Skills
        story.append(Paragraph("5. Matched Skills", h2_style))
        matched = ReportBuilder.get_matched_skills(report)
        match_rows: list[list[Any]] = [
            [
                Paragraph("<b>Job Requirement</b>", body_style),
                Paragraph("<b>Type</b>", body_style),
                Paragraph("<b>Matched Candidate Skill</b>", body_style),
                Paragraph("<b>Match Type</b>", body_style),
                Paragraph("<b>Similarity</b>", body_style),
                Paragraph("<b>Credit</b>", body_style),
            ]
        ]
        for m in matched:
            match_rows.append([
                Paragraph(_escape(m.target), body_style),
                Paragraph("Required" if m.is_required else "Optional", body_style),
                Paragraph(_escape(m.matched_candidate_skill or "—"), body_style),
                Paragraph(_escape(m.match_type.value), body_style),
                Paragraph(f"{m.similarity:.0f}%", body_style),
                Paragraph(f"{m.credit:.2f}", body_style),
            ])
        if len(match_rows) == 1:
            match_rows.append([Paragraph("No skills matched", body_style)] + [Paragraph("", body_style)] * 5)
        m_col_w = (A4[0] - 72) / 6
        matched_table = Table(match_rows, colWidths=[m_col_w] * 6)
        matched_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(matched_table)

        # 6. Missing Skills
        story.append(Paragraph("6. Missing Skills", h2_style))
        missing = ReportBuilder.get_missing_skills(report)
        missing_rows: list[list[Any]] = [
            [
                Paragraph("<b>Missing Skill</b>", body_style),
                Paragraph("<b>Requirement Type</b>", body_style),
                Paragraph("<b>Credit</b>", body_style),
            ]
        ]
        for m in missing:
            req_label = "Required (Must-have)" if m.is_required else "Optional"
            missing_rows.append([
                Paragraph(_escape(m.target), body_style),
                Paragraph(req_label, body_style),
                Paragraph("0.00", body_style),
            ])
        if len(missing_rows) == 1:
            missing_rows.append([Paragraph("All required skills matched", body_style), Paragraph("", body_style), Paragraph("", body_style)])
        miss_table = Table(missing_rows, colWidths=[(A4[0] - 72) * 0.5, (A4[0] - 72) * 0.3, (A4[0] - 72) * 0.2])
        miss_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(miss_table)

        # 7. Experience Analysis
        story.append(Paragraph("7. Experience Analysis", h2_style))
        exp_summary = (
            f"Required: <b>{report.match.experience.required_years} yr(s)</b>  &bull;  "
            f"Candidate: <b>{report.match.experience.candidate_years if report.match.experience.candidate_years is not None else 'Unknown'} yr(s)</b>  &bull;  "
            f"Status: <b>{report.match.experience.status.upper()}</b>"
        )
        story.append(Paragraph(exp_summary, body_style))
        if report.candidate.experience:
            exp_rows: list[list[Any]] = [
                [
                    Paragraph("<b>Job Title</b>", body_style),
                    Paragraph("<b>Company</b>", body_style),
                    Paragraph("<b>Duration</b>", body_style),
                    Paragraph("<b>Provenance</b>", body_style),
                ]
            ]
            for e in report.candidate.experience:
                dur = f"{e.duration_months} mo" if e.duration_months is not None else "?"
                exp_rows.append([
                    Paragraph(_escape(e.job_title or "Unspecified"), body_style),
                    Paragraph(_escape(e.company or "Unspecified"), body_style),
                    Paragraph(dur, body_style),
                    Paragraph(e.provenance.value, body_style),
                ])
            exp_table = Table(exp_rows, colWidths=[(A4[0] - 72) * 0.35, (A4[0] - 72) * 0.35, (A4[0] - 72) * 0.15, (A4[0] - 72) * 0.15])
            exp_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(Spacer(1, 4))
            story.append(exp_table)

        # 8. Education Analysis
        story.append(Paragraph("8. Education Analysis", h2_style))
        edu_summary = (
            f"Required Level: <b>{report.match.education.required_level.name}</b>  &bull;  "
            f"Candidate Level: <b>{report.match.education.candidate_level.name}</b>  &bull;  "
            f"Status: <b>{report.match.education.status.upper()}</b>"
        )
        story.append(Paragraph(edu_summary, body_style))
        if report.candidate.education:
            edu_rows: list[list[Any]] = [
                [
                    Paragraph("<b>Degree</b>", body_style),
                    Paragraph("<b>Level</b>", body_style),
                    Paragraph("<b>Institution</b>", body_style),
                    Paragraph("<b>Provenance</b>", body_style),
                ]
            ]
            for ed in report.candidate.education:
                edu_rows.append([
                    Paragraph(_escape(ed.degree or "Unspecified"), body_style),
                    Paragraph(ed.level.name, body_style),
                    Paragraph(_escape(ed.institution or "—"), body_style),
                    Paragraph(ed.provenance.value, body_style),
                ])
            edu_table = Table(edu_rows, colWidths=[(A4[0] - 72) * 0.4, (A4[0] - 72) * 0.2, (A4[0] - 72) * 0.25, (A4[0] - 72) * 0.15])
            edu_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(Spacer(1, 4))
            story.append(edu_table)

        # 9. Recommendations (AI-Generated)
        story.append(Paragraph("9. Recommendations (AI-Generated &mdash; Not Verified)", h2_style))
        if report.ai and report.ai.explanation and report.ai.explanation.status.value in ("ok", "partial") and report.ai.explanation.data:
            story.append(Paragraph(f"<b>Summary:</b> {_escape(report.ai.explanation.data.summary)}", body_style))
            if report.ai.explanation.data.strengths:
                for s in report.ai.explanation.data.strengths:
                    story.append(Paragraph(f"&bull; <b>Strength:</b> {_escape(s.point)}", body_style))
            if report.ai.explanation.data.concerns:
                for c in report.ai.explanation.data.concerns:
                    story.append(Paragraph(f"&bull; <b>Focus Area:</b> {_escape(c.point)}", body_style))
        else:
            status_val = report.ai.explanation.status.value if report.ai and report.ai.explanation else "disabled"
            story.append(Paragraph(f"<i>AI-generated content unavailable ({status_val}).</i>", subtitle_style))

        if report.ai and report.ai.recommendations and report.ai.recommendations.status.value in ("ok", "partial") and report.ai.recommendations.data:
            story.append(Spacer(1, 4))
            story.append(Paragraph("<b>Candidate Development Suggestions:</b>", body_style))
            for r in report.ai.recommendations.data:
                story.append(Paragraph(f"&bull; [<b>{r.priority.upper()}</b>] {_escape(r.action)} &mdash; <font color='#64748b'>{_escape(r.rationale)}</font>", body_style))

        # 10. Suitability Assessment
        story.append(Paragraph("10. Hiring-Suitability Assessment", h2_style))
        suitability_text = (
            f"Candidate profile demonstrates <b>{report.score.fit_band.value.upper()}</b> alignment with requirements based on deterministic scoring criteria "
            f"(Score: {report.score.total_score:.1f}/100, Coverage: {report.score.coverage * 100:.0f}%)."
        )
        story.append(Paragraph(suitability_text, body_style))

        # 11. Interview Questions
        story.append(Paragraph("11. Suggested Interview Questions (AI-Generated &mdash; Not Verified)", h2_style))
        if report.ai and report.ai.interview_questions and report.ai.interview_questions.status.value in ("ok", "partial") and report.ai.interview_questions.data:
            for idx, q in enumerate(report.ai.interview_questions.data, start=1):
                story.append(Paragraph(f"{idx}. <b>{_escape(q.question)}</b> <font color='#64748b'>({_escape(q.category)})</font>", body_style))
                story.append(Paragraph(f"   Rationale: {_escape(q.rationale)}", subtitle_style))
        else:
            status_val = report.ai.interview_questions.status.value if report.ai and report.ai.interview_questions else "disabled"
            story.append(Paragraph(f"<i>AI-generated content unavailable ({status_val}).</i>", subtitle_style))

        # 12. Appendix
        story.append(Paragraph("12. Appendix &amp; System Limitations", h2_style))
        appendix_text = (
            "Scoring limitations: Lexical skill matching may miss semantic equivalents. "
            "Experience calculations assume continuous employment within month intervals. "
            "Educational attainment evaluates level hierarchy without institution ranking."
        )
        story.append(Paragraph(appendix_text, subtitle_style))

        # Build PDF with custom NumberedCanvas
        def canvas_maker(*args: Any, **kwargs: Any) -> NumberedCanvas:
            c = NumberedCanvas(*args, **kwargs)
            c.report_id_str = report.report_id
            return c

        doc.build(story, canvasmaker=canvas_maker)
        return buffer.getvalue()
