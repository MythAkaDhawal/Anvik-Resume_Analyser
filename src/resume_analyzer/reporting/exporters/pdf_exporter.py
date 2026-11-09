"""PDF exporter generating print-ready Platypus document reports (FR-25).

Enforces strict XML escaping of dynamic strings, registers Unicode TTF fonts for
non-Latin character support (UT-XPT-06), adds page-numbered footers, and renders all §11.1 sections.
"""

from __future__ import annotations

import io
import logging
import os
import xml.sax.saxutils as saxutils  # nosec: B406
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.reporting.exporters.base import Exporter, register_exporter

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

    def showPage(self) -> None:  # noqa: N802
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
        left_text = (
            f"ANVIK Talent Intelligence  &bull;  Report ID: {self.report_id_str}"
            if self.report_id_str
            else "ANVIK Talent Intelligence"
        )
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

    def _build_meta_and_notice(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        cand_display = report.candidate.name or report.candidate.candidate_id
        items.append(
            Paragraph(
                f"ANVIK &mdash; Candidate Evaluation Report: {_escape(cand_display)}",
                styles["title"],
            )
        )
        created_str = report.created_at.strftime("%Y-%m-%d %H:%M UTC")
        meta_line = f"ANVIK Intelligent Talent Analysis  &bull;  Report ID: {report.report_id}  &bull;  Date: {created_str}  &bull;  v{report.app_version}"
        items.append(Paragraph(meta_line, styles["subtitle"]))
        items.append(Spacer(1, 8))

        notice_table = Table(
            [
                [
                    Paragraph(
                        f"<b>Compliance Notice:</b> {_escape(report.human_review_notice)}",
                        styles["notice"],
                    )
                ]
            ],
            colWidths=[A4[0] - 72],
        )
        notice_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F5F0")),
                    ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#B66F4B")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        items.append(notice_table)
        items.append(Spacer(1, 8))
        return items

    def _build_candidate_and_job_section(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        body_style = styles["body"]
        h2_style = styles["h2"]

        items.append(Paragraph("1. Candidate Information", h2_style))
        cand_data = [
            [
                Paragraph("<b>Candidate ID:</b>", body_style),
                Paragraph(report.candidate.candidate_id, body_style),
            ],
            [
                Paragraph("<b>Candidate Name:</b>", body_style),
                Paragraph(_escape(report.candidate.name or "Not detected"), body_style),
            ],
            [
                Paragraph("<b>Email:</b>", body_style),
                Paragraph(
                    _escape(report.candidate.email or "Not detected"), body_style
                ),
            ],
            [
                Paragraph("<b>Source Format:</b>", body_style),
                Paragraph(report.candidate.source_format.upper(), body_style),
            ],
        ]
        cand_table = Table(cand_data, colWidths=[120, A4[0] - 72 - 120])
        cand_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        items.append(cand_table)

        items.append(Paragraph("2. Job Requirements", h2_style))
        req_skills_str = ", ".join(report.job.required_skills)
        opt_skills_str = (
            ", ".join(report.job.optional_skills)
            if report.job.optional_skills
            else "None"
        )
        job_data = [
            [
                Paragraph("<b>Position Title:</b>", body_style),
                Paragraph(_escape(report.job.job_title), body_style),
            ],
            [
                Paragraph("<b>Required Skills:</b>", body_style),
                Paragraph(_escape(req_skills_str), body_style),
            ],
            [
                Paragraph("<b>Optional Skills:</b>", body_style),
                Paragraph(_escape(opt_skills_str), body_style),
            ],
            [
                Paragraph("<b>Min Experience:</b>", body_style),
                Paragraph(f"{report.job.min_experience_years} year(s)", body_style),
            ],
            [
                Paragraph("<b>Min Education:</b>", body_style),
                Paragraph(report.job.min_education_level.name, body_style),
            ],
            [
                Paragraph("<b>Strategy:</b>", body_style),
                Paragraph(report.score.strategy_name, body_style),
            ],
        ]
        job_table = Table(job_data, colWidths=[120, A4[0] - 72 - 120])
        job_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        items.append(job_table)
        return items

    def _build_score_and_flags_section(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        body_style = styles["body"]
        h2_style = styles["h2"]

        items.append(Paragraph("3. Overall Match Score", h2_style))
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
        score_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        items.append(score_table)

        if report.flags:
            flag_items = "<br/>".join(
                [
                    f"&bull; <b>{_escape(f.code)}:</b> {_escape(f.message)}"
                    for f in report.flags
                ]
            )
            flags_table = Table(
                [
                    [
                        Paragraph(
                            f"<b>Review Flags:</b><br/>{flag_items}", styles["alert"]
                        )
                    ]
                ],
                colWidths=[A4[0] - 72],
            )
            flags_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fde68a")),
                        ("PADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            items.append(Spacer(1, 4))
            items.append(flags_table)

        return items

    def _build_score_breakdown_section(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        body_style = styles["body"]
        items.append(Paragraph("4. Score Component Breakdown", styles["h2"]))
        comp_rows: list[list[Any]] = [
            [
                Paragraph("<b>Dimension</b>", body_style),
                Paragraph("<b>Status</b>", body_style),
                Paragraph("<b>Weight</b>", body_style),
                Paragraph("<b>Subscore</b>", body_style),
                Paragraph("<b>Points</b>", body_style),
                Paragraph("<b>Explanation</b>", body_style),
            ]
        ]
        for comp in report.score.components:
            sub = f"{comp.subscore:.2f}" if comp.subscore is not None else "—"
            pts = f"{comp.points:.1f}" if comp.points is not None else "—"
            comp_rows.append(
                [
                    Paragraph(comp.name.replace("_", " ").title(), body_style),
                    Paragraph(comp.status.value, body_style),
                    Paragraph(f"{comp.weight * 100:.0f}%", body_style),
                    Paragraph(sub, body_style),
                    Paragraph(pts, body_style),
                    Paragraph(_escape(comp.explanation or "—"), body_style),
                ]
            )
        comp_table = Table(
            comp_rows,
            colWidths=[
                (A4[0] - 72) * 0.20,
                (A4[0] - 72) * 0.15,
                (A4[0] - 72) * 0.10,
                (A4[0] - 72) * 0.12,
                (A4[0] - 72) * 0.10,
                (A4[0] - 72) * 0.33,
            ],
        )
        comp_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("PADDING", (0, 0), (-1, -1), 3.5),
                ]
            )
        )
        items.append(comp_table)
        return items

    def _build_skills_section(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        body_style = styles["body"]
        items.append(
            Paragraph("5. Skill Match Analysis (Job Requirements)", styles["h2"])
        )
        match_rows: list[list[Any]] = [
            [
                Paragraph("<b>Target Skill</b>", body_style),
                Paragraph("<b>Type</b>", body_style),
                Paragraph("<b>Matched Candidate Skill</b>", body_style),
                Paragraph("<b>Match Type</b>", body_style),
                Paragraph("<b>Credit</b>", body_style),
            ]
        ]
        for sm in report.match.skill_matches:
            target_str = _escape(sm.target)
            matched_str = _escape(sm.matched_candidate_skill or "—")
            req_label = "Required" if sm.is_required else "Optional"
            match_rows.append(
                [
                    Paragraph(target_str, body_style),
                    Paragraph(req_label, body_style),
                    Paragraph(matched_str, body_style),
                    Paragraph(sm.match_type.value, body_style),
                    Paragraph(f"{sm.credit * 100:.0f}%", body_style),
                ]
            )
        match_table = Table(
            match_rows,
            colWidths=[
                (A4[0] - 72) * 0.25,
                (A4[0] - 72) * 0.15,
                (A4[0] - 72) * 0.25,
                (A4[0] - 72) * 0.20,
                (A4[0] - 72) * 0.15,
            ],
        )
        match_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("PADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        items.append(match_table)

        items.append(Paragraph("6. Candidate Skills Inventory", styles["h2"]))
        if not report.candidate.skills:
            items.append(
                Paragraph(
                    "<i>No skills extracted from candidate profile.</i>",
                    styles["subtitle"],
                )
            )
        else:
            cand_skills_rows: list[list[Any]] = [
                [
                    Paragraph("<b>Skill Name</b>", body_style),
                    Paragraph("<b>Canonical</b>", body_style),
                    Paragraph("<b>Category</b>", body_style),
                    Paragraph("<b>Provenance</b>", body_style),
                    Paragraph("<b>Mentions</b>", body_style),
                ]
            ]
            for sk in report.candidate.skills:
                cand_skills_rows.append(
                    [
                        Paragraph(_escape(sk.name), body_style),
                        Paragraph(_escape(sk.canonical_name or "—"), body_style),
                        Paragraph(_escape(sk.category or "Uncategorized"), body_style),
                        Paragraph(sk.provenance.value, body_style),
                        Paragraph(str(sk.mentions), body_style),
                    ]
                )
            cand_skills_table = Table(
                cand_skills_rows,
                colWidths=[
                    (A4[0] - 72) * 0.30,
                    (A4[0] - 72) * 0.25,
                    (A4[0] - 72) * 0.20,
                    (A4[0] - 72) * 0.15,
                    (A4[0] - 72) * 0.10,
                ],
            )
            cand_skills_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                        ("PADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            items.append(cand_skills_table)

        return items

    def _build_experience_section(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        body_style = styles["body"]
        h2_style = styles["h2"]

        items.append(Paragraph("7. Experience Analysis", h2_style))
        exp_summary = (
            f"Required: <b>{report.match.experience.required_years:.1f} yr(s)</b>  &bull;  "
            f"Candidate: <b>{report.match.experience.candidate_years or 0.0:.1f} yr(s)</b>  &bull;  "
            f"Status: <b>{report.match.experience.status.upper()}</b>"
        )
        items.append(Paragraph(exp_summary, body_style))
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
                dur = (
                    f"{e.duration_months} mo" if e.duration_months is not None else "?"
                )
                exp_rows.append(
                    [
                        Paragraph(_escape(e.job_title or "Unspecified"), body_style),
                        Paragraph(_escape(e.company or "Unspecified"), body_style),
                        Paragraph(dur, body_style),
                        Paragraph(e.provenance.value, body_style),
                    ]
                )
            exp_table = Table(
                exp_rows,
                colWidths=[
                    (A4[0] - 72) * 0.35,
                    (A4[0] - 72) * 0.35,
                    (A4[0] - 72) * 0.15,
                    (A4[0] - 72) * 0.15,
                ],
            )
            exp_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                        ("PADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            items.append(Spacer(1, 4))
            items.append(exp_table)
        return items

    def _build_education_section(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        body_style = styles["body"]
        h2_style = styles["h2"]

        items.append(Paragraph("8. Education Analysis", h2_style))
        edu_summary = (
            f"Required Level: <b>{report.match.education.required_level.name}</b>  &bull;  "
            f"Candidate Level: <b>{report.match.education.candidate_level.name}</b>  &bull;  "
            f"Status: <b>{report.match.education.status.upper()}</b>"
        )
        items.append(Paragraph(edu_summary, body_style))
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
                edu_rows.append(
                    [
                        Paragraph(_escape(ed.degree or "Unspecified"), body_style),
                        Paragraph(ed.level.name, body_style),
                        Paragraph(_escape(ed.institution or "—"), body_style),
                        Paragraph(ed.provenance.value, body_style),
                    ]
                )
            edu_table = Table(
                edu_rows,
                colWidths=[
                    (A4[0] - 72) * 0.4,
                    (A4[0] - 72) * 0.2,
                    (A4[0] - 72) * 0.25,
                    (A4[0] - 72) * 0.15,
                ],
            )
            edu_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                        ("PADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            items.append(Spacer(1, 4))
            items.append(edu_table)
        return items

    def _build_ai_explanation_section(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        body_style = styles["body"]
        subtitle_style = styles["subtitle"]
        h2_style = styles["h2"]

        items.append(
            Paragraph(
                "9. Recommendations (AI-Generated &mdash; Not Verified)", h2_style
            )
        )
        if (
            report.ai
            and report.ai.explanation
            and report.ai.explanation.status.value in ("ok", "partial")
            and report.ai.explanation.data
        ):
            items.append(
                Paragraph(
                    f"<b>Summary:</b> {_escape(report.ai.explanation.data.summary)}",
                    body_style,
                )
            )
            for s in report.ai.explanation.data.strengths or []:
                items.append(
                    Paragraph(f"&bull; <b>Strength:</b> {_escape(s.point)}", body_style)
                )
            for c in report.ai.explanation.data.concerns or []:
                items.append(
                    Paragraph(
                        f"&bull; <b>Focus Area:</b> {_escape(c.point)}", body_style
                    )
                )
        else:
            status_val = (
                report.ai.explanation.status.value
                if report.ai and report.ai.explanation
                else "disabled"
            )
            items.append(
                Paragraph(
                    f"<i>AI-generated content unavailable ({status_val}).</i>",
                    subtitle_style,
                )
            )

        if (
            report.ai
            and report.ai.recommendations
            and report.ai.recommendations.status.value in ("ok", "partial")
            and report.ai.recommendations.data
        ):
            items.append(Spacer(1, 4))
            items.append(
                Paragraph("<b>Candidate Development Suggestions:</b>", body_style)
            )
            for r in report.ai.recommendations.data:
                items.append(
                    Paragraph(
                        f"&bull; [<b>{r.priority.upper()}</b>] {_escape(r.action)} &mdash; <font color='#64748b'>{_escape(r.rationale)}</font>",
                        body_style,
                    )
                )
        return items

    def _build_questions_and_appendix(
        self, report: AnalysisReport, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        body_style = styles["body"]
        subtitle_style = styles["subtitle"]
        h2_style = styles["h2"]

        items.append(Paragraph("10. Hiring-Suitability Assessment", h2_style))
        suitability_text = (
            f"Candidate profile demonstrates <b>{report.score.fit_band.value.upper()}</b> alignment with requirements based on deterministic scoring criteria "
            f"(Score: {report.score.total_score:.1f}/100, Coverage: {report.score.coverage * 100:.0f}%)."
        )
        items.append(Paragraph(suitability_text, body_style))

        items.append(
            Paragraph(
                "11. Suggested Interview Questions (AI-Generated &mdash; Not Verified)",
                h2_style,
            )
        )
        if (
            report.ai
            and report.ai.interview_questions
            and report.ai.interview_questions.status.value in ("ok", "partial")
            and report.ai.interview_questions.data
        ):
            for idx, q in enumerate(report.ai.interview_questions.data, start=1):
                items.append(
                    Paragraph(
                        f"{idx}. <b>{_escape(q.question)}</b> <font color='#64748b'>({_escape(q.category)})</font>",
                        body_style,
                    )
                )
                items.append(
                    Paragraph(f"   Rationale: {_escape(q.rationale)}", subtitle_style)
                )
        else:
            status_val = (
                report.ai.interview_questions.status.value
                if report.ai and report.ai.interview_questions
                else "disabled"
            )
            items.append(
                Paragraph(
                    f"<i>AI-generated content unavailable ({status_val}).</i>",
                    subtitle_style,
                )
            )

        items.append(Paragraph("12. Appendix &amp; System Limitations", h2_style))
        appendix_text = (
            "Scoring limitations: Lexical skill matching may miss semantic equivalents. "
            "Experience calculations assume continuous employment within month intervals. "
            "Educational attainment evaluates level hierarchy without institution ranking."
        )
        items.append(Paragraph(appendix_text, subtitle_style))
        return items

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

        sample_styles = getSampleStyleSheet()
        body_style = ParagraphStyle(
            "Body",
            parent=sample_styles["Normal"],
            fontName=self.font_name,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#171817"),
        )
        styles = {
            "title": ParagraphStyle(
                "ReportTitle",
                parent=sample_styles["Heading1"],
                fontName=self.font_name,
                fontSize=18,
                leading=22,
                textColor=colors.HexColor("#B66F4B"),
            ),
            "subtitle": ParagraphStyle(
                "ReportSubtitle",
                parent=sample_styles["Normal"],
                fontName=self.font_name,
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#77765D"),
            ),
            "h2": ParagraphStyle(
                "SectionH2",
                parent=sample_styles["Heading2"],
                fontName=self.font_name,
                fontSize=12,
                leading=16,
                textColor=colors.HexColor("#B66F4B"),
                spaceBefore=12,
                spaceAfter=4,
            ),
            "body": body_style,
            "notice": ParagraphStyle(
                "NoticeStyle",
                parent=body_style,
                fontName=self.font_name,
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#171817"),
            ),
            "alert": ParagraphStyle(
                "AlertStyle",
                parent=body_style,
                fontName=self.font_name,
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#B66F4B"),
            ),
        }

        story: list[Any] = []
        story.extend(self._build_meta_and_notice(report, styles))
        story.extend(self._build_candidate_and_job_section(report, styles))
        story.extend(self._build_score_and_flags_section(report, styles))
        story.extend(self._build_score_breakdown_section(report, styles))
        story.extend(self._build_skills_section(report, styles))
        story.extend(self._build_experience_section(report, styles))
        story.extend(self._build_education_section(report, styles))
        story.extend(self._build_ai_explanation_section(report, styles))
        story.extend(self._build_questions_and_appendix(report, styles))

        def canvas_maker(*args: Any, **kwargs: Any) -> NumberedCanvas:
            c = NumberedCanvas(*args, **kwargs)
            c.report_id_str = report.report_id
            return c

        doc.build(story, canvasmaker=canvas_maker)
        return buffer.getvalue()
