"""Deterministic extraction of candidate contact information: name and email (FR-04).

Follows conservative heuristics without fabrication. Phone numbers and street
addresses are excluded to preserve privacy (NFR-11, NFR-14).
"""

from __future__ import annotations

import logging
import re

from resume_analyzer.models.candidate import ParseWarning
from resume_analyzer.parsing.section_splitter import _detect_heading

logger = logging.getLogger(__name__)

# Strict standard email pattern
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Non-name document title phrases that should never be accepted as a candidate name
DISALLOWED_NAME_PHRASES = {
    "curriculum vitae",
    "resume",
    "cv",
    "bio",
    "profile",
    "summary",
    "contact information",
    "personal information",
    "details",
}

# Individual token validation: alphabetic with allowed '.', "'", '-'
NAME_TOKEN_REGEX = re.compile(r"^[A-Za-z]+[.'\-]?[A-Za-z]*\.?$")


def extract_email(
    header_text: str,
    full_text: str,
) -> tuple[str | None, list[ParseWarning]]:
    """Extract email address from header or full text, validating structure.

    Args:
        header_text: Text preceding first section heading.
        full_text: Entire resume text.

    Returns:
        Tuple of (primary_email, warnings_list).
    """
    warnings: list[ParseWarning] = []

    # Find emails in header first, then in full text
    header_matches = EMAIL_REGEX.findall(header_text)
    full_matches = EMAIL_REGEX.findall(full_text)

    # Combine matches preserving order
    all_raw_emails = header_matches + [
        e for e in full_matches if e not in header_matches
    ]

    valid_emails: list[str] = []
    seen_lower: set[str] = set()

    for candidate_str in all_raw_emails:
        c_clean = candidate_str.strip().rstrip(".,;")
        if len(c_clean) > 254:
            continue
        if c_clean.count("@") != 1:
            continue
        user, domain = c_clean.split("@", 1)
        if not user or not domain or "." not in domain:
            continue
        # Avoid file-extension false positives like 'name@company.pdf'
        if domain.lower().endswith((".pdf", ".doc", ".docx", ".txt", ".png", ".jpg")):
            continue

        lower = c_clean.lower()
        if lower not in seen_lower:
            seen_lower.add(lower)
            valid_emails.append(c_clean)

    if not valid_emails:
        warnings.append(
            ParseWarning(
                code="NO_EMAIL",
                message="No valid candidate email address detected.",
                field="email",
            )
        )
        return None, warnings

    primary = valid_emails[0]
    if len(valid_emails) > 1:
        warnings.append(
            ParseWarning(
                code="MULTIPLE_EMAILS",
                message=f"Multiple email addresses found ({len(valid_emails)}); first match retained.",
                field="email",
            )
        )

    return primary, warnings


def _is_valid_name_candidate(line: str) -> str | None:
    """Validate whether a candidate header line represents a real name."""
    if any(char.isdigit() for char in line) or "@" in line:
        return None
    lower_raw = line.lower()
    if "http:" in lower_raw or "https:" in lower_raw or "www." in lower_raw:
        return None

    clean_line = re.sub(r"^[#\s\-*•]+", "", line).strip()
    lower_line = clean_line.lower()

    if _detect_heading(clean_line) is not None:
        return None
    if lower_line in DISALLOWED_NAME_PHRASES:
        return None
    if any(
        phrase in lower_line for phrase in ("curriculum vitae", "resume of", "resume")
    ):
        return None

    tokens = clean_line.split()
    if not (2 <= len(tokens) <= 4):
        return None

    if all(NAME_TOKEN_REGEX.match(tok) for tok in tokens):
        return clean_line
    return None


def extract_name(
    header_text: str,
    email: str | None,
) -> tuple[str | None, list[ParseWarning]]:
    """Extract candidate name using conservative heuristic rules.

    Rules from TECHNICAL_SPECIFICATION §6.3:
    1. First non-empty header line.
    2. Has 2-4 tokens.
    3. Each token is alphabetic (allowing '.', ''', '-').
    4. Not a heading synonym or generic resume label.
    5. Contains no digits, '@', or URL.

    Args:
        header_text: Text preceding first section header.
        email: Extracted candidate email, if any.

    Returns:
        Tuple of (name_or_none, warnings_list).
    """
    warnings: list[ParseWarning] = []

    if not header_text:
        warnings.append(
            ParseWarning(
                code="NO_NAME",
                message="Candidate name could not be reliably determined from header.",
                field="name",
            )
        )
        return None, warnings

    lines = [line.strip() for line in header_text.split("\n") if line.strip()]

    for line in lines:
        name_found = _is_valid_name_candidate(line)
        if name_found:
            return name_found, warnings

    warnings.append(
        ParseWarning(
            code="NO_NAME",
            message="Candidate name could not be reliably determined from header.",
            field="name",
        )
    )
    return None, warnings
