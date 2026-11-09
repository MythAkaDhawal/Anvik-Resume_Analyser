"""Experience evaluation logic against job requirements (FR-10, §7.3)."""

from __future__ import annotations

from resume_analyzer.models.results import ExperienceAnalysis


def evaluate_experience(
    candidate_years: float | None,
    required_years: float,
) -> ExperienceAnalysis:
    """Evaluate candidate professional experience against target minimum years.

    Rules from TECHNICAL_SPECIFICATION §7.3:
    - required_years == 0 -> status='not_required', subscore=None, gap_years=0.0
    - candidate_years is None -> status='unknown', subscore=None, gap_years=None
    - candidate_years >= required_years -> status='met', subscore=1.0, gap_years=0.0
    - otherwise -> status='partial' (if candidate_years > 0) else 'unmet',
      subscore=candidate_years / required_years, gap_years=required_years - candidate_years

    Args:
        candidate_years: Total non-overlapping experience years, or None if unknown.
        required_years: Minimum years required by job (>= 0).

    Returns:
        ExperienceAnalysis instance.
    """
    req = float(max(0.0, required_years))

    if req == 0.0:
        return ExperienceAnalysis(
            required_years=0.0,
            candidate_years=candidate_years,
            status="not_required",
            subscore=None,
            gap_years=0.0,
        )

    if candidate_years is None:
        return ExperienceAnalysis(
            required_years=req,
            candidate_years=None,
            status="unknown",
            subscore=None,
            gap_years=None,
        )

    cand = float(candidate_years)

    if cand >= req:
        return ExperienceAnalysis(
            required_years=req,
            candidate_years=cand,
            status="met",
            subscore=1.0,
            gap_years=0.0,
        )

    # Deficient experience
    gap = round(max(0.0, req - cand), 1)
    subscore = round(max(0.0, cand / req), 4)
    status_label = "partial" if cand > 0.0 else "unmet"

    return ExperienceAnalysis(
        required_years=req,
        candidate_years=cand,
        status=status_label,
        subscore=subscore,
        gap_years=gap,
    )
