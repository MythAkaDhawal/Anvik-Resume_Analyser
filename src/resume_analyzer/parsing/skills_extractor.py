"""Extraction of candidate skills from skills section and resume body text (FR-05).

Combines explicit delimiter parsing in skills sections with taxonomy n-gram
body scanning, deduplicates by canonical name, and enforces stuffing bounds.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from resume_analyzer.models.candidate import ParseWarning, Skill
from resume_analyzer.models.enums import Provenance
from resume_analyzer.skills.normalizer import normalize_skill
from resume_analyzer.skills.skill_index import SkillIndex

logger = logging.getLogger(__name__)

# Delimiters for skills section splitting: newlines, commas, semicolons, pipes, bullets
SECTION_DELIMITERS = re.compile(r"[\n,;|•●▪■◦‣·]")


def extract_skills(
    sections: dict[str, str],
    index: SkillIndex,
) -> tuple[list[Skill], list[ParseWarning]]:
    """Extract skills from skills section and scan body text using taxonomy.

    Args:
        sections: Dictionary of extracted resume sections.
        index: Precomputed SkillIndex.

    Returns:
        Tuple of (list_of_skills, warnings_list).
    """
    warnings: list[ParseWarning] = []
    # Map key (canonical or normalized) -> Skill
    skills_map: dict[str, Skill] = {}

    skills_text = sections.get("skills", "")

    # 1. Parse Skills section (if present)
    if skills_text:
        _extract_from_skills_section(skills_text, index, skills_map)

    # 2. Body scan across experience, projects, summary, certifications, other
    body_text_parts: list[str] = [
        sections.get("experience", ""),
        sections.get("projects", ""),
        sections.get("summary", ""),
        sections.get("certifications", ""),
        sections.get("other", ""),
    ]
    # If no separate skills section exists, include header in body scan
    if not skills_text:
        body_text_parts.append(sections.get("header", ""))

    combined_body = "\n".join(part for part in body_text_parts if part)
    body_mentions: Counter[str] = index.find_mentions(combined_body)

    for canonical, count in body_mentions.items():
        key = canonical.lower()
        if key in skills_map:
            # Add body occurrences to section occurrence
            skills_map[key].mentions += count
        else:
            category = index.category(canonical)
            skills_map[key] = Skill(
                name=canonical,
                canonical_name=canonical,
                category=category,
                provenance=Provenance.EXTRACTED_RULE,
                mentions=count,
            )

    extracted_list = list(skills_map.values())

    # 3. Stuffing defense cap: 300 skills limit
    if len(extracted_list) > 300:
        extracted_list = extracted_list[:300]
        warnings.append(
            ParseWarning(
                code="SKILL_LIST_TRUNCATED",
                message="Extracted skills count exceeded 300; list truncated to first 300 items.",
                field="skills",
            )
        )

    if not extracted_list:
        warnings.append(
            ParseWarning(
                code="NO_SKILLS",
                message="No recognized or unrecognized skills were identified in the resume.",
                field="skills",
            )
        )

    return extracted_list, warnings


def _record_skill_token(
    token: str,
    index: SkillIndex,
    skills_map: dict[str, Skill],
) -> None:
    """Validate, normalize, and record a single skill token into the skills map."""
    token_clean = token.strip()
    if len(token_clean) > 40 or len(token_clean.split()) > 5:
        return

    norm = normalize_skill(token_clean)
    if not norm:
        return

    canonical = index.canonical(norm)
    if canonical:
        key = canonical.lower()
        if key in skills_map:
            skills_map[key].mentions += 1
        else:
            category = index.category(canonical)
            skills_map[key] = Skill(
                name=token_clean,
                canonical_name=canonical,
                category=category,
                provenance=Provenance.EXTRACTED_RULE,
                mentions=1,
            )
    else:
        key = norm
        if key not in skills_map:
            skills_map[key] = Skill(
                name=token_clean,
                canonical_name=None,
                category=None,
                provenance=Provenance.EXTRACTED_RULE,
                mentions=1,
            )
        else:
            skills_map[key].mentions += 1


def _extract_from_skills_section(
    skills_text: str,
    index: SkillIndex,
    skills_map: dict[str, Skill],
) -> None:
    """Parse comma/pipe/newline separated skills in dedicated skills section."""
    lines = skills_text.split("\n")
    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        if ":" in clean_line:
            _, rest = clean_line.split(":", 1)
            if rest.strip():
                clean_line = rest.strip()

        chunks = SECTION_DELIMITERS.split(clean_line)
        for chunk in chunks:
            frag = chunk.strip()
            if not frag:
                continue

            if "/" in frag:
                norm_whole = normalize_skill(frag)
                if index.canonical(norm_whole) is not None:
                    sub_tokens = [frag]
                else:
                    sub_tokens = [p.strip() for p in frag.split("/") if p.strip()]
            else:
                sub_tokens = [frag]

            for tok in sub_tokens:
                _record_skill_token(tok, index, skills_map)
