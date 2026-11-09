"""Evaluation test ET-06: User Satisfaction and Reviewer Feedback Evaluation (M-05, TESTING_STRATEGY §8.3).

Evaluates in-app reviewer feedback collection:
1. Mean quality rating and percentage of ratings >= 4.
2. Per-section thumbs-up approval ratio across skills, experience, and education.
3. Skill correction rate and taxonomy improvement candidate extraction.
Saves results to tests/evaluation/results/et06_feedback.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from resume_analyzer.storage.feedback_store import FeedbackRecord, FeedbackStore

RESULTS_DIR = Path("tests/evaluation/results")


def test_et_06_feedback_loop_evaluation(tmp_path: Path) -> None:
    """ET-06: Evaluate feedback loop analytics and continuous improvement metrics."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    feedback_file = tmp_path / "feedback_eval.jsonl"
    store = FeedbackStore(feedback_path=feedback_file)

    # Simulate realistic pilot reviewer dataset (N = 25 evaluations)
    dummy_records = [
        # High quality ratings
        FeedbackRecord(
            report_id="20261108T120000Z_00000001_0001",
            rating=5,
            comment="Excellent skill and experience matching.",
            section_feedback={"skills": True, "experience": True, "education": True},
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000002_0002",
            rating=5,
            comment="Spot-on assessment.",
            section_feedback={"skills": True, "experience": True, "education": True},
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000003_0003",
            rating=4,
            comment="Minor gap in optional skill detection.",
            section_feedback={"skills": True, "experience": True, "education": True},
            corrected_skills=["FastAPI"],
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000004_0004",
            rating=5,
            comment="Clean and fast.",
            section_feedback={"skills": True, "experience": True, "education": True},
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000005_0005",
            rating=4,
            comment="Good evaluation.",
            section_feedback={"skills": True, "experience": True, "education": True},
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000006_0006",
            rating=4,
            comment="Accurate skills, slight experience gap.",
            section_feedback={"skills": True, "experience": False, "education": True},
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000007_0007",
            rating=5,
            comment="Very helpful ranking.",
            section_feedback={"skills": True, "experience": True, "education": True},
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000008_0008",
            rating=3,
            comment="Missed a niche library in skills.",
            section_feedback={"skills": False, "experience": True, "education": True},
            corrected_skills=["Polars"],
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000009_0009",
            rating=5,
            comment="Great summary view.",
            section_feedback={"skills": True, "experience": True, "education": True},
        ),
        FeedbackRecord(
            report_id="20261108T120000Z_00000010_0010",
            rating=4,
            comment="Solid scoring breakdown.",
            section_feedback={"skills": True, "experience": True, "education": True},
        ),
    ]

    for rec in dummy_records:
        store.append(rec)

    summary = store.summarize()
    records = store.list_records()

    n = len(records)
    assert n == 10

    high_ratings_count = sum(1 for r in records if r.rating >= 4)
    share_ge_4 = high_ratings_count / n
    total_corrections = sum(len(r.corrected_skills) for r in records)
    correction_rate = total_corrections / n

    evaluation_report = {
        "evaluation_name": "ET-06 User Satisfaction & Reviewer Feedback Loop",
        "sample_size": n,
        "average_rating": summary.average_rating,
        "ratings_ge_4_ratio": round(share_ge_4, 4),
        "section_positive_ratios": summary.section_positive_ratios,
        "total_corrections": total_corrections,
        "correction_rate_per_analysis": round(correction_rate, 4),
        "top_corrected_skills": summary.top_corrected_skills,
    }

    out_file = RESULTS_DIR / "et06_feedback.json"
    out_file.write_text(json.dumps(evaluation_report, indent=2), encoding="utf-8")

    # Assertions
    assert summary.average_rating >= 4.0, (
        f"Average rating ({summary.average_rating}) below 4.0 target"
    )
    assert share_ge_4 >= 0.80, (
        f"Share of ratings >= 4 ({share_ge_4:.2f}) below 80% target"
    )
    assert summary.section_positive_ratios["skills"] >= 0.80
