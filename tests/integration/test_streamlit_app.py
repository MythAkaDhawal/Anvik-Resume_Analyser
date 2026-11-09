"""Integration smoke test for the Streamlit UI application (IT-06, FR-31).

Verifies that the application starts cleanly without unhandled exceptions,
enforces job form validation, handles navigation, displays candidate scores,
and presents export action buttons.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from resume_analyzer.models.candidate import (
    Candidate,
    EducationEntry,
    ExperienceEntry,
    Skill,
)
from resume_analyzer.models.enums import (
    ComponentStatus,
    EducationLevel,
    FitBand,
    MatchType,
)
from resume_analyzer.models.results import (
    AIInsights,
    AnalysisReport,
    EducationAnalysis,
    ExperienceAnalysis,
    MatchResult,
    ScoreComponent,
    ScoreResult,
    SkillMatch,
)


@pytest.fixture(autouse=True)
def mock_component_manifests() -> None:
    """Mock component manifest scanning to avoid Windows disk scan bottlenecks."""
    with patch(
        "streamlit.components.v2.manifest_scanner.scan_component_manifests",
        return_value=[],
    ):
        yield


def test_it_06_streamlit_app_smoke() -> None:
    """Smoke test Streamlit UI navigation, validation, score display, and exports (IT-06)."""
    # 1. App starts without unhandled exception
    app_path = (
        Path(__file__).parent.parent.parent / "src/resume_analyzer/ui/streamlit_app.py"
    ).resolve()
    at = AppTest.from_file(str(app_path), default_timeout=15)
    at.run()
    assert len(at.exception) == 0, f"App crashed on startup with: {at.exception}"
    assert len(at.title) > 0
    assert "Step 1: Define Job Requirements" in at.title[0].value

    # 2. Form validation error when submitting blank form
    submit_btn = at.get("button")[0]
    submit_btn.click().run()
    assert len(at.exception) == 0
    # Must report error message
    assert len(at.error) > 0
    assert any(
        "empty" in e.value.lower() or "skill" in e.value.lower() for e in at.error
    )

    # 3. Valid job submission
    title_input = at.get("text_input")[0]
    title_input.input("Data Engineer")

    req_skills_area = at.get("text_area")[0]
    req_skills_area.input("Python, SQL, Spark")

    submit_btn = at.get("button")[0]
    submit_btn.click().run()
    assert len(at.exception) == 0
    assert at.session_state["job"] is not None
    assert at.session_state["job"].job_title == "Data Engineer"

    # 4. Navigation to Results with mock report
    dummy_report = AnalysisReport(
        report_id="20261108T100000Z_01234567_abcd",
        created_at=datetime.now(UTC),
        app_version="0.1.0",
        config_snapshot={
            "strategy": "weighted",
            "fuzzy_threshold": 85.0,
            "ai": {"provider": "null"},
        },
        candidate=Candidate(
            candidate_id="0123456789ab",
            name="Smoke Test Candidate",
            email="smoke@test.local",
            skills=[Skill(name="Python", mentions=1)],
            experience=[
                ExperienceEntry(
                    job_title="Software Developer",
                    duration_months=36,
                )
            ],
            education=[
                EducationEntry(
                    degree="BS Computer Science",
                    level=EducationLevel.BACHELOR,
                )
            ],
            total_experience_years=3.0,
            highest_education_level=EducationLevel.BACHELOR,
            source_format="txt",
            parser_version="1.0.0",
        ),
        job=at.session_state["job"],
        match=MatchResult(
            skill_matches=[
                SkillMatch(
                    target="Python",
                    matched_candidate_skill="Python",
                    match_type=MatchType.EXACT,
                    similarity=100.0,
                    credit=1.0,
                    is_required=True,
                ),
                SkillMatch(
                    target="Spark",
                    matched_candidate_skill=None,
                    match_type=MatchType.NONE,
                    similarity=0.0,
                    credit=0.0,
                    is_required=True,
                ),
            ],
            required_credit=0.5,
            optional_credit=None,
            experience=ExperienceAnalysis(
                required_years=2.0,
                candidate_years=3.0,
                status="met",
                subscore=1.0,
            ),
            education=EducationAnalysis(
                required_level=EducationLevel.BACHELOR,
                candidate_level=EducationLevel.BACHELOR,
                status="met",
                subscore=1.0,
            ),
        ),
        score=ScoreResult(
            strategy_name="weighted",
            total_score=78.5,
            coverage=1.0,
            fit_band=FitBand.MODERATE,
            components=[
                ScoreComponent(
                    name="required_skills",
                    status=ComponentStatus.EVALUATED,
                    weight=0.50,
                    subscore=0.5,
                    points=25.0,
                    explanation="Half required skills matched",
                ),
                ScoreComponent(
                    name="experience",
                    status=ComponentStatus.EVALUATED,
                    weight=0.20,
                    subscore=1.0,
                    points=20.0,
                    explanation="Experience requirements met",
                ),
            ],
            flags=[],
        ),
        ai=AIInsights(),
        flags=[],
    )

    at.session_state["reports"] = [dummy_report]
    at.session_state["current_page"] = "3 Results"
    at.session_state["nav_radio"] = "3 Results"
    at.run()
    assert len(at.exception) == 0
    assert "Step 3: Screening Results & Ranking" in at.title[0].value

    # Verify score metrics are rendered
    metrics = [m.value for m in at.metric]
    assert any("78.5" in m for m in metrics)

    # 5. Navigation to Reports page shows export controls
    at.session_state["current_page"] = "4 Reports"
    at.session_state["nav_radio"] = "4 Reports"
    at.run()

    assert len(at.exception) == 0
    assert "Step 4: Export Reports" in at.title[0].value

    # Download buttons for HTML, PDF, Excel must be present
    download_buttons = at.get("download_button")
    assert len(download_buttons) >= 3
    labels = [btn.label for btn in download_buttons]
    assert any("HTML" in lbl for lbl in labels)
    assert any("PDF" in lbl for lbl in labels)
    assert any("Excel" in lbl for lbl in labels)

    # 6. Navigation to History page shows persistence controls and feedback summary (FR-28, FR-29)
    at.session_state["current_page"] = "5 History"
    at.session_state["nav_radio"] = "5 History"
    at.run()

    assert len(at.exception) == 0
    assert "Step 5: History & Persistence" in at.title[0].value


def test_it_07_workflow_navigation_and_state_preservation() -> None:
    """Verify end-to-end multi-step navigation, validation guards, and state preservation."""
    app_path = (
        Path(__file__).parent.parent.parent / "src/resume_analyzer/ui/streamlit_app.py"
    ).resolve()
    at = AppTest.from_file(str(app_path), default_timeout=15)
    at.run()
    assert len(at.exception) == 0
    assert "Step 1: Define Job Requirements" in at.title[0].value

    # 1. Empty submission displays validation errors and stays on Step 1
    submit_btn = at.get("button")[0]
    submit_btn.click().run()
    assert len(at.exception) == 0
    assert len(at.error) > 0
    assert at.session_state["current_page"] == "1 Job"

    # 2. Valid submission advances to Step 2
    title_in = at.get("text_input")[0]
    title_in.input("Staff Python Architect")
    skills_in = at.get("text_area")[0]
    skills_in.input("Python, FastAPI, Docker, PostgreSQL")
    num_in = at.get("number_input")[0]
    num_in.set_value(5.5)

    submit_btn = at.get("button")[0]
    submit_btn.click().run()
    if "Step 2: Upload Resumes" not in at.title[0].value:
        at.run()

    assert len(at.exception) == 0
    assert at.session_state["current_page"] == "2 Resumes"
    assert "Step 2: Upload Resumes" in at.title[0].value
    assert at.session_state["job"] is not None
    assert at.session_state["job"].title == "Staff Python Architect"
    assert at.session_state["job"].min_experience_years == 5.5

    # 3. Back navigation to Step 1 preserves all entered fields
    back_btns = [b for b in at.button if "Back to Step 1" in b.label or "Edit Job" in b.label]
    assert len(back_btns) > 0
    back_btns[0].click().run()
    if "Step 1: Define Job Requirements" not in at.title[0].value:
        at.run()

    assert len(at.exception) == 0
    assert at.session_state["current_page"] == "1 Job"
    assert "Step 1: Define Job Requirements" in at.title[0].value
    assert at.get("text_input")[0].value == "Staff Python Architect"
    assert "FastAPI" in at.get("text_area")[0].value
    assert at.get("number_input")[0].value == 5.5

    # 4. Advance back to Step 2 via top proceed button
    proceed_btns = [b for b in at.button if "Proceed to Upload Resumes" in b.label]
    assert len(proceed_btns) > 0
    proceed_btns[0].click().run()
    if "Step 2: Upload Resumes" not in at.title[0].value:
        at.run()

    assert len(at.exception) == 0
    assert at.session_state["current_page"] == "2 Resumes"
    assert "Step 2: Upload Resumes" in at.title[0].value

    # 5. Sidebar radio navigation
    at.sidebar.radio[0].set_value("1 Job").run()
    assert at.session_state["current_page"] == "1 Job"
    at.sidebar.radio[0].set_value("2 Resumes").run()
    assert at.session_state["current_page"] == "2 Resumes"
