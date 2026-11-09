"""Post-inference output grounding, fact validation, and safety filters (AI_PROMPTS §3-§7)."""

from __future__ import annotations

import re

from resume_analyzer.ai.schemas import (
    ExtractionResult,
    ImprovementRecommendations,
    InterviewQuestionsResult,
    MatchExplanation,
    SkillCategorizationResult,
)

# Prohibited hiring verdicts regex
VERDICT_REGEX = re.compile(
    r"(?i)\b(?:hire|hiring|reject|rejected|shortlist|do not hire|do not interview|not suitable|unsuitable|recommend(?:ed)? (?:for|to|hiring))\b"
)

# Protected characteristics regex
PROTECTED_TERMS_REGEX = re.compile(
    r"(?i)\b(?:age|gender|sex|male|female|race|ethnicity|religion|marital|married|pregnant|pregnancy|disability|health|children|political)\b"
)

# Disallowed URL regex
URL_REGEX = re.compile(r"(?i)(?:https?://|www\.|\.com|\.org|\.io|\.net|@)")


def ground_p1_extraction(
    result: ExtractionResult, raw_text: str
) -> tuple[ExtractionResult, int]:
    """Verify extracted skills and companies appear in the raw resume text."""
    dropped = 0
    raw_lower = raw_text.lower()

    # 1. Ground skills
    grounded_skills = []
    for s in result.skills:
        if s.name and s.name.lower() in raw_lower:
            grounded_skills.append(s)
        else:
            dropped += 1

    # 2. Ground experience companies
    for exp in result.experience:
        if exp.company and exp.company.lower() not in raw_lower:
            exp.company = None
            dropped += 1

        # Date validation: null out impossible formats
        if exp.start_date and not re.match(r"^\d{4}(?:-\d{2})?$", exp.start_date):
            exp.start_date = None
            dropped += 1
        if exp.end_date and not re.match(r"^\d{4}(?:-\d{2})?$", exp.end_date):
            exp.end_date = None
            dropped += 1

    result.skills = grounded_skills
    return result, dropped


def ground_p2_categorization(
    result: SkillCategorizationResult,
    input_skills: list[str],
    allowed_categories: list[str],
    min_confidence: float = 0.5,
) -> tuple[SkillCategorizationResult, int]:
    """Validate skill categories against allowed list and input skill set."""
    dropped = 0
    input_set = {s.lower(): s for s in input_skills}
    allowed_set = {c.lower(): c for c in allowed_categories}

    valid_items = []
    seen_skills = set()

    for item in result.categories:
        k = item.skill.lower()
        if k not in input_set:
            # Extra unknown skill produced by LLM
            dropped += 1
            continue

        if k in seen_skills:
            dropped += 1
            continue
        seen_skills.add(k)

        # Category validation
        cat_lower = item.category.lower()
        if cat_lower not in allowed_set:
            item.category = "Other"
            dropped += 1
        elif item.confidence < min_confidence:
            item.category = "Other"
        else:
            item.category = allowed_set[cat_lower]

        valid_items.append(item)

    # Fill in any missing input skills with 'Other'
    for k, original_skill in input_set.items():
        if k not in seen_skills:
            from resume_analyzer.ai.schemas import SkillCategoryItem

            valid_items.append(
                SkillCategoryItem(
                    skill=original_skill,
                    category="Other",
                    confidence=0.0,
                )
            )
            dropped += 1

    result.categories = valid_items
    return result, dropped


def ground_p3_explanation(
    result: MatchExplanation,
    valid_fact_ids: set[str],
    allowed_numbers: set[str],
) -> tuple[MatchExplanation, int]:
    """Filter explanation items violating citation, number, or verdict rules."""
    dropped = 0

    # 1. Summary checks
    if VERDICT_REGEX.search(result.summary) or PROTECTED_TERMS_REGEX.search(
        result.summary
    ):
        result.summary = "Match summary withheld due to safety policy violation."
        dropped += 1

    # 2. Strengths checks
    valid_strengths = []
    for s in result.strengths:
        if VERDICT_REGEX.search(s.point) or PROTECTED_TERMS_REGEX.search(s.point):
            dropped += 1
            continue
        # Citation check
        if not s.evidence or not all(e in valid_fact_ids for e in s.evidence):
            dropped += 1
            continue
        # Number check
        nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", s.point))
        if not nums.issubset(allowed_numbers):
            dropped += 1
            continue
        valid_strengths.append(s)

    # 3. Concerns checks
    valid_concerns = []
    for c in result.concerns:
        if VERDICT_REGEX.search(c.point) or PROTECTED_TERMS_REGEX.search(c.point):
            dropped += 1
            continue
        if not c.evidence or not all(e in valid_fact_ids for e in c.evidence):
            dropped += 1
            continue
        nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", c.point))
        if not nums.issubset(allowed_numbers):
            dropped += 1
            continue
        valid_concerns.append(c)

    result.strengths = valid_strengths[:5]
    result.concerns = valid_concerns[:5]
    result.suggested_review_focus = result.suggested_review_focus[:5]
    result.limitations = result.limitations[:3]

    return result, dropped


def ground_p4_recommendations(
    result: ImprovementRecommendations,
    valid_gap_ids: set[str],
) -> tuple[ImprovementRecommendations, int]:
    """Validate recommendations citing valid gap IDs without URLs or verdicts."""
    dropped = 0
    valid_recs = []
    seen_gaps = set()

    for r in result.recommendations:
        if r.gap_id not in valid_gap_ids or r.gap_id in seen_gaps:
            dropped += 1
            continue
        seen_gaps.add(r.gap_id)

        # URL check
        if URL_REGEX.search(r.action) or URL_REGEX.search(r.rationale):
            dropped += 1
            continue

        # Verdict and protected-term check
        if VERDICT_REGEX.search(r.action) or VERDICT_REGEX.search(r.rationale):
            dropped += 1
            continue
        if PROTECTED_TERMS_REGEX.search(r.action) or PROTECTED_TERMS_REGEX.search(
            r.rationale
        ):
            dropped += 1
            continue

        valid_recs.append(r)

    result.recommendations = valid_recs[:6]
    return result, dropped


def ground_p5_interview_questions(
    result: InterviewQuestionsResult,
    allowed_skills: set[str],
    target_count: int = 8,
) -> tuple[InterviewQuestionsResult, int]:
    """Validate interview questions target job skills and omit protected topics."""
    dropped = 0
    valid_qs = []
    lower_allowed = {s.lower() for s in allowed_skills}

    for q in result.questions:
        # Protected-topic check
        if PROTECTED_TERMS_REGEX.search(q.question) or PROTECTED_TERMS_REGEX.search(
            q.rationale
        ):
            dropped += 1
            continue

        # URL check
        if URL_REGEX.search(q.question):
            dropped += 1
            continue

        # Target skill check
        if q.target_skill and q.target_skill.lower() not in lower_allowed:
            q.target_skill = None
            dropped += 1

        valid_qs.append(q)

    result.questions = valid_qs[:target_count]
    return result, dropped
