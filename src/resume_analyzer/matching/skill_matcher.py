"""Deterministic candidate-job skill matching algorithm (FR-09, §7.2).

Performs exact, alias, and guarded fuzzy skill matching. Produces exactly one
SkillMatch per job skill (both required and optional), preserving order.
"""

from __future__ import annotations

import logging

from resume_analyzer.config.settings import FuzzySettings
from resume_analyzer.models.candidate import Candidate, Skill
from resume_analyzer.models.enums import MatchType
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import SkillMatch
from resume_analyzer.skills.normalizer import fuzzy_similarity, normalize_skill
from resume_analyzer.skills.skill_index import SkillIndex

logger = logging.getLogger(__name__)


def _find_best_fuzzy_match(
    t_norm: str,
    t_canonical: str | None,
    candidate_entries: list[tuple[Skill, str]],
    index: SkillIndex,
    settings: FuzzySettings,
) -> tuple[Skill | None, float]:
    """Find candidate skill with highest fuzzy similarity satisfying taxonomy and lexical guards."""
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
        # Guard 3: Confusable pairs check
        if index.is_confusable(t_norm, c_norm):
            continue

        sim = fuzzy_similarity(t_norm, c_norm)
        if sim >= settings.threshold and sim > best_similarity:
            best_similarity = sim
            best_cand_skill = cand_skill

    return best_cand_skill, best_similarity


def _match_single_target(
    target_skill: str,
    is_required: bool,
    cand_by_norm: dict[str, Skill],
    cand_by_canonical: dict[str, Skill],
    candidate_entries: list[tuple[Skill, str]],
    index: SkillIndex,
    settings: FuzzySettings,
) -> SkillMatch:
    """Evaluate single target skill against candidate skills."""
    t_norm = normalize_skill(target_skill)
    t_canonical = index.canonical(t_norm)

    # 1. EXACT match
    if t_norm in cand_by_norm:
        matched = cand_by_norm[t_norm]
        return SkillMatch(
            target=target_skill,
            target_canonical=t_canonical,
            is_required=is_required,
            matched_candidate_skill=matched.name,
            match_type=MatchType.EXACT,
            similarity=100.0,
            credit=1.0,
        )

    # 2. ALIAS match
    if t_canonical is not None and t_canonical in cand_by_canonical:
        matched = cand_by_canonical[t_canonical]
        return SkillMatch(
            target=target_skill,
            target_canonical=t_canonical,
            is_required=is_required,
            matched_candidate_skill=matched.name,
            match_type=MatchType.ALIAS,
            similarity=100.0,
            credit=1.0,
        )

    # 3. FUZZY match
    if settings.enabled and t_norm:
        cand_skill, sim = _find_best_fuzzy_match(
            t_norm, t_canonical, candidate_entries, index, settings
        )
        if cand_skill is not None:
            return SkillMatch(
                target=target_skill,
                target_canonical=t_canonical,
                is_required=is_required,
                matched_candidate_skill=cand_skill.name,
                match_type=MatchType.FUZZY,
                similarity=round(sim, 2),
                credit=round(sim / 100.0, 4),
            )

    # 4. NONE
    return SkillMatch(
        target=target_skill,
        target_canonical=t_canonical,
        is_required=is_required,
        matched_candidate_skill=None,
        match_type=MatchType.NONE,
        similarity=0.0,
        credit=0.0,
    )


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

    cand_by_norm: dict[str, Skill] = {}
    cand_by_canonical: dict[str, Skill] = {}
    candidate_entries: list[tuple[Skill, str]] = []

    for skill in candidate.skills:
        c_norm = normalize_skill(skill.name)
        if c_norm and c_norm not in cand_by_norm:
            cand_by_norm[c_norm] = skill
        if skill.canonical_name:
            cand_by_canonical[skill.canonical_name] = skill
        candidate_entries.append((skill, c_norm))

    target_skills: list[tuple[str, bool]] = [(s, True) for s in job.required_skills] + [
        (s, False) for s in job.optional_skills
    ]

    return [
        _match_single_target(
            target_skill,
            is_required,
            cand_by_norm,
            cand_by_canonical,
            candidate_entries,
            index,
            settings,
        )
        for target_skill, is_required in target_skills
    ]
