"""Excel workbook exporter for single reports and batch rankings (FR-26).

Enforces formula-injection neutralization (prefixing strings starting with =, +, -, @, \\t, \\r with '),
sets explicit cell types, freezes headers, formats column widths, and produces both single and batch workbooks.
"""

from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from resume_analyzer.exceptions import ExportError
from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.reporting.exporters.base import Exporter, register_exporter

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill(start_color="171817", end_color="171817", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=10, bold=True, color="E9E2D2")
SECTION_FONT = Font(name="Calibri", size=11, bold=True, color="B66F4B")
BOLD_FONT = Font(name="Calibri", size=9.5, bold=True, color="171817")
BODY_FONT = Font(name="Calibri", size=9.5, color="171817")
MUTED_FONT = Font(name="Calibri", size=9, color="77765D", italic=True)
THIN_SIDE = Side(border_style="thin", color="D1D5DB")
BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)


def sanitize_excel_value(val: Any) -> Any:
    """Neutralize formula injection by prefixing formula triggers with a single quote."""
    if val is None:
        return ""
    if isinstance(val, (int, float, bool)):
        return val
    text = str(val)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def _style_header_row(ws: Any, row_idx: int, col_count: int) -> None:
    """Apply styling and formatting to an Excel table header row."""
    for col in range(1, col_count + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.border = BORDER
        cell.alignment = Alignment(vertical="center", horizontal="left")


def _auto_fit_columns(ws: Any, max_len_cap: int = 50) -> None:
    """Adjust worksheet column widths according to maximum content length."""
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), max_len_cap)


