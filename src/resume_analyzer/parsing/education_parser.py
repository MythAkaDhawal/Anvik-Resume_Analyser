"""Education section parsing and deterministic qualification attainment mapping (FR-07).

Identifies degrees, attainment levels, academic majors, and educational institutions
while strictly excluding graduation years to prevent age/proxy bias (NFR-14).
"""

from __future__ import annotations

import logging
import re

from resume_analyzer.models.candidate import EducationEntry, ParseWarning
from resume_analyzer.models.enums import EducationLevel, Provenance

logger = logging.getLogger(__name__)

# Degree keyword definitions mapped to EducationLevel
# Short abbreviations (<= 3 chars) are matched case-sensitively
DEGREE_KEYWORDS: list[tuple[EducationLevel, list[str], list[str]]] = [
    # Level, case-insensitive patterns, case-sensitive short patterns
    (
        EducationLevel.DOCTORATE,
        [
            r"\bph\.?d\b",
            r"\bdoctorate\b",
            r"\bdoctor of philosophy\b",
            r"\bd\.phil\b",
        ],
        [],
    ),
    (
        EducationLevel.MASTER,
        [
            r"\bmaster(?:'s)?\b",
            r"\bm\.?sc\b",
            r"\bmsc\b",
            r"\bm\.?s\.\b",
            r"\bm\.?tech\b",
            r"\bmtech\b",
            r"\bm\.?e\.\b",
            r"\bmba\b",
            r"\bm\.?a\.\b",
            r"\bmca\b",
            r"\bm\.?eng\b",
            r"\bmeng\b",
        ],
        [r"\bMS\b", r"\bME\b", r"\bMA\b"],
    ),
    (
        EducationLevel.BACHELOR,
        [
            r"\bbachelor(?:'s)?\b",
            r"\bb\.?sc\b",
            r"\bbsc\b",
            r"\bb\.?s\.\b",
            r"\bb\.?tech\b",
            r"\bbtech\b",
            r"\bb\.?e\.\b",
            r"\bb\.?a\.\b",
            r"\bbca\b",
            r"\bb\.?com\b",
            r"\bbcom\b",
            r"\bb\.?eng\b",
            r"\bbeng\b",
            r"\bundergraduate degree\b",
        ],
        [r"\bBS\b", r"\bBE\b", r"\bBA\b"],
    ),
    (
        EducationLevel.HIGH_SCHOOL,
        [
            r"\bhigh school(?: diploma)?\b",
            r"\bsecondary school\b",
            r"\bhsc\b",
            r"\bssc\b",
            r"\b12th\b",
            r"\b10th\b",
            r"\ba-levels\b",
            r"\bgcse\b",
        ],
        [],
    ),
    (
        EducationLevel.DIPLOMA,
        [
            r"\bdiploma\b",
            r"\bassociate(?:'s)? degree\b",
            r"\bassociate of\b",
            r"\bpolytechnic\b",
            r"\ba\.?s\.\b",
            r"\ba\.?a\.\b",
        ],
        [],
    ),
]

# Precompile degree regex patterns once at import time
COMPILED_DEGREE_PATTERNS: list[
    tuple[EducationLevel, list[re.Pattern[str]], list[re.Pattern[str]]]
] = [
    (
        level,
        [re.compile(p, re.IGNORECASE) for p in ci],
        [re.compile(p) for p in cs],
    )
    for level, ci, cs in DEGREE_KEYWORDS
]

INSTITUTION_KEYWORDS = re.compile(
    r"(?i)\b(?:university|college|institute|school|academy|polytechnic)\b"
)


def _extract_institution_from_lines(
    entry_lines: list[str], primary_line: str
) -> str | None:
    """Extract education institution by scanning lines for institution keywords."""
    for el in entry_lines:
        if not INSTITUTION_KEYWORDS.search(el):
            continue
        inst_cand = re.sub(r"^[#\s\-*•]+", "", el).strip()
        if el == primary_line:
            parts = re.split(r",\s*|\s*\|\s*|\s+-\s+", inst_cand)
            for p in parts:
                if INSTITUTION_KEYWORDS.search(p):
                    return p.strip()
        else:
            return inst_cand
    return None


