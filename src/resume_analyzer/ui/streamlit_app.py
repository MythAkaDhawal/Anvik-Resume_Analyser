"""Streamlit main web application for the Intelligent Resume Analyzer.

Implements multi-step workflow W-1 through W-4 (PROJECT_REQUIREMENTS §5) with
deterministic Python core and optional GenAI enhancements.
"""

from __future__ import annotations

import logging

import streamlit as st

from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import AnalysisReport
from resume_analyzer.reporting.exporters.base import export_batch_workbook
from resume_analyzer.services.analysis_service import AnalysisOptions
from resume_analyzer.storage.feedback_store import FeedbackStore
from resume_analyzer.storage.result_store import ResultStore
from resume_analyzer.ui.components import (
    apply_custom_theme,
    render_ai_insights_view,
    render_anvik_brand_banner,
    render_anvik_sidebar_brand,
    render_experience_education_view,
    render_export_downloads,
    render_feedback_widget,
    render_fit_band_metric,
    render_human_review_notice,
    render_score_breakdown,
    render_scoring_limitations,
    render_skills_view,
)
from resume_analyzer.ui.state import (
    PAGES,
    clear_results,
    get_batch_runner,
    init_session_state,
    set_page,
)

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="ANVIK — Intelligent Talent Analysis",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """Main Streamlit application entry point."""
    init_session_state()
    apply_custom_theme()

    # --- Sidebar Navigation ---
    render_anvik_sidebar_brand()

    # Synchronize programmatic navigation with sidebar radio
    if st.session_state.get("_last_synced_page") != st.session_state["current_page"]:
        st.session_state["nav_radio"] = st.session_state["current_page"]
        st.session_state["_last_synced_page"] = st.session_state["current_page"]

    def _on_nav_change() -> None:
        st.session_state["current_page"] = st.session_state["nav_radio"]
        st.session_state["_last_synced_page"] = st.session_state["nav_radio"]

    st.sidebar.radio(
        "Workflow Steps",
        PAGES,
        key="nav_radio",
        on_change=_on_nav_change,
    )
    st.session_state["current_page"] = st.session_state["nav_radio"]

    st.sidebar.divider()
    render_human_review_notice()

    # Sidebar active summary
    job_val = st.session_state.get("job")
    rep_count = len(st.session_state.get("reports", []))
    ai_on = st.session_state.get("options", AnalysisOptions()).ai_enabled
    st.sidebar.markdown(
        f"""
        <div style="font-size: 0.8rem; color: #A39E93; line-height: 1.6; padding: 4px 0;">
          <div><strong>Role:</strong> {job_val.title if job_val else "<em>Not configured</em>"}</div>
          <div><strong>Ranked:</strong> {rep_count} candidates</div>
          <div><strong>Engine:</strong> Deterministic Core</div>
          <div><strong>AI Augmentation:</strong> {"Active (P1–P5)" if ai_on else "Off (Offline Core)"}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    current_page = st.session_state["current_page"]

    if current_page == "1 Job":
        render_job_page()
    elif current_page == "2 Resumes":
        render_resumes_page()
    elif current_page == "3 Results":
        render_results_page()
    elif current_page == "4 Reports":
        render_reports_page()
    elif current_page == "5 History":
        render_history_page()


# -----------------------------------------------------------------------------
# 1. Job Page
# -----------------------------------------------------------------------------
def render_job_page() -> None:
    """Render Job Requirements definition page."""
    render_anvik_brand_banner(compact=False)
    st.title("Step 1: Define Job Requirements")
    st.write(
        "Enter target job role specifications. All resume matching and scoring are executed "
        "deterministically against these criteria."
    )

    existing_job: JobRequirements | None = st.session_state.get("job")

    if existing_job:
        c_status, c_fwd = st.columns([3, 1])
        with c_status:
            st.info(
                f"Currently configured role: **{existing_job.title}** "
                f"({len(existing_job.required_skills)} required skill{'s' if len(existing_job.required_skills) != 1 else ''}). "
                "Update below or proceed to candidate resumes."
            )
        with c_fwd:
            if st.button("Proceed to Upload Resumes ➡️", key="btn_fwd_step2_top", use_container_width=True):
                set_page("2 Resumes")
                st.rerun()

    with st.form("job_form"):
        title = st.text_input(
            "Job Title *",
            value=existing_job.title if existing_job else "",
            placeholder="e.g. Senior Python Developer",
            help="1–100 characters.",
        )

        required_skills_raw = st.text_area(
            "Required Skills (comma-separated) *",
            value=", ".join(existing_job.required_skills) if existing_job else "",
            placeholder="e.g. Python, SQL, Docker, AWS",
            help="At least one required skill is mandatory.",
        )

        optional_skills_raw = st.text_area(
            "Optional / Nice-to-have Skills (comma-separated)",
            value=", ".join(existing_job.optional_skills) if existing_job else "",
            placeholder="e.g. Kubernetes, FastAPI, Redis",
        )

        c1, c2 = st.columns(2)
        with c1:
            min_exp = st.number_input(
                "Minimum Experience (Years)",
                min_value=0.0,
                max_value=50.0,
                step=0.5,
                value=float(existing_job.min_experience_years) if existing_job else 0.0,
            )
        with c2:
            edu_options = [e.name for e in EducationLevel]
            default_edu_idx = (
                edu_options.index(existing_job.min_education_level.name)
                if existing_job and existing_job.min_education_level
                else 0
            )
            min_edu = st.selectbox(
                "Minimum Education Level",
                edu_options,
                index=default_edu_idx,
            )

        fields_raw = st.text_input(
            "Preferred Fields of Study (comma-separated)",
            value=", ".join(existing_job.preferred_fields) if existing_job else "",
            placeholder="e.g. Computer Science, Software Engineering",
        )

        context_desc = st.text_area(
            "Job Description Context (Optional)",
            value=existing_job.description
            if existing_job and existing_job.description
            else "",
            placeholder="Full job description context...",
            max_chars=5000,
        )

        st.subheader("Analysis & Scoring Options")
        strategy_choice = st.selectbox(
            "Scoring Strategy",
            ["weighted", "basic"],
            index=0 if st.session_state["options"].strategy == "weighted" else 1,
            help="Weighted: 50% Req, 15% Opt, 20% Exp, 15% Edu. Basic: 70% Skills, 20% Exp, 10% Edu.",
        )

        ai_master = st.checkbox(
            "Enable Optional AI Insights (P1–P5)",
            value=st.session_state["options"].ai_enabled,
            help="Pure deterministic core runs when disabled. Requires configured AI provider.",
        )

        ai_p1 = False
        ai_p2 = False
        ai_p3 = False
        ai_p4 = False
        ai_p5 = False
        if ai_master:
            ac1, ac2 = st.columns(2)
            with ac1:
                ai_p1 = st.checkbox("P1: AI Candidate Extraction", value=True)
                ai_p2 = st.checkbox("P2: Skill Categorization", value=True)
                ai_p3 = st.checkbox("P3: Match Explanation", value=True)
            with ac2:
                ai_p4 = st.checkbox("P4: Upskilling Recommendations", value=True)
                ai_p5 = st.checkbox("P5: Interview Questions", value=True)

        submitted = st.form_submit_button(
            "Save & Proceed to Upload Resumes ➡️",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        # Validate inputs
        req_list = [s.strip() for s in required_skills_raw.split(",") if s.strip()]
        opt_list = [s.strip() for s in optional_skills_raw.split(",") if s.strip()]
        fields_list = [f.strip() for f in fields_raw.split(",") if f.strip()]

        errors = []
        if not title.strip():
            errors.append("Job title cannot be empty.")
        if not req_list:
            errors.append("At least one required skill must be provided.")

        if errors:
            for err in errors:
                st.error(f"Validation error: {err}")
        else:
            try:
                job_obj = JobRequirements(
                    job_title=title.strip(),
                    required_skills=req_list,
                    optional_skills=opt_list,
                    min_experience_years=float(min_exp),
                    min_education_level=EducationLevel.from_string(min_edu),
                    preferred_fields=fields_list,
                    description=context_desc.strip() or None,
                )
                st.session_state["job"] = job_obj
                st.session_state["options"] = AnalysisOptions(
                    strategy=strategy_choice,
                    ai_enabled=ai_master,
                    ai_extract_candidate=ai_p1 if ai_master else False,
                    ai_categorize_skills=ai_p2 if ai_master else False,
                    ai_explain_match=ai_p3 if ai_master else False,
                    ai_recommendations=ai_p4 if ai_master else False,
                    ai_interview_questions=ai_p5 if ai_master else False,
                )
                set_page("2 Resumes")
                st.rerun()
            except Exception as e:
                st.error(f"Invalid Job Requirements: {e}")

    render_scoring_limitations()


# -----------------------------------------------------------------------------
# 2. Resumes Page
# -----------------------------------------------------------------------------
def render_resumes_page() -> None:
    """Render resume file upload and batch analysis launch page."""
    render_anvik_brand_banner(compact=True)
    st.title("Step 2: Upload Resumes")

    job: JobRequirements | None = st.session_state.get("job")
    if not job:
        st.warning(
            "⚠️ No job requirements configured yet. Please complete Step 1 first."
        )
        if st.button("Go to Step 1: Define Job"):
            set_page("1 Job")
            st.rerun()
        return

    c_job_info, c_job_edit = st.columns([3, 1])
    with c_job_info:
        st.info(
            f"Target Role: **{job.title}** ({len(job.required_skills)} required skills)"
        )
    with c_job_edit:
        if st.button("⬅️ Edit Job (Step 1)", key="btn_edit_job_step2", use_container_width=True):
            set_page("1 Job")
            st.rerun()

    uploaded_files = st.file_uploader(
        "Select candidate resumes (.pdf, .docx, .txt)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Upload single or multiple resumes up to 5MB each.",
    )

    if uploaded_files:
        st.write(f"**{len(uploaded_files)} file(s) ready for analysis:**")
        cols = st.columns(3)
        for idx, f in enumerate(uploaded_files):
            cols[idx % 3].caption(f"📄 {f.name} ({f.size / 1024:.1f} KB)")

    col_run, col_clear, col_back = st.columns([2, 1, 1])
    with col_run:
        run_clicked = st.button(
            "🚀 Run Analysis", type="primary", use_container_width=True
        )
    with col_clear:
        if st.button("Clear Past Results", use_container_width=True):
            clear_results()
            st.success("Results cleared.")
    with col_back:
        if st.button("⬅️ Back to Step 1", key="btn_back_step1_footer", use_container_width=True):
            set_page("1 Job")
            st.rerun()

    if run_clicked:
        if not uploaded_files:
            st.error("Please upload at least one resume file to analyze.")
            return

        file_payloads = [(f.name, f.getvalue()) for f in uploaded_files]
        batch_runner = get_batch_runner()
        progress_bar = st.progress(0.0, text="Initializing batch analysis...")

        def update_progress(done: int, total: int, current_file: str) -> None:
            pct = done / float(total) if total > 0 else 1.0
            progress_bar.progress(pct, text=f"Analyzing {done}/{total}: {current_file}")

        with st.spinner("Processing resumes through deterministic engine..."):
            result = batch_runner.run(
                files=file_payloads,
                job=job,
                options=st.session_state["options"],
                progress=update_progress,
            )

        st.session_state["reports"] = result.reports
        st.session_state["failures"] = result.failures
        st.session_state["selected_report_idx"] = 0

        # Auto-save successfully analyzed reports to persistence store (FR-27)
        store = ResultStore()
        for r in result.reports:
            try:
                store.save(r)
            except Exception as err:
                logger.warning(
                    "Could not auto-save report %s: %s",
                    getattr(r, "report_id", "unknown"),
                    err,
                )

        st.success(
            f"Analysis complete! {len(result.reports)} succeeded, {len(result.failures)} failed."
        )
        set_page("3 Results")
        st.rerun()


# -----------------------------------------------------------------------------
# 3. Results Page
# -----------------------------------------------------------------------------
def render_results_page() -> None:
    """Render candidate ranking and detailed scorecard view."""
    render_anvik_brand_banner(compact=True)
    st.title("Step 3: Screening Results & Ranking")

    reports: list[AnalysisReport] = st.session_state.get("reports", [])
    failures = st.session_state.get("failures", [])

    if not reports and not failures:
        st.info(
            "No analysis results found. Please upload resumes and run analysis in Step 2."
        )
        if st.button("Go to Step 2: Upload Resumes"):
            set_page("2 Resumes")
            st.rerun()
        return

    # Render any batch failures in an isolated table
    if failures:
        st.error(f"⚠️ {len(failures)} file(s) failed validation or ingestion:")
        failure_rows = [
            {"File": f.display_name, "Code": f.error_code, "Reason": f.user_message}
            for f in failures
        ]
        st.table(failure_rows)

    if not reports:
        st.warning("All uploaded files failed processing.")
        return

    # Summary metrics
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total Candidates Ranked", len(reports))
    with m2:
        top_score = reports[0].score.total_score if reports else 0.0
        st.metric("Top Score", f"{top_score:.1f} / 100")
    with m3:
        avg_score = sum(r.score.total_score for r in reports) / len(reports)
        st.metric("Average Score", f"{avg_score:.1f} / 100")

    st.divider()

    # Candidate Ranking Table
    st.subheader("Candidate Rankings")
    ranking_rows = []
    for rank, r in enumerate(reports, start=1):
        cand = r.candidate
        score = r.score
        ranking_rows.append(
            {
                "Rank": rank,
                "Candidate": cand.name or "Anonymous",
                "Score": f"{score.total_score:.1f}",
                "Fit Band": score.fit_band.value,
                "Matched Skills": len(
                    [s for s in r.match.skill_matches if s.match_type.value != "none"]
                ),
                "Missing Req": len(
                    [
                        s
                        for s in r.match.skill_matches
                        if s.is_required and s.match_type.value == "none"
                    ]
                ),
                "Experience (Yrs)": f"{cand.total_experience_years or 0.0:.1f}",
                "Education": cand.highest_education_level.value,
            }
        )
    st.dataframe(ranking_rows, use_container_width=True)

    st.divider()

    # Detailed Single Candidate View
    st.subheader("Candidate Detailed Assessment")
    cand_options = [
        f"#{i + 1}: {r.candidate.name or 'Anonymous'} (Score: {r.score.total_score:.1f} - {r.score.fit_band.value})"
        for i, r in enumerate(reports)
    ]
    selected_idx = st.selectbox(
        "Select candidate to inspect:",
        range(len(cand_options)),
        format_func=lambda i: cand_options[i],
        index=st.session_state.get("selected_report_idx", 0),
    )
    st.session_state["selected_report_idx"] = selected_idx

    active_report = reports[selected_idx]

    # Candidate header
    st.markdown(f"### {active_report.candidate.name or 'Anonymous'}")
    cinfo1, cinfo2 = st.columns(2)
    with cinfo1:
        st.write(f"**Email:** {active_report.candidate.email or 'Not provided'}")
        st.write(f"**Candidate ID:** `{active_report.candidate.candidate_id}`")
    with cinfo2:
        st.write(f"**Report ID:** `{active_report.report_id}`")
        st.write(f"**Strategy Used:** `{active_report.score.strategy_name}`")

    # Metrics & Breakdown
    render_fit_band_metric(
        active_report.score.fit_band.value,
        active_report.score.total_score,
    )
    render_score_breakdown(active_report)
    render_skills_view(active_report)
    render_experience_education_view(active_report)
    render_ai_insights_view(active_report)

    # Reviewer evaluation and continuous improvement feedback (FR-29)
    render_feedback_widget(active_report)

    st.divider()
    c_nav_back, c_nav_fwd = st.columns(2)
    with c_nav_back:
        if st.button(
            "⬅️ Back to Step 2: Upload Resumes",
            key="btn_back_step2",
            use_container_width=True,
        ):
            set_page("2 Resumes")
            st.rerun()
    with c_nav_fwd:
        if st.button(
            "Proceed to Export Reports ➡️",
            key="btn_fwd_step4",
            type="primary",
            use_container_width=True,
        ):
            set_page("4 Reports")
            st.rerun()


# -----------------------------------------------------------------------------
# 4. Reports Page
# -----------------------------------------------------------------------------
def render_reports_page() -> None:
    """Render export page for individual reports and batch Excel workbooks."""
    render_anvik_brand_banner(compact=True)
    st.title("Step 4: Export Reports")

    reports: list[AnalysisReport] = st.session_state.get("reports", [])
    if not reports:
        st.info("No analyzed reports to export. Please run analysis first.")
        if st.button("Go to Step 1: Define Job"):
            set_page("1 Job")
            st.rerun()
        return

    # Batch export section if multiple reports
    if len(reports) > 1:
        st.subheader("Batch Ranking Export")
        st.write(
            "Export all candidate evaluations into a consolidated Excel ranking workbook."
        )
        batch_xlsx = export_batch_workbook(reports)
        st.download_button(
            label=f"📊 Download Batch Ranking Workbook ({len(reports)} Candidates)",
            data=batch_xlsx,
            file_name="batch_ranking_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
        st.divider()

    # Individual report export section
    cand_options = [
        f"#{i + 1}: {r.candidate.name or 'Anonymous'} (Score: {r.score.total_score:.1f})"
        for i, r in enumerate(reports)
    ]
    selected_idx = st.selectbox(
        "Choose candidate report to download:",
        range(len(cand_options)),
        format_func=lambda i: cand_options[i],
        index=st.session_state.get("selected_report_idx", 0),
    )
    active_report = reports[selected_idx]

    render_export_downloads(active_report)
    st.divider()
    render_scoring_limitations()

    st.divider()
    c_rep_back, c_rep_fwd = st.columns(2)
    with c_rep_back:
        if st.button(
            "⬅️ Back to Step 3: Screening Results",
            key="btn_back_step3",
            use_container_width=True,
        ):
            set_page("3 Results")
            st.rerun()
    with c_rep_fwd:
        if st.button(
            "Proceed to History & Diagnostics ➡️",
            key="btn_fwd_step5",
            type="primary",
            use_container_width=True,
        ):
            set_page("5 History")
            st.rerun()


# -----------------------------------------------------------------------------
# 5. History Page
# -----------------------------------------------------------------------------
def render_history_page() -> None:
    """Render historical analysis viewer, retention manager, and feedback diagnostics (FR-28, NFR-19)."""
    render_anvik_brand_banner(compact=True)
    st.title("Step 5: History & Persistence")
    st.caption(
        "Manage saved analyses, reload past evaluations, configure data retention, and review feedback."
    )

    store = ResultStore()
    summaries = store.list()

    if not summaries:
        st.info(
            "No saved analyses found in `data/results/`. Run an analysis in Step 2 to generate records."
        )
    else:
        st.subheader(f"Saved Analyses ({len(summaries)})")
        table_data = [
            {
                "Report ID": s.report_id,
                "Candidate": s.candidate_name or "Anonymous",
                "Score": f"{s.total_score:.1f}" if s.total_score is not None else "—",
                "Fit Band": s.fit_band or "—",
                "Date (UTC)": s.created_at.strftime("%Y-%m-%d %H:%M")
                if s.created_at
                else "—",
                "Status": "✅ OK" if s.readable else "⚠️ Unreadable",
            }
            for s in summaries
        ]
        st.dataframe(table_data, use_container_width=True)

        readable_summaries = [s for s in summaries if s.readable]
        if readable_summaries:
            st.divider()
            st.subheader("Manage Saved Analysis")
            options_labels = [
                f"{s.candidate_name or 'Anonymous'} — ID: {s.report_id} (Score: {s.total_score or 0.0:.1f})"
                for s in readable_summaries
            ]
            chosen_idx = st.selectbox(
                "Select analysis record:",
                range(len(options_labels)),
                format_func=lambda i: options_labels[i],
                key="history_selected_record",
            )
            chosen_summary = readable_summaries[chosen_idx]

            col_load, col_del = st.columns([1, 1])
            with col_load:
                if st.button(
                    "📥 Reload Analysis into Results",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        loaded = store.load(chosen_summary.report_id)
                        st.session_state["reports"] = [loaded]
                        st.session_state["selected_report_idx"] = 0
                        set_page("3 Results")
                        st.success(
                            f"Loaded analysis for {loaded.candidate.name or 'Candidate'}"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to reload analysis: {e}")

            with col_del:
                if st.button(
                    f"🗑️ Delete Analysis ({chosen_summary.report_id[:17]}...)",
                    use_container_width=True,
                ):
                    try:
                        store.delete(chosen_summary.report_id)
                        st.success(f"Deleted report `{chosen_summary.report_id}`")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete analysis: {e}")

    # Retention & Purging Section (FR-28, NFR-19)
    st.divider()
    st.subheader("Data Retention & Cleanup")
    col_p1, col_p2 = st.columns([2, 1])
    with col_p1:
        purge_days = st.number_input(
            "Purge analyses older than (days):",
            min_value=1,
            max_value=365,
            value=30,
            step=1,
        )
    with col_p2:
        st.write("")
        st.write("")
        if st.button("🧹 Purge Old Records", use_container_width=True):
            purged = store.purge_older_than(int(purge_days))
            st.success(
                f"Purged {purged} analysis record(s) older than {purge_days} day(s)."
            )
            st.rerun()

    with st.expander("⚠️ Danger Zone: Delete All Data", expanded=False):
        st.warning("This will permanently remove all saved analysis records from disk.")
        confirm_delete_all = st.checkbox(
            "I confirm that I want to delete all saved analyses."
        )
        if st.button(
            "Permanently Delete All Analyses",
            type="secondary",
            disabled=not confirm_delete_all,
        ):
            count = store.delete_all()
            st.success(f"Successfully deleted all {count} saved analysis file(s).")
            st.rerun()

    # Reviewer Feedback Summary Section (FR-29)
    st.divider()
    st.subheader("Reviewer Feedback & Model Quality Diagnostics")
    fb_store = FeedbackStore()
    fb_summary = fb_store.summarize()

    if fb_summary.total_submissions == 0:
        st.info(
            "No reviewer feedback recorded yet (`data/feedback.jsonl`). Submit feedback in Step 3 to populate."
        )
    else:
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Total Submissions", fb_summary.total_submissions)
        with m2:
            st.metric("Average Star Rating", f"{fb_summary.average_rating:.2f} / 5.00")

        if fb_summary.section_positive_ratios:
            st.write("**Section Quality Approval Ratios:**")
            for sec, ratio in fb_summary.section_positive_ratios.items():
                st.write(f"- **{sec.title()}**: {ratio * 100:.1f}% positive")

        if fb_summary.top_corrected_skills:
            st.write("**Top Corrected Skills:**")
            for sk, cnt in fb_summary.top_corrected_skills:
                st.write(f"- `{sk}` ({cnt} correction{'s' if cnt > 1 else ''})")

    st.divider()
    if st.button("⬅️ Back to Step 4: Export Reports", key="btn_back_step4"):
        set_page("4 Reports")
        st.rerun()


if __name__ == "__main__":
    main()
