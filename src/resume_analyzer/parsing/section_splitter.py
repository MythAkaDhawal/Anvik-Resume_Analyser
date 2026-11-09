"""Resume section splitting and heading identification (FR-05, FR-06, FR-07).

Identifies standard section headers (summary, skills, experience, education,
projects, certifications) and partitions resume text into structured segments.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Heading synonyms mapped to standard section keys
HEADING_SYNONYMS: dict[str, list[str]] = {
    "summary": [
        "summary",
        "professional summary",
        "profile",
        "personal profile",
        "career summary",
        "executive summary",
        "objective",
        "career objective",
        "about me",
    ],
    "skills": [
        "skills",
        "technical skills",
        "core competencies",
        "key skills",
        "technologies",
        "tools",
        "technical proficiencies",
        "competencies",
        "skillset",
        "skills & expertise",
        "skills and tools",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "internships",
        "work history",
        "career history",
        "employment",
        "relevant experience",
    ],
    "education": [
        "education",
        "academic background",
        "qualifications",
        "academics",
        "educational qualifications",
        "academic history",
        "education & training",
    ],
    "projects": [
        "projects",
        "personal projects",
        "academic projects",
        "technical projects",
        "key projects",
    ],
    "certifications": [
        "certifications",
        "certificates",
        "licenses",
        "courses",
        "professional certifications",
        "training & certifications",
    ],
}

# Inverted mapping: cleaned synonym -> canonical section key
_SYNONYM_TO_KEY: dict[str, str] = {}
for sec_key, syn_list in HEADING_SYNONYMS.items():
    for syn in syn_list:
        _SYNONYM_TO_KEY[syn.lower()] = sec_key


def _detect_heading(line: str) -> str | None:
    """Determine whether a line qualifies as a recognized section header."""
    clean_line = line.strip()
    if not clean_line:
        return None

    # Strip markdown headers (##), bullet points, and trailing punctuation/colons
    stripped = re.sub(r"^[#\s\-*•]+", "", clean_line)
    stripped = re.sub(r"[:\-—_.]+$", "", stripped).strip()

    # Must be <= 40 chars and <= 5 words per specification
    if len(stripped) > 40:
        return None
    words = stripped.split()
    if not words or len(words) > 5:
        return None

    norm_lower = stripped.lower()

    # Exact match against synonyms
    if norm_lower in _SYNONYM_TO_KEY:
        return _SYNONYM_TO_KEY[norm_lower]

    # Prefix match (e.g. "Technical Skills (Advanced)")
    for syn, key in _SYNONYM_TO_KEY.items():
        if norm_lower.startswith(syn):
            # Check boundary after synonym
            remainder = norm_lower[len(syn) :].strip()
            if not remainder or remainder.startswith(("(", "-", ":", "&")):
                return key

    return None


def split_sections(text: str) -> tuple[dict[str, str], list[str]]:
    """Partition cleaned resume text into standard sections.

    Args:
        text: Normalized resume text.

    Returns:
        Tuple of (sections_dict, warnings) where sections_dict has keys:
        'header', 'summary', 'skills', 'experience', 'education',
        'projects', 'certifications', 'other'.
    """
    sections: dict[str, list[str]] = {
        "header": [],
        "summary": [],
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "other": [],
    }
    warnings: list[str] = []

    lines = text.split("\n")
    current_section = "header"
    detected_any_heading = False

    for line in lines:
        heading_key = _detect_heading(line)
        if heading_key:
            current_section = heading_key
            detected_any_heading = True
        else:
            sections[current_section].append(line)

    if not detected_any_heading:
        # Whole text is treated as 'other' and warning raised
        warnings.append("NO_SECTIONS_DETECTED")
        sections["other"] = lines
        sections["header"] = []

    result = {k: "\n".join(v).strip() for k, v in sections.items()}
    return result, warnings
