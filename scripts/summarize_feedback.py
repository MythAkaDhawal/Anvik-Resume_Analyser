#!/usr/bin/env python
"""Summarize user feedback stored in data/feedback.jsonl (Phase 12).

Thin CLI wrapper invoking FeedbackStore.summarize().
"""

from __future__ import annotations

import sys

from resume_analyzer.storage.feedback_store import FeedbackStore


def main() -> int:
    """Print aggregated feedback metrics to standard output."""
    store = FeedbackStore()
    summary = store.summarize()

    print("\n================ USER FEEDBACK SUMMARY ================")
    print(f"Total Submissions:       {summary.total_submissions}")
    print(f"Average Star Rating:     {summary.average_rating:.2f} / 5.00")

    if summary.section_positive_ratios:
        print("\nSection Positive Approval Ratios:")
        for sec, ratio in summary.section_positive_ratios.items():
            print(f"  • {sec:<20} {ratio * 100:>5.1f}% positive")

    if summary.top_corrected_skills:
        print("\nTop Corrected Skills:")
        for skill, count in summary.top_corrected_skills:
            print(f"  • {skill:<20} ({count} corrections)")

    print("=======================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