@register_exporter
class ExcelExporter(Exporter):
    """Excel exporter creating multi-sheet single reports and batch ranking workbooks."""

    format = "xlsx"

    def render_bytes(self, report: AnalysisReport) -> bytes:
        """Render single AnalysisReport into four sheets (Summary, Skills, Exp-Edu, AI)."""
        wb = openpyxl.Workbook()
        # Sheet 1: Summary
        ws_summary = wb.active
        ws_summary.title = "Summary"
        self._populate_summary_sheet(ws_summary, report)

        # Sheet 2: Skills
        ws_skills = wb.create_sheet(title="Skills")
        self._populate_skills_sheet(ws_skills, report)

        # Sheet 3: Experience-Education
        ws_exp_edu = wb.create_sheet(title="Experience-Education")
        self._populate_exp_edu_sheet(ws_exp_edu, report)

        # Sheet 4: AI-Insights
        ws_ai = wb.create_sheet(title="AI-Insights")
        self._populate_ai_sheet(ws_ai, report)

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def _populate_summary_sheet(self, ws: Any, report: AnalysisReport) -> None:
        """Build metadata, candidate, job, overall score, and score breakdown."""
        ws.freeze_panes = "A2"
        headers = ["Section", "Field", "Value", "Notes"]
        ws.append(headers)
        _style_header_row(ws, 1, len(headers))

        rows: list[list[Any]] = [
            ["Metadata", "Report ID", report.report_id, ""],
            [
                "Metadata",
                "Created At",
                report.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                "",
            ],
            ["Metadata", "App Version", report.app_version, ""],
            ["Metadata", "Legal Notice", report.human_review_notice, ""],
            ["Candidate", "Candidate ID", report.candidate.candidate_id, ""],
            ["Candidate", "Name", report.candidate.name or "Not detected", ""],
            ["Candidate", "Email", report.candidate.email or "Not detected", ""],
            ["Candidate", "Source Format", report.candidate.source_format.upper(), ""],
            ["Job", "Target Title", report.job.job_title, ""],
            ["Job", "Required Skills", ", ".join(report.job.required_skills), ""],
            [
                "Job",
                "Optional Skills",
                ", ".join(report.job.optional_skills)
                if report.job.optional_skills
                else "None",
                "",
            ],
            ["Job", "Min Experience Years", report.job.min_experience_years, ""],
            ["Job", "Min Education Level", report.job.min_education_level.name, ""],
            ["Job", "Scoring Strategy", report.score.strategy_name, ""],
            ["Score", "Total Score", report.score.total_score, "Scale: 0-100"],
            ["Score", "Fit Band", report.score.fit_band.value.upper(), ""],
            [
                "Score",
                "Data Coverage",
                f"{report.score.coverage * 100:.0f}%",
                "Evaluated weights share",
            ],
        ]

        if report.flags:
            flags_str = "; ".join([f"{f.code}: {f.message}" for f in report.flags])
            rows.append(["Score", "Flags", flags_str, "Advisory human review notes"])

        for comp in report.score.components:
            sub = f"{comp.subscore:.2f}" if comp.subscore is not None else "N/A"
            pts = f"{comp.points:.1f}" if comp.points is not None else "0.0"
            rows.append(
                [
                    "Breakdown",
                    comp.name,
                    f"{comp.weight * 100:.0f}% wt | {sub} sub | {pts} pts",
                    comp.explanation,
                ]
            )

        for r_idx, row in enumerate(rows, start=2):
            for c_idx, val in enumerate(row, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=sanitize_excel_value(val))
                cell.font = BODY_FONT
                cell.border = BORDER

        _auto_fit_columns(ws)

    def _populate_skills_sheet(self, ws: Any, report: AnalysisReport) -> None:
        """Build matched and missing skills table."""
        ws.freeze_panes = "A2"
        headers = [
            "Job Requirement",
            "Requirement Type",
            "Matched Candidate Skill",
            "Match Type",
            "Similarity %",
            "Credit Awarded",
            "Provenance",
        ]
        ws.append(headers)
        _style_header_row(ws, 1, len(headers))

        row_idx = 2
        for m in report.match.skill_matches:
            req_type = (
                "Required (Must-have)" if m.is_required else "Optional (Nice-to-have)"
            )
            matched_skill = m.matched_candidate_skill or "—"
            row = [
                m.target,
                req_type,
                matched_skill,
                m.match_type.value,
                m.similarity,
                m.credit,
                m.provenance.value,
            ]
            for c_idx, val in enumerate(row, start=1):
                cell = ws.cell(
                    row=row_idx, column=c_idx, value=sanitize_excel_value(val)
                )
                cell.font = BODY_FONT
                cell.border = BORDER
            row_idx += 1

        _auto_fit_columns(ws)

    def _populate_exp_edu_sheet(self, ws: Any, report: AnalysisReport) -> None:
        """Build experience and education entries and evaluation summaries."""
        ws.freeze_panes = "A2"
        headers = ["Section", "Field 1", "Field 2", "Field 3", "Field 4", "Provenance"]
        ws.append(headers)
        _style_header_row(ws, 1, len(headers))

        rows: list[list[Any]] = [
            [
                "Experience Summary",
                f"Required: {report.match.experience.required_years} yr(s)",
                f"Candidate: {report.match.experience.candidate_years if report.match.experience.candidate_years is not None else 'Unknown'} yr(s)",
                f"Status: {report.match.experience.status.upper()}",
                f"Gap: {report.match.experience.gap_years if report.match.experience.gap_years is not None else '0.0'} yr(s)",
                report.match.experience.provenance.value,
            ]
        ]

        for e in report.candidate.experience:
            dates = (
                f"{e.start.strftime('%b %Y') if e.start else '?'} - "
                f"{'Present' if e.is_current else (e.end.strftime('%b %Y') if e.end else '?')}"
            )
            dur = f"{e.duration_months} mo" if e.duration_months is not None else "?"
            rows.append(
                [
                    "Experience Entry",
                    e.job_title or "Unspecified",
                    e.company or "Unspecified",
                    dates,
                    dur,
                    e.provenance.value,
                ]
            )

        rows.append(
            [
                "Education Summary",
                f"Required: {report.match.education.required_level.name}",
                f"Candidate: {report.match.education.candidate_level.name}",
                f"Status: {report.match.education.status.upper()}",
                f"Field Match: {'Yes' if report.match.education.field_match else ('No' if report.match.education.field_match is False else 'N/A')}",
                report.match.education.provenance.value,
            ]
        )

        for ed in report.candidate.education:
            rows.append(
                [
                    "Education Entry",
                    ed.degree or "Unspecified",
                    ed.level.name,
                    ed.field_of_study or "—",
                    ed.institution or "—",
                    ed.provenance.value,
                ]
            )

        for r_idx, row in enumerate(rows, start=2):
            for c_idx, val in enumerate(row, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=sanitize_excel_value(val))
                cell.font = BODY_FONT
                cell.border = BORDER

        _auto_fit_columns(ws)

    def _populate_ai_sheet(self, ws: Any, report: AnalysisReport) -> None:
        """Build AI insights sheet covering explanation, recommendations, and interview questions."""
        ws.freeze_panes = "A2"
        headers = [
            "AI Feature",
            "Category / Topic",
            "Content / Question",
            "Rationale / Details",
            "Status",
        ]
        ws.append(headers)
        _style_header_row(ws, 1, len(headers))

        rows: list[list[Any]] = []

        # P3: Explanation
        if (
            report.ai
            and report.ai.explanation
            and report.ai.explanation.status.value in ("ok", "partial")
            and report.ai.explanation.data
        ):
            rows.append(
                [
                    "Match Explanation",
                    "Summary",
                    report.ai.explanation.data.summary,
                    "",
                    "OK",
                ]
            )
            for s in report.ai.explanation.data.strengths:
                rows.append(
                    [
                        "Match Explanation",
                        "Strength",
                        s.point,
                        ", ".join(s.evidence),
                        "OK",
                    ]
                )
            for c in report.ai.explanation.data.concerns:
                rows.append(
                    [
                        "Match Explanation",
                        "Focus Area",
                        c.point,
                        ", ".join(c.evidence),
                        "OK",
                    ]
                )
        else:
            status_val = (
                report.ai.explanation.status.value
                if report.ai and report.ai.explanation
                else "disabled"
            )
            rows.append(
                [
                    "Match Explanation",
                    "N/A",
                    f"AI-generated content unavailable ({status_val})",
                    "",
                    status_val,
                ]
            )

        # P4: Recommendations
        if (
            report.ai
            and report.ai.recommendations
            and report.ai.recommendations.status.value in ("ok", "partial")
            and report.ai.recommendations.data
        ):
            for r in report.ai.recommendations.data:
                rows.append(
                    ["Recommendation", r.priority.upper(), r.action, r.rationale, "OK"]
                )
        else:
            status_val = (
                report.ai.recommendations.status.value
                if report.ai and report.ai.recommendations
                else "disabled"
            )
            rows.append(
                [
                    "Recommendation",
                    "N/A",
                    f"AI-generated content unavailable ({status_val})",
                    "",
                    status_val,
                ]
            )

        # P5: Interview Questions
        if (
            report.ai
            and report.ai.interview_questions
            and report.ai.interview_questions.status.value in ("ok", "partial")
            and report.ai.interview_questions.data
        ):
            for q in report.ai.interview_questions.data:
                rows.append(
                    ["Interview Question", q.category, q.question, q.rationale, "OK"]
                )
        else:
            status_val = (
                report.ai.interview_questions.status.value
                if report.ai and report.ai.interview_questions
                else "disabled"
            )
            rows.append(
                [
                    "Interview Question",
                    "N/A",
                    f"AI-generated content unavailable ({status_val})",
                    "",
                    status_val,
                ]
            )

        for r_idx, row in enumerate(rows, start=2):
            for c_idx, val in enumerate(row, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=sanitize_excel_value(val))
                cell.font = BODY_FONT
                cell.border = BORDER

        _auto_fit_columns(ws)

    def build_batch_workbook(self, reports: list[AnalysisReport]) -> openpyxl.Workbook:
        """Construct multi-candidate batch ranking Excel workbook."""
        wb = openpyxl.Workbook()
        ws_rank = wb.active
        ws_rank.title = "Ranking"
        ws_rank.freeze_panes = "A2"

        headers = [
            "Rank",
            "Candidate ID",
            "Name",
            "Score",
            "Fit band",
            "Coverage",
            "Missing required skills",
            "Flags",
            "Strategy",
        ]
        ws_rank.append(headers)
        _style_header_row(ws_rank, 1, len(headers))

        sorted_reports = sorted(
            reports,
            key=lambda r: (
                -r.score.total_score,
                -r.match.required_credit,
                r.candidate.candidate_id,
            ),
        )

        for rank, r in enumerate(sorted_reports, start=1):
            missing_req = [
                m.target
                for m in r.match.skill_matches
                if m.is_required and (m.credit < 0.5 or m.match_type.value == "none")
            ]
            missing_str = ", ".join(missing_req) if missing_req else "None"
            flags_str = ", ".join([f.code for f in r.flags]) if r.flags else "None"

            row = [
                rank,
                r.candidate.candidate_id,
                r.candidate.name or "Not detected",
                r.score.total_score,
                r.score.fit_band.value.upper(),
                f"{r.score.coverage * 100:.0f}%",
                missing_str,
                flags_str,
                r.score.strategy_name,
            ]

            r_idx = rank + 1
            for c_idx, val in enumerate(row, start=1):
                cell = ws_rank.cell(
                    row=r_idx, column=c_idx, value=sanitize_excel_value(val)
                )
                cell.font = BODY_FONT
                cell.border = BORDER
                if c_idx in (1, 4):  # Rank and Score
                    cell.alignment = Alignment(horizontal="center")

        _auto_fit_columns(ws_rank)
        return wb

    def export_batch_bytes(self, reports: list[AnalysisReport]) -> bytes:
        """Render batch ranking workbook to in-memory bytes."""
        wb = self.build_batch_workbook(reports)
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def export_batch(self, reports: list[AnalysisReport], out_path: Path | str) -> Path:
        """Export multi-candidate batch ranking workbook atomically."""
        target = Path(out_path).resolve()
        parent_dir = target.parent

        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ExportError(
                f"Failed to create directory '{parent_dir}': {e}",
                details={"path": str(target)},
            ) from e

        temp_file = parent_dir / f"{target.stem}.{uuid.uuid4().hex[:8]}.tmp"

        try:
            wb = self.build_batch_workbook(reports)
            wb.save(temp_file)
            os.replace(temp_file, target)
            logger.info(
                "Batch ranking workbook written path=%s count=%d", target, len(reports)
            )
            return target
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise ExportError(
                f"Failed to export batch workbook to '{target}': {e}",
                details={"path": str(target), "error": str(e)},
            ) from e
