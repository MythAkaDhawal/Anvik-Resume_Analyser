"""Reporting package for assembling and exporting analysis reports."""

from __future__ import annotations

from resume_analyzer.reporting.exporters.base import (
    Exporter,
    export_batch_workbook,
    get_exporter,
)
from resume_analyzer.reporting.provenance import (
    AI_UNAVAILABLE_NOTICE_TEMPLATE,
    AI_UNVERIFIED_NOTICE,
    HUMAN_REVIEW_NOTICE,
    PROVENANCE_BADGE_CSS,
    PROVENANCE_DISPLAY_NAMES,
    contains_verdict_language,
    get_badge_css_class,
    get_provenance_display,
    validate_no_verdict_language,
)
from resume_analyzer.reporting.report_builder import ReportBuilder

__all__ = [
    "AI_UNAVAILABLE_NOTICE_TEMPLATE",
    "AI_UNVERIFIED_NOTICE",
    "Exporter",
    "HUMAN_REVIEW_NOTICE",
    "PROVENANCE_BADGE_CSS",
    "PROVENANCE_DISPLAY_NAMES",
    "ReportBuilder",
    "contains_verdict_language",
    "export_batch_workbook",
    "get_badge_css_class",
    "get_exporter",
    "get_provenance_display",
    "validate_no_verdict_language",
]
