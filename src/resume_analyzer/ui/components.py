"""Reusable presentation components for the Streamlit UI.

Adheres strictly to the separation of concerns: presentation only, zero business logic.
"""

from __future__ import annotations

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


def render_human_review_notice() -> None:
    """Render mandatory human-in-the-loop compliance notice."""
    st.info(f"**Notice:** {DEFAULT_HUMAN_REVIEW_NOTICE}")


def render_scoring_limitations() -> None:
    """Render scoring limitations expander as required by §7.7."""
    with st.expander("ℹ️ Important Scoring Limitations & Advisory (§7.7)", expanded=False):
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
    """Render fit band and score highlight."""
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.metric(label="Overall Match Score", value=f"{total_score:.1f} / 100")
    with col2:
        st.metric(label="Fit Band", value=fit_band)
    with col3:
        st.caption("Provenance: 🔵 COMPUTED (Deterministic Python scoring)")


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
        with st.expander("Adjustment Details & Flags", expanded=False):
            st.write("**Flags:**", ", ".join(f"`{f}`" for f in score.flags))


def render_skills_view(report: AnalysisReport) -> None:
    """Render skill match analysis tables."""
    match = report.match
    st.subheader("Skill Match Analysis")

    tab1, tab2, tab3 = st.tabs(["Matched Skills", "Missing Required", "Missing Optional"])

    matched = [s for s in match.skill_matches if s.match_type.value != "none"]
    missing_req = [s for s in match.skill_matches if s.is_required and s.match_type.value == "none"]
    missing_opt = [s for s in match.skill_matches if not s.is_required and s.match_type.value == "none"]

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
            st.error(f"Missing {len(missing_req)} required skill(s):")
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
        st.markdown("#### Experience")
        years = cand.total_experience_years if cand.total_experience_years is not None else 0.0
        st.write(f"**Total Experience:** {years:.1f} years ({int(years * 12)} months)")
        st.write(f"**Status:** {exp_eval.status}")
        credit = exp_eval.subscore if exp_eval.subscore is not None else 0.0
        st.write(f"**Credits Awarded:** {credit:.2f} / 1.00")
        if exp_eval.gap_years:
            st.warning(f"Experience gap: {exp_eval.gap_years:.1f} year(s) deficient")

    with col2:
        st.markdown("#### Education")
        st.write(f"**Detected Level:** {cand.highest_education_level.value}")
        st.write(f"**Status:** {edu_eval.status}")
        edu_credit = edu_eval.subscore if edu_eval.subscore is not None else 0.0
        st.write(f"**Credits Awarded:** {edu_credit:.2f} / 1.00")
        if cand.education:
            for entry in cand.education:
                deg_title = entry.degree or entry.level.value
                st.caption(f"• {deg_title} ({entry.institution or 'Institution unspecified'})")


def render_ai_insights_view(report: AnalysisReport) -> None:
    """Render optional AI insights (P3 explanation, P4 recommendations, P5 questions)."""
    ai = report.ai
    st.subheader("AI Analysis & Insights")

    has_ai = any([
        ai.explanation and ai.explanation.data,
        ai.recommendations and ai.recommendations.data,
        ai.interview_questions and ai.interview_questions.data,
    ])

    if not has_ai:
        st.info("AI insights were disabled or unavailable for this analysis run. (Deterministic core operation)")
        return

    st.caption("Provenance: 🟠 AI_GENERATED (Non-authoritative analysis advisory)")

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
        recs = getattr(rec_data, "recommendations", rec_data) if not isinstance(rec_data, list) else rec_data
        with st.expander("Upskilling Recommendations (P4)", expanded=False):
            for r in recs:
                skill = getattr(r, "skill", str(r))
                prio = getattr(r, "priority", "Normal")
                reason = getattr(r, "reason", "")
                st.markdown(f"- **{skill}** ({prio} Priority): {reason}")

    if ai.interview_questions and ai.interview_questions.data:
        q_data = ai.interview_questions.data
        questions = getattr(q_data, "questions", q_data) if not isinstance(q_data, list) else q_data
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
            label="Download HTML Report",
            data=html_bytes,
            file_name=f"report_{report.candidate.candidate_id}.html",
            mime="text/html",
            use_container_width=True,
        )

    with c2:
        pdf_bytes = get_exporter("pdf").export_bytes(report)
        st.download_button(
            label="Download PDF Report",
            data=pdf_bytes,
            file_name=f"report_{report.candidate.candidate_id}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with c3:
        xlsx_bytes = get_exporter("xlsx").export_bytes(report)
        st.download_button(
            label="Download Excel Workbook",
            data=xlsx_bytes,
            file_name=f"report_{report.candidate.candidate_id}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_feedback_widget(report: AnalysisReport) -> None:
    """Render user feedback submission form for continuous quality evaluation (FR-29)."""
    st.subheader("Evaluation Feedback")
    with st.expander("📝 Rate Analysis Quality & Suggest Corrections", expanded=False):
        with st.form(f"feedback_form_{report.report_id}"):
            rating = st.slider("Quality Rating (1 = Poor, 5 = Excellent)", min_value=1, max_value=5, value=5)
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                skills_thumb = st.checkbox("Skills match was accurate", value=True)
            with col_t2:
                exp_thumb = st.checkbox("Experience analysis was accurate", value=True)
            corrected_raw = st.text_input("Corrected Skills (comma-separated, if any)", placeholder="e.g. Python, SQL")
            comment = st.text_area("Reviewer Comments (Max 1000 characters)", max_chars=1000)
            submitted = st.form_submit_button("Submit Feedback", use_container_width=True)

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