def parse_education(
    education_text: str,
) -> tuple[list[EducationEntry], EducationLevel, list[ParseWarning]]:
    """Parse education section into EducationEntry records and compute highest level.

    Args:
        education_text: Raw education section text.

    Returns:
        Tuple of (entries_list, highest_level, warnings_list).
    """
    entries: list[EducationEntry] = []
    warnings: list[ParseWarning] = []

    if not education_text.strip():
        warnings.append(
            ParseWarning(
                code="NO_EDUCATION",
                message="No education section or qualifications were found in the resume.",
                field="education",
            )
        )
        return entries, EducationLevel.UNSPECIFIED, warnings

    lines = [line.strip() for line in education_text.split("\n") if line.strip()]

    # Locate lines that start a degree qualification
    degree_matches: list[tuple[int, EducationLevel, str]] = []
    for idx, line in enumerate(lines):
        level, matched_str = _match_degree_level(line)
        if level != EducationLevel.UNSPECIFIED:
            degree_matches.append((idx, level, matched_str))

    if not degree_matches:
        warnings.append(
            ParseWarning(
                code="UNKNOWN_DEGREE",
                message="Education text found, but qualifications could not be mapped to standard levels.",
                field="education",
            )
        )
        # Create an entry with UNSPECIFIED level retaining the raw text
        entries.append(
            EducationEntry(
                degree=lines[0] if lines else None,
                level=EducationLevel.UNSPECIFIED,
                provenance=Provenance.EXTRACTED_RULE,
            )
        )
        return entries, EducationLevel.UNSPECIFIED, warnings

    for i, (line_idx, level, matched_str) in enumerate(degree_matches):
        next_line_idx = (
            degree_matches[i + 1][0] if i + 1 < len(degree_matches) else len(lines)
        )
        entry_lines = lines[line_idx:next_line_idx]
        primary_line = entry_lines[0]

        # Field of study extraction from primary line (or subsequent line)
        field_of_study = _extract_field_of_study(primary_line, matched_str)
        if not field_of_study and len(entry_lines) > 1:
            field_of_study = _extract_field_of_study(entry_lines[1], "")

        institution = _extract_institution_from_lines(entry_lines, primary_line)

        entries.append(
            EducationEntry(
                degree=primary_line,
                level=level,
                field_of_study=field_of_study,
                institution=institution,
                provenance=Provenance.EXTRACTED_RULE,
            )
        )

    highest_level = max(
        (entry.level for entry in entries), default=EducationLevel.UNSPECIFIED
    )
    return entries, highest_level, warnings


def detect_education_level(degree: str) -> EducationLevel:
    """Detect educational attainment level from a degree description string."""
    level, _ = _match_degree_level(degree)
    return level


def _match_degree_level(line: str) -> tuple[EducationLevel, str]:
    """Test a line against degree keyword patterns in priority order."""
    for level, ci_patterns, cs_patterns in COMPILED_DEGREE_PATTERNS:
        # 1. Case-insensitive matches
        for pat in ci_patterns:
            m = pat.search(line)
            if m:
                return level, m.group(0)

        # 2. Case-sensitive matches (for short 2-3 char abbreviations like BS, MS, BE, ME)
        for pat in cs_patterns:
            m = pat.search(line)
            if m:
                return level, m.group(0)

    return EducationLevel.UNSPECIFIED, ""


def _extract_field_of_study(line: str, matched_keyword: str) -> str | None:
    """Extract academic discipline following 'in', 'of', or comma after degree keyword."""
    # Pattern: 'in <field>', 'of <field>', or ', <field>'
    m = re.search(r"(?:in|of|,)\s+([A-Za-z\s&/]+)", line, re.IGNORECASE)
    if m:
        field_candidate = m.group(1).strip()
        # Stop at delimiters: '|', '(', comma, a year, or institution
        field_candidate = re.split(
            r"\s*\|\s*|\s*\(\s*|,\s*|\b(?:19\d\d|20\d\d)\b|\b(?:university|college|school)\b",
            field_candidate,
            flags=re.IGNORECASE,
        )[0].strip()

        if 2 <= len(field_candidate) <= 60:
            # Reject if candidate is just "Science" from "Bachelor of Science" without major
            if field_candidate.lower() in (
                "science",
                "arts",
                "engineering",
                "technology",
                "commerce",
            ):
                # Try finding 'in <major>' specifically
                m_in = re.search(r"\bin\s+([A-Za-z\s&/]+)", line, re.IGNORECASE)
                if m_in:
                    f2 = m_in.group(1).strip()
                    f2 = re.split(r"\s*\|\s*|\s*\(\s*|,\s*", f2)[0].strip()
                    if 2 <= len(f2) <= 60:
                        return f2
            return field_candidate

    return None
