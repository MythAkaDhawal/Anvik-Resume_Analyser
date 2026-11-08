"""Skills taxonomy, normalization, and indexing package."""

from __future__ import annotations

from resume_analyzer.skills.normalizer import (
    clear_normalizer_caches,
    fuzzy_similarity,
    normalize_skill,
)
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import (
    SkillTaxonomy,
    SkillTaxonomyEntry,
    clear_taxonomy_cache,
)

__all__ = [
    "SkillIndex",
    "SkillTaxonomy",
    "SkillTaxonomyEntry",
    "clear_normalizer_caches",
    "clear_taxonomy_cache",
    "fuzzy_similarity",
    "normalize_skill",
]
