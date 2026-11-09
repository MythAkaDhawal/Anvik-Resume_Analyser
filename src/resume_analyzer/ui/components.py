"""Reusable presentation components for the ANVIK Streamlit UI.

Adheres strictly to the separation of concerns: presentation only, zero business logic.
Implements the official ANVIK visual identity (Carbon Ink, Warm Ivory, Oxidised Copper,
Aged Graphite, Muted Moss) and layout standards.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.reporting.exporters.base import get_exporter
from resume_analyzer.reporting.provenance import DEFAULT_HUMAN_REVIEW_NOTICE

SCORING_LIMITATIONS = [
    "Weights and thresholds are design defaults, not empirically derived; they must be calibrated on labelled data before production use.",
    "Skill coverage measures the mention of a skill, not underlying proficiency, depth, or recency.",
    "Fuzzy matches can yield false positives; they are clearly flagged as FUZZY and receive only partial credit.",
    "Experience evaluation counts elapsed calendar time, not relevance; year-only dates are approximated.",
    "Education evaluation is ordinal and intentionally ignores institutional prestige to avoid bias.",
    "Unrecognized skills outside the taxonomy are matched by exact string only.",
    "The deterministic score is not a measure of general potential, culture fit, or future job performance.",
]

# Assets directory relative to this file
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


@lru_cache(maxsize=8)
def get_asset_base64(filename: str) -> str:
    """Read a bundled asset and return its base64 data URI string."""
    asset_file = ASSETS_DIR / filename
    if not asset_file.exists():
        asset_file = Path("assets") / filename
    if asset_file.exists():
        encoded = base64.b64encode(asset_file.read_bytes()).decode("ascii")
        ext = asset_file.suffix.lower().lstrip(".")
        mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
        return f"data:{mime};base64,{encoded}"
    return ""


def apply_custom_theme() -> None:
    """Inject the official ANVIK design system CSS tokens and rules."""
    custom_css = """
    <style>
    /* ANVIK Official Design Tokens */
    :root {
      --anvik-carbon: #171817;
      --anvik-surface: #1E201E;
      --anvik-card: #242624;
      --anvik-graphite: #343633;
      --anvik-ivory: #E9E2D2;
      --anvik-ivory-dim: #C5BFB0;
      --anvik-copper: #B66F4B;
      --anvik-copper-hover: #C97D56;
      --anvik-moss: #77765D;
      --anvik-border: #383A37;
      --anvik-border-subtle: #2A2D2A;
    }

    /* Overall page atmosphere */
    .stApp {
      background-color: var(--anvik-carbon);
      color: var(--anvik-ivory);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    }

    /* Refined Headings */
    h1, h2, h3, h4, h5, h6 {
      color: var(--anvik-ivory) !important;
      font-weight: 600 !important;
      letter-spacing: -0.015em !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
      background-color: #121312 !important;
      border-right: 1px solid var(--anvik-border-subtle) !important;
    }

    /* Primary Buttons: Oxidised Copper */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
      background-color: var(--anvik-copper) !important;
      color: #171817 !important;
      font-weight: 600 !important;
      border: 1px solid var(--anvik-copper) !important;
      border-radius: 4px !important;
      letter-spacing: 0.03em !important;
      padding: 0.5rem 1.2rem !important;
      transition: all 0.2s ease !important;
    }

    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
      background-color: var(--anvik-copper-hover) !important;
      border-color: var(--anvik-copper-hover) !important;
      color: #FFFFFF !important;
      box-shadow: 0 2px 8px rgba(182, 111, 75, 0.25) !important;
    }

    /* Secondary Buttons: Aged Graphite */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"],
    .stDownloadButton > button {
      background-color: var(--anvik-card) !important;
      color: var(--anvik-ivory) !important;
      border: 1px solid var(--anvik-border) !important;
      border-radius: 4px !important;
      font-weight: 500 !important;
      transition: all 0.2s ease !important;
    }

    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover,
    .stDownloadButton > button:hover {
      border-color: var(--anvik-copper) !important;
      color: var(--anvik-ivory) !important;
    }

    /* Metric Cards */
    div[data-testid="stMetric"] {
      background-color: var(--anvik-surface);
      border: 1px solid var(--anvik-border);
      border-radius: 6px;
      padding: 14px 18px;
    }
    div[data-testid="stMetricLabel"] {
      color: var(--anvik-ivory-dim) !important;
      font-size: 0.8rem !important;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
      color: var(--anvik-ivory) !important;
      font-weight: 700 !important;
    }

    /* Form Fields & Inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div,
    .stNumberInput > div > div > input {
      background-color: var(--anvik-surface) !important;
      color: var(--anvik-ivory) !important;
      border: 1px solid var(--anvik-border) !important;
      border-radius: 4px !important;
    }

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stNumberInput > div > div > input:focus {
      border-color: var(--anvik-copper) !important;
      box-shadow: 0 0 0 1px var(--anvik-copper) !important;
    }

    /* Radio navigation buttons */
    div[data-testid="stRadio"] > div {
      gap: 6px;
    }
    div[data-testid="stRadio"] label {
      padding: 6px 12px;
      border-radius: 4px;
      border: 1px solid transparent;
      transition: all 0.15s ease;
    }
    div[data-testid="stRadio"] label:hover {
      background-color: var(--anvik-surface);
      border-color: var(--anvik-border);
    }

    /* Tabs */
    button[data-baseweb="tab"] {
      color: var(--anvik-ivory-dim) !important;
      font-weight: 500 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
      color: var(--anvik-ivory) !important;
      border-bottom-color: var(--anvik-copper) !important;
      font-weight: 600 !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
      background-color: var(--anvik-surface) !important;
      border: 1px solid var(--anvik-border) !important;
      border-radius: 6px !important;
    }

    /* Dataframe tables */
    div[data-testid="stDataFrame"] {
      border: 1px solid var(--anvik-border);
      border-radius: 6px;
    }

    /* Custom Brand Banner */
    .anvik-banner {
      background: linear-gradient(180deg, #1A1C1A 0%, #151615 100%);
      border: 1px solid var(--anvik-border);
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      gap: 24px;
    }
    .anvik-banner-emblem {
      width: 80px;
      height: 80px;
      flex-shrink: 0;
    }
    .anvik-banner-title {
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--anvik-ivory);
      letter-spacing: 0.12em;
      margin: 0;
      line-height: 1.1;
    }
    .anvik-banner-subtitle {
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      color: var(--anvik-copper);
      margin: 4px 0 10px 0;
      font-weight: 600;
    }
    .anvik-banner-desc {
      font-size: 0.92rem;
      color: var(--anvik-ivory-dim);
      margin: 0;
      line-height: 1.5;
    }
    .anvik-badge-row {
      display: flex;
      gap: 10px;
      margin-top: 12px;
      flex-wrap: wrap;
    }
    .anvik-badge {
      display: inline-flex;
      align-items: center;
      padding: 3px 10px;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      border: 1px solid var(--anvik-border);
      background-color: var(--anvik-card);
      color: var(--anvik-ivory);
    }
    .anvik-badge-accent {
      border-color: var(--anvik-copper);
      color: var(--anvik-copper);
    }
    .anvik-badge-moss {
      border-color: var(--anvik-moss);
      color: #A8A78D;
    }

    /* Compact Header */
    .anvik-header-compact {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--anvik-border-subtle);
      padding-bottom: 12px;
      margin-bottom: 20px;
    }
    .anvik-header-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .anvik-header-emblem-small {
      width: 36px;
      height: 36px;
    }
    .anvik-header-brand {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: 0.15em;
      color: var(--anvik-ivory);
      margin: 0;
    }
    .anvik-header-tag {
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--anvik-copper);
      margin: 0;
    }

    /* Sidebar Logo */
    .anvik-sidebar-brand {
      text-align: center;
      padding: 12px 0 16px 0;
      border-bottom: 1px solid var(--anvik-border-subtle);
      margin-bottom: 16px;
    }
    .anvik-sidebar-emblem {
      width: 72px;
      height: 72px;
      margin: 0 auto 8px auto;
      display: block;
    }
    .anvik-sidebar-title {
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: 0.22em;
      color: var(--anvik-ivory);
      margin: 0;
      line-height: 1.2;
    }
    .anvik-sidebar-category {
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--anvik-copper);
      margin: 3px 0 0 0;
      font-weight: 600;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def render_anvik_brand_banner(compact: bool = False) -> None:
    """Render the official ANVIK product brand header."""
    icon_b64 = get_asset_base64("anvik_icon.svg") or get_asset_base64("anvik_icon.png")

    if compact:
        img_tag = (
            f'<img src="{icon_b64}" class="anvik-header-emblem-small" alt="ANVIK Logo" />'
            if icon_b64
            else '<span style="color:#B66F4B; font-size:1.5rem;">✦</span>'
        )
        st.markdown(
            f"""
            <div class="anvik-header-compact">
              <div class="anvik-header-left">
                {img_tag}
                <div>
                  <h3 class="anvik-header-brand">ANVIK</h3>
                  <p class="anvik-header-tag">Intelligent Talent Analysis</p>
                </div>
              </div>
              <div class="anvik-badge-row" style="margin-top:0;">
                <span class="anvik-badge anvik-badge-moss">⚙️ Deterministic Core Active</span>
                <span class="anvik-badge">v1.0.0</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        img_tag = (
            f'<img src="{icon_b64}" class="anvik-banner-emblem" alt="ANVIK Logo" />'
            if icon_b64
            else '<span style="color:#B66F4B; font-size:3rem;">✦</span>'
        )
        st.markdown(
            f"""
            <div class="anvik-banner">
              {img_tag}
              <div style="flex:1;">
                <h1 class="anvik-banner-title">ANVIK</h1>
                <p class="anvik-banner-subtitle">Intelligent Talent Analysis</p>
                <p class="anvik-banner-desc">
                  An explainable talent screening system. Combines a rigorous, deterministic Python evaluation core
                  with optional generative AI augmentation. Zero hallucinated matches, strict provenance tracking, and full auditability.
                </p>
                <div class="anvik-badge-row">
                  <span class="anvik-badge anvik-badge-accent">Deterministic Matching Engine</span>
                  <span class="anvik-badge anvik-badge-moss">Human-in-the-Loop Enforced</span>
                  <span class="anvik-badge">Multi-Format Extraction (PDF, DOCX, TXT)</span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_anvik_sidebar_brand() -> None:
    """Render the official ANVIK logo and title in the sidebar."""
    icon_b64 = get_asset_base64("anvik_icon.svg") or get_asset_base64("anvik_icon.png")
    img_tag = (
        f'<img src="{icon_b64}" class="anvik-sidebar-emblem" alt="ANVIK Emblem" />'
        if icon_b64
        else '<div style="color:#B66F4B; font-size:2.5rem; text-align:center;">✦</div>'
    )
    st.sidebar.markdown(
        f"""
        <div class="anvik-sidebar-brand">
          {img_tag}
          <h2 class="anvik-sidebar-title">ANVIK</h2>
          <p class="anvik-sidebar-category">Intelligent Talent Analysis</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_human_review_notice() -> None:
    """Render mandatory human-in-the-loop compliance notice."""
    st.markdown(
        f"""
        <div style="background-color: #202220; border-left: 3px solid #B66F4B; padding: 10px 14px; border-radius: 0 4px 4px 0; margin-bottom: 14px;">
          <div style="color: #B66F4B; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;">Compliance Advisory</div>
          <div style="color: #E9E2D2; font-size: 0.85rem; line-height: 1.4;">{DEFAULT_HUMAN_REVIEW_NOTICE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_scoring_limitations() -> None:
    """Render scoring limitations expander as required by §7.7."""
    with st.expander(
        "ℹ️ Important Scoring Limitations & Advisory (§7.7)", expanded=False
    ):
        for idx, item in enumerate(SCORING_LIMITATIONS, start=1):
            st.markdown(f"**{idx}.** {item}")


def render_provenance_badge(provenance: str) -> str:
    """Return markdown string representing a color-coded provenance badge."""
    p_upper = (provenance or "").upper()
    badges = {
        "EXTRACTED_RULE": "🟢 `EXTRACTED_RULE` (Rule-Based)",
        "EXTRACTED_AI": "🟣 `EXTRACTED_AI` (AI Extraction)",
        "COMPUTED": "🔵 `COMPUTED` (Deterministic)",
        "AI_GENERATED": "🟠 `AI_GENERATED` (AI Insight)",
    }
    return badges.get(p_upper, f"`{provenance}`")


def render_fit_band_metric(fit_band: str, total_score: float) -> None:
    """Render fit band and score highlight with official brand tokens."""
    band_colors = {
        "strong": "#77765D",
        "moderate": "#B66F4B",
        "limited": "#9E7B47",
        "low": "#8C4A4A",
    }
    border_color = band_colors.get(fit_band.lower(), "#B66F4B")

    col1, col2, col3 = st.columns([1.2, 1.2, 2.0])
    with col1:
        st.metric(label="Overall Match Score", value=f"{total_score:.1f} / 100")
    with col2:
        st.metric(label="Fit Band Alignment", value=fit_band.upper())
    with col3:
        st.markdown(
            f"""
            <div style="border-left: 2px solid {border_color}; padding-left: 12px; height: 100%; display: flex; flex-direction: column; justify-content: center;">
              <span style="color: #A39E93; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Scoring Provenance</span>
              <span style="color: #E9E2D2; font-size: 0.88rem; font-weight: 500; margin-top: 2px;">🔵 COMPUTED &bull; Deterministic Engine</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_score_breakdown(report: AnalysisReport) -> None:
    """Render sub-score cards."""
    score = report.score
    st.subheader("Score Breakdown")
    cols = st.columns(len(score.components) if score.components else 1)
    for idx, comp in enumerate(score.components):
        with cols[idx]:
            pts_str = f"{comp.points:.1f}" if comp.points is not None else "0.0"
            max_pts = f"{comp.weight * 100:.0f}"
            label_name = comp.name.replace("_", " ").title()
            st.metric(label=label_name, value=f"{pts_str} / {max_pts}")

    if score.flags:
        with st.expander("Adjustment Details & Audit Flags", expanded=False):
            st.write("**Flags:**", ", ".join(f"`{f}`" for f in score.flags))


def render_skills_view(report: AnalysisReport) -> None:
    """Render skill match analysis tables."""
    match = report.match
    st.subheader("Skill Match Analysis")

    tab1, tab2, tab3 = st.tabs(
        ["Matched Skills", "Missing Required", "Missing Optional"]
    )

    matched = [s for s in match.skill_matches if s.match_type.value != "none"]
    missing_req = [
        s for s in match.skill_matches if s.is_required and s.match_type.value == "none"
    ]
    missing_opt = [
        s
        for s in match.skill_matches
        if not s.is_required and s.match_type.value == "none"
    ]

    with tab1:
        if matched:
            table_data = []
            for s in matched:
                table_data.append(
                    {
                        "Target Skill": s.target,
                        "Candidate Match": s.matched_candidate_skill or "—",
                        "Match Type": s.match_type.value.upper(),
                        "Similarity": f"{s.similarity:.1f}%",
                        "Credit": f"{s.credit:.2f}",
                        "Requirement": "Required" if s.is_required else "Optional",
                    }
                )
            st.dataframe(table_data, use_container_width=True)
        else:
            st.write("No matching skills found.")

    with tab2:
        if missing_req:
            st.markdown(
                f"""
                <div style="background-color: #2B1D1D; border-left: 3px solid #B66F4B; padding: 10px 14px; border-radius: 4px; margin-bottom: 12px;">
                  <strong style="color: #E9E2D2;">Missing {len(missing_req)} required skill(s):</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )
            for req in missing_req:
                st.markdown(f"- **{req.target}**")
        else:
            st.success("All required skills satisfied!")

    with tab3:
        if missing_opt:
            st.info(f"Missing {len(missing_opt)} optional skill(s):")
            for opt in missing_opt:
                st.markdown(f"- {opt.target}")
        else:
            st.write("All optional skills matched.")


def render_experience_education_view(report: AnalysisReport) -> None:
    """Render experience and education details."""
    cand = report.candidate
    exp_eval = report.match.experience
    edu_eval = report.match.education

    st.subheader("Experience & Education Details")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Experience Alignment")
        years = (
            cand.total_experience_years
            if cand.total_experience_years is not None
            else 0.0
        )
        st.write(f"**Total Experience:** {years:.1f} years ({int(years * 12)} months)")
        st.write(f"**Status:** `{exp_eval.status.upper()}`")
        credit = exp_eval.subscore if exp_eval.subscore is not None else 0.0
        st.write(f"**Credits Awarded:** {credit:.2f} / 1.00")
        if exp_eval.gap_years:
            st.warning(f"Experience gap: {exp_eval.gap_years:.1f} year(s) deficient")

    with col2:
        st.markdown("#### Education Attainment")
        st.write(f"**Detected Level:** `{cand.highest_education_level.value}`")
        st.write(f"**Status:** `{edu_eval.status.upper()}`")
        edu_credit = edu_eval.subscore if edu_eval.subscore is not None else 0.0
        st.write(f"**Credits Awarded:** {edu_credit:.2f} / 1.00")
        if cand.education:
            for entry in cand.education:
                deg_title = entry.degree or entry.level.value
                st.caption(
                    f"• {deg_title} ({entry.institution or 'Institution unspecified'})"
                )


def render_ai_insights_view(report: AnalysisReport) -> None:
    """Render optional AI insights (P3 explanation, P4 recommendations, P5 questions)."""
    ai = report.ai
    st.subheader("AI Analysis & Insights")

    has_ai = any(
        [
            ai.explanation and ai.explanation.data,
            ai.recommendations and ai.recommendations.data,
            ai.interview_questions and ai.interview_questions.data,
        ]
    )

    if not has_ai:
        st.info(
            "AI insights were disabled or unavailable for this analysis run. (Pure deterministic core operation)"
        )
        return

    st.caption("Provenance: 🟠 AI_GENERATED (Advisory analysis only &bull; non-authoritative)")

    if ai.explanation and ai.explanation.data:
        exp_data = ai.explanation.data
        with st.expander("Match Explanation (P3)", expanded=True):
            if hasattr(exp_data, "strengths") and exp_data.strengths:
                st.markdown("**Identified Strengths:**")
                for s in exp_data.strengths:
                    pt = getattr(s, "point", str(s))
                    ev = getattr(s, "evidence", [])
                    st.markdown(f"- **{pt}**: {', '.join(ev) if ev else ''}")
            if hasattr(exp_data, "concerns") and exp_data.concerns:
                st.markdown("**Identified Concerns:**")
                for c in exp_data.concerns:
                    pt = getattr(c, "point", str(c))
                    ev = getattr(c, "evidence", [])
                    st.markdown(f"- **{pt}**: {', '.join(ev) if ev else ''}")

    if ai.recommendations and ai.recommendations.data:
        rec_data = ai.recommendations.data
        recs = (
            getattr(rec_data, "recommendations", rec_data)
            if not isinstance(rec_data, list)
            else rec_data
        )
        with st.expander("Upskilling Recommendations (P4)", expanded=False):
            for r in recs:
                skill = getattr(r, "skill", str(r))
                prio = getattr(r, "priority", "Normal")
                reason = getattr(r, "reason", "")
                st.markdown(f"- **{skill}** ({prio} Priority): {reason}")

    if ai.interview_questions and ai.interview_questions.data:
        q_data = ai.interview_questions.data
        questions = (
            getattr(q_data, "questions", q_data)
            if not isinstance(q_data, list)
            else q_data
        )
        with st.expander("Role-Specific Interview Questions (P5)", expanded=False):
            for idx, q in enumerate(questions, start=1):
                topic = getattr(q, "target_topic", "General")
                question_text = getattr(q, "question", str(q))
                rationale = getattr(q, "rationale", "")
                st.markdown(f"**{idx}. [{topic}]** {question_text}")
                if rationale:
                    st.caption(f"*Rationale:* {rationale}")


def render_export_downloads(report: AnalysisReport) -> None:
    """Render report download buttons for HTML, PDF, and Excel formats."""
    st.subheader("Export Report")
    c1, c2, c3 = st.columns(3)

    with c1:
        html_bytes = get_exporter("html").export_bytes(report)
        st.download_button(
            label="📄 Download HTML Report",
            data=html_bytes,
            file_name=f"anvik_report_{report.candidate.candidate_id}.html",
            mime="text/html",
            use_container_width=True,
        )

    with c2:
        pdf_bytes = get_exporter("pdf").export_bytes(report)
        st.download_button(
            label="📑 Download PDF Report",
            data=pdf_bytes,
            file_name=f"anvik_report_{report.candidate.candidate_id}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with c3:
        xlsx_bytes = get_exporter("xlsx").export_bytes(report)
        st.download_button(
            label="📊 Download Excel Workbook",
            data=xlsx_bytes,
            file_name=f"anvik_report_{report.candidate.candidate_id}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_feedback_widget(report: AnalysisReport) -> None:
    """Render user feedback submission form for continuous quality evaluation (FR-29)."""
    st.subheader("Evaluation Feedback")
    with st.expander("📝 Rate Analysis Quality & Suggest Corrections", expanded=False):
        with st.form(f"feedback_form_{report.report_id}"):
            rating = st.slider(
                "Quality Rating (1 = Poor, 5 = Excellent)",
                min_value=1,
                max_value=5,
                value=5,
            )
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                skills_thumb = st.checkbox("Skills match was accurate", value=True)
            with col_t2:
                exp_thumb = st.checkbox("Experience analysis was accurate", value=True)
            corrected_raw = st.text_input(
                "Corrected Skills (comma-separated, if any)",
                placeholder="e.g. Python, SQL",
            )
            comment = st.text_area(
                "Reviewer Comments (Max 1000 characters)", max_chars=1000
            )
            submitted = st.form_submit_button(
                "Submit Feedback", use_container_width=True
            )

        if submitted:
            from resume_analyzer.storage.feedback_store import (
                FeedbackRecord,
                FeedbackStore,
            )

            corrected = [s.strip() for s in corrected_raw.split(",") if s.strip()]
            record = FeedbackRecord(
                report_id=report.report_id,
                rating=rating,
                comment=comment.strip() or None,
                section_feedback={"skills": skills_thumb, "experience": exp_thumb},
                corrected_skills=corrected,
            )
            store = FeedbackStore()
            store.append(record)
            st.success("Thank you! Your feedback has been safely recorded.")
