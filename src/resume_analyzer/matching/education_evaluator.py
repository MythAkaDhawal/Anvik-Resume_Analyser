"""Education evaluation and academic qualification scoring (FR-11, §7.4)."""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

from resume_analyzer.models.candidate import Candidate
from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import EducationAnalysis


def _check_preferred_fields(
    education_entries: list[Any],
    preferred_fields: list[str],
) -> bool | None:
    """Check if candidate's field of study matches any job preferred fields."""
    candidate_fields = [
        e.field_of_study.strip()
        for e in education_entries
        if e.field_of_study and e.field_of_study.strip()
    ]
    if not candidate_fields:
        return None

    for pref in preferred_fields:
        pref_clean = pref.strip().lower()
        if not pref_clean:
            continue
        for c_field in candidate_fields:
            if fuzz.token_set_ratio(pref_clean, c_field.lower()) >= 85:
                return True
    return False


def evaluate_education(
    candidate: Candidate,
    job: JobRequirements,
) -> EducationAnalysis:
    """Evaluate candidate education level against job requirements.

    Rules from TECHNICAL_SPECIFICATION §7.4:
    - req == UNSPECIFIED -> status='not_required', subscore=None, field_match=None
    - cand == UNSPECIFIED -> status='unknown', subscore=None, field_match=None
    - cand >= req -> status='met', base_subscore=1.0
    - cand == req - 1 -> status='below', base_subscore=0.5
    - cand < req - 1 -> status='below', base_subscore=0.0

    Field-of-study adjustment:
    If job.preferred_fields is non-empty, status == 'met', and candidate has
    at least one education entry with a field:
    - field_match = True if any preferred field token_set_ratio >= 85
    - if field_match is False, subscore is capped at 0.75
    - if candidate has no field text, field_match=None and no cap applies

    Args:
        candidate: Candidate profile containing education entries and highest level.
        job: Job requirements specifying min_education_level and preferred_fields.

    Returns:
        EducationAnalysis instance.
    """
    req_level = job.min_education_level
    cand_level = candidate.highest_education_level

    # 1. Unspecified requirement
    if req_level == EducationLevel.UNSPECIFIED:
        return EducationAnalysis(
            required_level=req_level,
            candidate_level=cand_level,
            status="not_required",
            subscore=None,
            field_match=None,
        )

    # 2. Unknown candidate education
    if cand_level == EducationLevel.UNSPECIFIED:
        return EducationAnalysis(
            required_level=req_level,
            candidate_level=cand_level,
            status="unknown",
            subscore=None,
            field_match=None,
        )

    # 3. Attainment level comparison
    cand_int = int(cand_level)
    req_int = int(req_level)

    if cand_int >= req_int:
        status_label = "met"
        base_subscore = 1.0
    elif cand_int == req_int - 1:
        status_label = "below"
        base_subscore = 0.5
    else:
        status_label = "below"
        base_subscore = 0.0

    final_subscore = base_subscore
    field_match: bool | None = None

    # 4. Field of study adjustment (applies only when status == 'met')
    if status_label == "met" and job.preferred_fields:
        field_match = _check_preferred_fields(candidate.education, job.preferred_fields)
        if field_match is False:
            final_subscore = min(final_subscore, 0.75)

    return EducationAnalysis(
        required_level=req_level,
        candidate_level=cand_level,
        status=status_label,
        subscore=final_subscore,
        field_match=field_match,
    )
