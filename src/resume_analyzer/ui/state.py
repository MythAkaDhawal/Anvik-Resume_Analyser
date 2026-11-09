"""Session state management for the Streamlit UI (TECHNICAL_SPECIFICATION §16)."""

from __future__ import annotations

import streamlit as st

from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService
from resume_analyzer.services.batch_runner import BatchRunner

PAGES = ["1 Job", "2 Resumes", "3 Results", "4 Reports", "5 History"]


def init_session_state() -> None:
    """Initialize required session_state variables with default values."""
    if "job" not in st.session_state:
        st.session_state["job"] = None
    if "files" not in st.session_state:
        st.session_state["files"] = []
    if "reports" not in st.session_state:
        st.session_state["reports"] = []
    if "failures" not in st.session_state:
        st.session_state["failures"] = []
    if "options" not in st.session_state:
        st.session_state["options"] = AnalysisOptions(
            strategy="weighted",
            ai_enabled=False,
            ai_extract_candidate=False,
            ai_categorize_skills=False,
            ai_explain_match=False,
            ai_recommendations=False,
            ai_interview_questions=False,
        )
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "1 Job"
    if "nav_radio" not in st.session_state:
        st.session_state["nav_radio"] = "1 Job"
    if "_last_synced_page" not in st.session_state:
        st.session_state["_last_synced_page"] = "1 Job"
    if "selected_report_idx" not in st.session_state:
        st.session_state["selected_report_idx"] = 0


def set_page(page: str) -> None:
    """Transition to the specified UI page."""
    if page in PAGES:
        st.session_state["current_page"] = page


def clear_results() -> None:
    """Reset active analysis reports and failure records."""
    st.session_state["reports"] = []
    st.session_state["failures"] = []
    st.session_state["selected_report_idx"] = 0


@st.cache_resource
def get_service() -> AnalysisService:
    """Return a cached, reusable AnalysisService instance."""
    return AnalysisService()


@st.cache_resource
def get_batch_runner() -> BatchRunner:
    """Return a cached, reusable BatchRunner instance."""
    return BatchRunner(analysis_service=get_service())
