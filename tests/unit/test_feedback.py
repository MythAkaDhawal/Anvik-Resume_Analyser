"""Unit tests for user feedback persistence, validation, PII masking, and analytics (Phase 12, FR-29).

Tests UT-FB-01 through UT-FB-03 per TESTING_STRATEGY §5.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from resume_analyzer.exceptions import InvalidIdentifierError
from resume_analyzer.storage.feedback_store import FeedbackRecord, FeedbackStore

VALID_REPORT_ID = "20261108T120000Z_01234567_89ab"


# -----------------------------------------------------------------------------
# UT-FB-01: Feedback append writes valid JSON line to storage
# -----------------------------------------------------------------------------
def test_ut_fb_01_feedback_append_jsonl(tmp_path: Path) -> None:
    """Assert FeedbackStore.append() writes a single valid JSON line (FR-29)."""
    feedback_file = tmp_path / "feedback.jsonl"
    store = FeedbackStore(feedback_path=feedback_file)

    record = FeedbackRecord(
        report_id=VALID_REPORT_ID,
        rating=4,
        comment="Strong match on Python skills, but experience section was slightly misread.",
        section_feedback={"skills": True, "experience": False},
        corrected_skills=["FastAPI"],
    )

    store.append(record)

    assert feedback_file.is_file()
    lines = feedback_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    parsed = json.loads(lines[0])
    assert parsed["report_id"] == VALID_REPORT_ID
    assert parsed["rating"] == 4
    assert parsed["section_feedback"] == {"skills": True, "experience": False}
    assert parsed["corrected_skills"] == ["FastAPI"]

    # Append second record
    record2 = FeedbackRecord(
        report_id=VALID_REPORT_ID,
        rating=5,
        comment="Excellent evaluation overall.",
        section_feedback={"skills": True, "experience": True},
    )
    store.append(record2)

    lines = feedback_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


# -----------------------------------------------------------------------------
# UT-FB-02: Validation rules and PII masking on user comments
# -----------------------------------------------------------------------------
def test_ut_fb_02_validation_and_pii_masking() -> None:
    """Assert rating bounds, comment length, valid report_id, and automatic email masking (UT-FB-02)."""
    # 1. Rating bounds (1 to 5)
    with pytest.raises(ValidationError):
        FeedbackRecord(report_id=VALID_REPORT_ID, rating=0)

    with pytest.raises(ValidationError):
        FeedbackRecord(report_id=VALID_REPORT_ID, rating=6)

    # 2. Comment max length (1000 characters)
    oversized_comment = "A" * 1001
    with pytest.raises(ValidationError):
        FeedbackRecord(report_id=VALID_REPORT_ID, rating=3, comment=oversized_comment)

    # 3. Invalid report_id format
    with pytest.raises(InvalidIdentifierError):
        FeedbackRecord(report_id="bad_report_id", rating=4)

    with pytest.raises(InvalidIdentifierError):
        FeedbackRecord(report_id="../traversal_id", rating=4)

    # 4. Email and contact details in comment MUST be masked to [EMAIL] / [PHONE]
    comment_with_pii = (
        "Candidate contact was recruiter.john@techcorp.com and call +1-555-123-4567. "
        "Also see https://linkedin.com/in/john-doe for verification."
    )
    rec = FeedbackRecord(report_id=VALID_REPORT_ID, rating=4, comment=comment_with_pii)
    assert "[EMAIL]" in rec.comment
    assert "recruiter.john@techcorp.com" not in rec.comment
    assert "[PHONE]" in rec.comment
    assert "+1-555-123-4567" not in rec.comment
    assert "[URL]" in rec.comment


# -----------------------------------------------------------------------------
# UT-FB-03: Summary aggregation metrics
# -----------------------------------------------------------------------------
def test_ut_fb_03_summary_aggregation(tmp_path: Path) -> None:
    """Assert summarize() computes average rating, section approval ratios, and top corrected skills (UT-FB-03)."""
    feedback_file = tmp_path / "feedback.jsonl"
    store = FeedbackStore(feedback_path=feedback_file)

    # Empty store returns default zero metrics
    empty_summary = store.summarize()
    assert empty_summary.total_submissions == 0
    assert empty_summary.average_rating == 0.0
    assert empty_summary.section_positive_ratios == {}
    assert empty_summary.top_corrected_skills == []

    # Insert submissions
    r1 = FeedbackRecord(
        report_id=VALID_REPORT_ID,
        rating=5,
        section_feedback={"skills": True, "experience": True, "education": True},
        corrected_skills=["FastAPI", "Docker"],
    )
    r2 = FeedbackRecord(
        report_id=VALID_REPORT_ID,
        rating=3,
        section_feedback={"skills": False, "experience": True, "education": True},
        corrected_skills=["Docker", "Kubernetes"],
    )
    r3 = FeedbackRecord(
        report_id=VALID_REPORT_ID,
        rating=4,
        section_feedback={"skills": True, "experience": False, "education": True},
        corrected_skills=["Docker"],
    )

    store.append(r1)
    store.append(r2)
    store.append(r3)

    summary = store.summarize()
    assert summary.total_submissions == 3
    # Average rating: (5 + 3 + 4) / 3 = 4.0
    assert summary.average_rating == 4.0

    # Section ratios:
    # skills: 2 True, 1 False -> 2/3 = ~0.667
    assert pytest.approx(summary.section_positive_ratios["skills"], rel=1e-2) == 0.67
    # experience: 2 True, 1 False -> 2/3 = ~0.667
    assert (
        pytest.approx(summary.section_positive_ratios["experience"], rel=1e-2) == 0.67
    )
    # education: 3 True, 0 False -> 3/3 = 1.0
    assert summary.section_positive_ratios["education"] == 1.0

    # Top corrected skills: Docker (3), FastAPI (1), Kubernetes (1)
    assert len(summary.top_corrected_skills) == 3
    assert summary.top_corrected_skills[0] == ("Docker", 3)
    skills_map = dict(summary.top_corrected_skills)
    assert skills_map["Docker"] == 3
    assert skills_map["FastAPI"] == 1
    assert skills_map["Kubernetes"] == 1
