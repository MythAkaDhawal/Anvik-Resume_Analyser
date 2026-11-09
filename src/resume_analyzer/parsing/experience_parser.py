"""Experience section extraction, date range parsing, and total years calculation (FR-06).

Parses flexible date grammars, resolves 'Present' using reference_date, merges
overlapping intervals, and extracts job titles and company names.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from resume_analyzer.models.candidate import ExperienceEntry, ParseWarning
from resume_analyzer.models.enums import Provenance

logger = logging.getLogger(__name__)

MONTH_NAME_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

PRESENT_KEYWORDS = {"present", "current", "now", "ongoing", "till date", "to date"}

DATE_RANGE_REGEX = re.compile(
    r"(?i)\b((?:[a-z]{3,9}\.?\s+\d{4})|(?:\d{1,2}[./\-]\d{4})|(?:\d{4}))\s*(?:[-–—]|to|until|till)\s*((?:[a-z]{3,9}\.?\s+\d{4})|(?:\d{1,2}[./\-]\d{4})|(?:\d{4})|present|current|now|ongoing|till date|to date)\b"
)

# Precompiled date fragment patterns for high-throughput normalization
NUM_DATE_RE = re.compile(r"^(\d{1,2})[./\-](\d{4})$")
NAMED_DATE_RE = re.compile(r"^([a-z]{3,9})\.?\s+(\d{4})$")
YEAR_RE = re.compile(r"^(\d{4})$")

TITLE_LEXICON = {
    "engineer",
    "developer",
    "analyst",
    "intern",
    "manager",
    "scientist",
    "consultant",
    "designer",
    "lead",
    "architect",
    "administrator",
    "associate",
    "trainee",
    "specialist",
    "director",
    "head",
    "officer",
    "programmer",
    "coordinator",
    "technician",
    "tester",
}


def parse_date_fragment(frag: str, reference_date: date) -> tuple[date | None, bool]:
    """Parse a date fragment string into a resolved date object and is_current flag."""
    norm = frag.strip().lower()
    if norm in PRESENT_KEYWORDS:
        # First day of reference_date month
        return date(reference_date.year, reference_date.month, 1), True

    # Case 1: Numeric month and year (e.g., 01/2020, 1-2020, 03.2022)
    m_num = NUM_DATE_RE.match(norm)
    if m_num:
        m, y = int(m_num.group(1)), int(m_num.group(2))
        if 1 <= m <= 12 and 1950 <= y <= 2099:
            return date(y, m, 1), False

    # Case 2: Named month and year (e.g., Jan 2020, January 2020, Jan. 2020)
    m_named = NAMED_DATE_RE.match(norm)
    if m_named:
        name_str, y_str = m_named.group(1), m_named.group(2)
        if name_str in MONTH_NAME_MAP:
            y = int(y_str)
            m = MONTH_NAME_MAP[name_str]
            if 1950 <= y <= 2099:
                return date(y, m, 1), False

    # Case 3: Year only (e.g., 2020) -> July 1 midpoint per specification
    m_year = YEAR_RE.match(norm)
    if m_year:
        y = int(m_year.group(1))
        if 1950 <= y <= 2099:
            return date(y, 7, 1), False

    return None, False


def parse_experience(
    experience_text: str,
    reference_date: date,
) -> tuple[list[ExperienceEntry], list[ParseWarning]]:
    """Parse experience section into discrete ExperienceEntry records.

    Args:
        experience_text: Raw experience section text.
        reference_date: Reference date for current/present role resolution.

    Returns:
        Tuple of (entries_list, warnings_list).
    """
    entries: list[ExperienceEntry] = []
    warnings: list[ParseWarning] = []

    if not experience_text.strip():
        return entries, warnings

    lines = experience_text.split("\n")
    # Identify line indices containing date ranges
    range_occurrences: list[tuple[int, re.Match[str]]] = []
    for idx, line in enumerate(lines):
        match = DATE_RANGE_REGEX.search(line)
        if match:
            range_occurrences.append((idx, match))

    if not range_occurrences:
        warnings.append(
            ParseWarning(
                code="NO_EXPERIENCE_DATES",
                message="Experience section contains text but no parseable date ranges were found.",
                field="experience",
            )
        )
        return entries, warnings

    for i, (line_idx, match) in enumerate(range_occurrences):
        start_str, end_str = match.group(1), match.group(2)
        start_date, _ = parse_date_fragment(start_str, reference_date)
        end_date, is_current = parse_date_fragment(end_str, reference_date)

        # Title & Company extraction from line with date or line directly above it
        candidate_lines: list[str] = []
        if line_idx > 0:
            candidate_lines.append(lines[line_idx - 1])
        # Line containing the date, with the date string removed
        line_no_date = (
            lines[line_idx][: match.start()] + " " + lines[line_idx][match.end() :]
        ).strip()
        if line_no_date:
            candidate_lines.append(line_no_date)

        job_title, company = _extract_title_and_company(candidate_lines)

        # Duration and validity checking
        duration_months: int | None = None
        if start_date:
            # Future date check: start > 12 months after reference_date
            ref_future_bound = date(
                reference_date.year + 1, reference_date.month, reference_date.day
            )
            if start_date > ref_future_bound:
                warnings.append(
                    ParseWarning(
                        code="FUTURE_DATE",
                        message=f"Experience start date ({start_date.isoformat()}) is more than 1 year in the future.",
                        field="experience",
                    )
                )

            effective_end = end_date or reference_date
            if effective_end < start_date:
                warnings.append(
                    ParseWarning(
                        code="INVALID_DATE_RANGE",
                        message=f"Experience end date ({effective_end.isoformat()}) precedes start date ({start_date.isoformat()}).",
                        field="experience",
                    )
                )
                duration_months = None
            else:
                duration_months = max(
                    0,
                    (effective_end.year - start_date.year) * 12
                    + (effective_end.month - start_date.month),
                )

        # When role is current, stored end date must be None per spec
        stored_end = None if is_current else end_date

        entries.append(
            ExperienceEntry(
                job_title=job_title,
                company=company,
                start=start_date,
                end=stored_end,
                is_current=is_current,
                duration_months=duration_months,
                provenance=Provenance.EXTRACTED_RULE,
            )
        )

    return entries, warnings


def _extract_title_and_company(
    candidate_lines: list[str],
) -> tuple[str | None, str | None]:
    """Extract job title and company from line fragments around date ranges."""
    for line in candidate_lines:
        line_clean = re.sub(r"^[#\s\-*•]+", "", line).strip()
        if not line_clean:
            continue

        # Split on common separators: ' at ', ' @ ', ' | ', ' - ', ', '
        parts = re.split(r"\s+(?:at|@)\s+|\s*\|\s*|\s+-\s+|,\s*", line_clean)
        parts = [p.strip() for p in parts if p.strip()]

        title: str | None = None
        company: str | None = None

        for idx, part in enumerate(parts):
            words = set(re.findall(r"[a-zA-Z]+", part.lower()))
            if words & TITLE_LEXICON:
                title = part
                # Remaining parts may indicate company
                other_parts = [p for j, p in enumerate(parts) if j != idx]
                if other_parts:
                    company = other_parts[0]
                break

        if title or company:
            return title, company

    return None, None


def compute_duration_months(
    start: date | None,
    end: date | None,
    is_current: bool = False,
    reference_date: date | None = None,
) -> int | None:
    """Compute duration in months between start and end dates."""
    if start is None:
        return None
    ref = reference_date or date.today()
    effective_end = end or ref
    if effective_end < start:
        return None
    return max(
        0,
        (effective_end.year - start.year) * 12 + (effective_end.month - start.month),
    )


def _extract_valid_intervals(
    entries: list[ExperienceEntry],
    reference_date: date,
    count_internships: bool,
) -> list[tuple[date, date]]:
    """Extract valid, sanitized start and end date intervals from entries."""
    valid_intervals: list[tuple[date, date]] = []
    ref_future_bound = date(
        reference_date.year + 1, reference_date.month, reference_date.day
    )

    for entry in entries:
        if (
            not count_internships
            and entry.job_title
            and "intern" in entry.job_title.lower()
        ):
            continue
        if not entry.start or entry.start > ref_future_bound:
            continue

        end_date = entry.end or (reference_date if entry.is_current else None)
        if not end_date or end_date < entry.start:
            continue

        valid_intervals.append((entry.start, end_date))

    return valid_intervals


def _merge_date_intervals(
    intervals: list[tuple[date, date]],
) -> list[tuple[date, date]]:
    """Sort and merge overlapping or contiguous date ranges."""
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged: list[tuple[date, date]] = [sorted_intervals[0]]

    for current_start, current_end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if current_start <= last_end:
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))

    return merged


def total_experience_years(
    entries: list[ExperienceEntry],
    reference_date: date,
    count_internships: bool = True,
) -> float | None:
    """Calculate non-overlapping total years of professional experience.

    Merges overlapping and touching date intervals, sums total duration,
    and returns years rounded to 1 decimal place.

    Args:
        entries: Extracted ExperienceEntry list.
        reference_date: Active reference date for current roles.
        count_internships: Whether to include roles titled 'intern'.

    Returns:
        Total experience years as float, or None if no valid dates were present.
    """
    valid_intervals = _extract_valid_intervals(
        entries, reference_date, count_internships
    )
    if not valid_intervals:
        return None

    merged = _merge_date_intervals(valid_intervals)
    total_months = sum(
        max(0, (end.year - start.year) * 12 + (end.month - start.month))
        for start, end in merged
    )
    return round(total_months / 12.0, 1)
