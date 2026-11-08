"""Deterministic candidate-job skill matching algorithm (FR-09, §7.2).

Performs exact, alias, and guarded fuzzy skill matching. Produces exactly one
SkillMatch per job skill (both required and optional), preserving order.
"""

from __future__ import annotations

import logging
from typing import Sequence

from resume_analyzer.config.settings import FuzzySettings
from resume_analyzer.models.candidate import Candidate, Skill
from resume_analyzer.models.enums import MatchType
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import SkillMatch
from resume_analyzer.skills.normalizer import fuzzy_similarity, normalize_skill
from resume_analyzer.skills.skill_index import SkillIndex

logger = logging.getLogger(__name__)


def match_skills(
    candidate: Candidate,
    job: JobRequirements,
    index: SkillIndex,
    fuzzy_settings: FuzzySettings | None = None,
) -> list[SkillMatch]:
    """Match candidate skills against all job requirements (required and optional).

    Evaluation follows strict priority:
    1. EXACT: Normalized strings match exactly (100% similarity, 1.0 credit).
    2. ALIAS: Target canonical equals candidate canonical via taxonomy (100% similarity, 1.0 credit).
    3. FUZZY: When at least one side is outside taxonomy, meets length and first-character
       guards, exceeds threshold, and is not a declared confusable pair.
    4. NONE: No match achieved (0.0 similarity, 0.0 credit).

    Args:
        candidate: Extracted Candidate profile.
        job: Validated JobRequirements.
        index: Active SkillIndex.
        fuzzy_settings: Optional fuzzy matching configuration.

    Returns:
        List containing exactly one SkillMatch for each required skill followed
        by each optional skill.
    """
    settings = fuzzy_settings or FuzzySettings()

    # Pre-index candidate skills for efficient O(1) lookups
    # cand_by_norm: normalized raw name -> Skill
    cand_by_norm: dict[str, Skill] = {}
    # cand_by_canonical: canonical_name -> Skill
    cand_by_canonical: dict[str, Skill] = {}
    # candidate_entries: list of (Skill, normalized_name)
    candidate_entries: list[tuple[Skill, str]] = []

    for skill in candidate.skills:
        c_norm = normalize_skill(skill.name)
        if c_norm and c_norm not in cand_by_norm:
            cand_by_norm[c_norm] = skill

        # Register by canonical taxonomy identifier
        if skill.canonical_name:
            cand_by_canonical[skill.canonical_name] = skill

        candidate_entries.append((skill, c_norm))

    matches: list[SkillMatch] = []

    # Sequence of (skill_name, is_required) preserving job order
    target_skills: list[tuple[str, bool]] = [
        (s, True) for s in job.required_skills
    ] + [(s, False) for s in job.optional_skills]

    for target_skill, is_required in target_skills:
        t_norm = normalize_skill(target_skill)
        t_canonical = index.canonical(t_norm)

        # 1. EXACT match check
        if t_norm in cand_by_norm:
            matched_cand = cand_by_norm[t_norm]
            matches.append(
                SkillMatch(
                    target=target_skill,
                    target_canonical=t_canonical,
                    is_required=is_required,
                    matched_candidate_skill=matched_cand.name,
                    match_type=MatchType.EXACT,
                    similarity=100.0,
                    credit=1.0,
                )
            )
            continue

        # 2. ALIAS match check
        if t_canonical is not None and t_canonical in cand_by_canonical:
            matched_cand = cand_by_canonical[t_canonical]
            matches.append(
                SkillMatch(
                    target=target_skill,
                    target_canonical=t_canonical,
                    is_required=is_required,
                    matched_candidate_skill=matched_cand.name,
                    match_type=MatchType.ALIAS,
                    similarity=100.0,
                    credit=1.0,
                )
            )
            continue

        # 3. FUZZY match check (if enabled)
        fuzzy_match_found = False
        if settings.enabled and t_norm:
            best_cand_skill: Skill | None = None
            best_similarity: float = 0.0

            for cand_skill, c_norm in candidate_entries:
                if not c_norm:
                    continue

                # Rule §7.2: If both sides are known taxonomy skills, they are different skills by definition
                if t_canonical is not None and cand_skill.canonical_name is not None:
                    continue

                # Guard 1: Minimum token length
                if min(len(t_norm), len(c_norm)) < settings.min_length:
                    continue

                # Guard 2: First characters must match
                if t_norm[0] != c_norm[0]:
                    continue

                # Guard 3: Confusable pairs check (e.g. Java vs JavaScript)
                if index.is_confusable(t_norm, c_norm):
                    continue

                similarity = fuzzy_similarity(t_norm, c_norm)
                if similarity >= settings.threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_cand_skill = cand_skill

            if best_cand_skill is not None:
                credit = round(best_similarity / 100.0, 4)
                matches.append(
                    SkillMatch(
                        target=target_skill,
                        target_canonical=t_canonical,
                        is_required=is_required,
                        matched_candidate_skill=best_cand_skill.name,
                        match_type=MatchType.FUZZY,
                        similarity=round(best_similarity, 2),
                        credit=credit,
                    )
                )
                fuzzy_match_found = True

        if fuzzy_match_found:
            continue

        # 4. NONE (Unmatched)
        matches.append(
            SkillMatch(
                target=target_skill,
                target_canonical=t_canonical,
                is_required=is_required,
                matched_candidate_skill=None,
                match_type=MatchType.NONE,
                similarity=0.0,
                credit=0.0,
            )
        )

    return matches
