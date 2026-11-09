"""Skill taxonomy representation, loading, and schema validation (FR-05).

Loads skills, categories, aliases, and confusable pairs from JSON with strict
validation against duplicate canonicals and alias collisions.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from resume_analyzer.exceptions import ConfigurationError
from resume_analyzer.skills.normalizer import normalize_skill

logger = logging.getLogger(__name__)


class SkillTaxonomyEntry(BaseModel):
    """A single skill definition in the taxonomy.

    Attributes:
        canonical: Official display name (e.g. 'Python', 'AWS').
        category: Broad skill domain category.
        aliases: Common synonyms, acronyms, or versions.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    canonical: str = Field(min_length=1, max_length=60)
    category: str
    aliases: list[str] = Field(default_factory=list)


class SkillTaxonomy(BaseModel):
    """Complete loaded skill taxonomy model.

    Attributes:
        schema_version: Schema format version ('1.0').
        sources: Attribution statement for taxonomy data.
        categories: Ordered list of allowed skill categories.
        skills: List of validated skill entries.
        confusable_pairs: List of skill pairs that must never fuzzy-match.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: str = "1.0"
    sources: str | None = None
    categories: list[str]
    skills: list[SkillTaxonomyEntry]
    confusable_pairs: list[list[str]] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path | str) -> SkillTaxonomy:
        """Load and strictly validate a SkillTaxonomy from a JSON file.

        Args:
            path: Filesystem path to skills_taxonomy.json.

        Returns:
            Validated SkillTaxonomy instance.

        Raises:
            ConfigurationError: If file not found, unparseable, contains duplicate
                canonical names, or has alias collisions.
        """
        return _load_taxonomy_cached(str(Path(path).resolve()))


def _validate_skill_aliases(
    canonical: str,
    c_norm: str,
    aliases: Any,
    seen_aliases: dict[str, str],
) -> list[str]:
    """Validate and deduplicate aliases for a single canonical skill."""
    cleaned_aliases: list[str] = []
    if isinstance(aliases, list):
        for a in aliases:
            a_str = str(a).strip()
            if not a_str:
                continue
            a_norm = normalize_skill(a_str)
            if a_norm == c_norm:
                continue
            if a_norm in seen_aliases:
                prev_owner = seen_aliases[a_norm]
                raise ConfigurationError(
                    f"Alias collision: '{a_str}' for skill '{canonical}' "
                    f"collides with alias for '{prev_owner}'.",
                    key="skills.alias_collision",
                )
            seen_aliases[a_norm] = canonical
            cleaned_aliases.append(a_str)
    return cleaned_aliases


def _validate_taxonomy_item(
    idx: int,
    item: Any,
    allowed_categories: set[str],
    seen_canonicals: dict[str, str],
    seen_aliases: dict[str, str],
) -> SkillTaxonomyEntry:
    """Validate a single raw skill entry dictionary from taxonomy JSON."""
    if not isinstance(item, dict):
        raise ConfigurationError(
            f"Skill item at index {idx} must be an object.",
            key=f"skills[{idx}]",
        )

    canonical = item.get("canonical", "").strip()
    category = item.get("category", "").strip()
    aliases = item.get("aliases", [])

    if not canonical:
        raise ConfigurationError(
            f"Skill at index {idx} has an empty canonical name.",
            key=f"skills[{idx}].canonical",
        )

    if category not in allowed_categories:
        raise ConfigurationError(
            f"Skill '{canonical}' references undeclared category '{category}'.",
            key=f"skills[{idx}].category",
        )

    c_norm = normalize_skill(canonical)
    if c_norm in seen_canonicals:
        raise ConfigurationError(
            f"Duplicate canonical skill '{canonical}' collides with '{seen_canonicals[c_norm]}'.",
            key="skills.duplicate_canonical",
        )
    seen_canonicals[c_norm] = canonical

    cleaned_aliases = _validate_skill_aliases(canonical, c_norm, aliases, seen_aliases)
    return SkillTaxonomyEntry(
        canonical=canonical,
        category=category,
        aliases=cleaned_aliases,
    )


@lru_cache(maxsize=4)
def _load_taxonomy_cached(resolved_path_str: str) -> SkillTaxonomy:
    """Internal LRU-cached loader for skill taxonomies."""
    path = Path(resolved_path_str)
    if not path.exists():
        raise ConfigurationError(
            f"Skill taxonomy file not found: {path}",
            key="skills_taxonomy_path",
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
        raw_data = json.loads(raw_text)
    except Exception as err:
        raise ConfigurationError(
            f"Failed to read skill taxonomy JSON at {path}: {err}",
            key="skills_taxonomy_syntax",
        ) from err

    if not isinstance(raw_data, dict):
        raise ConfigurationError(
            f"Skill taxonomy root must be a JSON object, got {type(raw_data).__name__}",
            key="skills_taxonomy_root",
        )

    categories_list = raw_data.get("categories", [])
    if not isinstance(categories_list, list) or not categories_list:
        raise ConfigurationError(
            "Skill taxonomy must declare a non-empty 'categories' list.",
            key="categories",
        )
    allowed_categories = set(categories_list)

    skills_raw = raw_data.get("skills", [])
    if not isinstance(skills_raw, list) or not skills_raw:
        raise ConfigurationError(
            "Skill taxonomy must declare a non-empty 'skills' list.",
            key="skills",
        )

    seen_canonicals: dict[str, str] = {}
    seen_aliases: dict[str, str] = {}
    validated_entries = [
        _validate_taxonomy_item(
            idx, item, allowed_categories, seen_canonicals, seen_aliases
        )
        for idx, item in enumerate(skills_raw)
    ]

    raw_confusables = raw_data.get("confusable_pairs", [])
    validated_confusables = [
        [str(pair[0]), str(pair[1])]
        for pair in raw_confusables
        if isinstance(pair, (list, tuple)) and len(pair) == 2
    ]

    return SkillTaxonomy(
        schema_version=str(raw_data.get("schema_version", "1.0")),
        sources=raw_data.get("sources"),
        categories=categories_list,
        skills=validated_entries,
        confusable_pairs=validated_confusables,
    )


def clear_taxonomy_cache() -> None:
    """Clear cached taxonomy instances (called in test fixtures)."""
    _load_taxonomy_cached.cache_clear()
