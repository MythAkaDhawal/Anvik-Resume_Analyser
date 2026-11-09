"""PII masking and prompt injection indicator scanner (NFR-11, NFR-13).

Redacts personal contact details (email, phone, URLs, street addresses)
before untrusted text is sent to any GenAI provider, and flags suspicious
injection vectors using regex heuristics.
"""

from __future__ import annotations

import re

# PII patterns
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,4}[-.\s]?)?(?:\(?\d{2,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{3,5}\b"
)
URL_PATTERN = re.compile(
    r"(?:https?://\S+|www\.\S+|(?:linkedin\.com/in/|github\.com/)[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
ADDRESS_PATTERN = re.compile(
    r"(?i)\b\d{1,5}\s+[A-Za-z0-9\s.,]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|court|ct|square|sq)\b[^\n]*",
)

# Injection indicator heuristic patterns per AI_PROMPTS §2.4
INJECTION_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "IGNORE_INSTRUCTIONS",
        re.compile(
            r"(?i)\b(?:ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above)\s+(?:instructions|prompts)|disregard\s+.*instructions)\b"
        ),
    ),
    (
        "ROLE_OVERRIDE",
        re.compile(
            r"(?i)\b(?:you\s+are\s+now|act\s+as\s+a?|new\s+instructions|system\s+prompt|system\s*:|developer\s+message)\b"
        ),
    ),
    (
        "SCORE_MANIPULATION",
        re.compile(
            r"(?i)(?:(?:give|assign|rate|score).{0,40}(?:100|perfect|highest|maximum)|top\s+candidate|must\s+(?:hire|select))\b"
        ),
    ),
    (
        "OUTPUT_FORMAT_HIJACK",
        re.compile(
            r"(?i)\b(?:respond\s+(?:only\s+)?with|output\s+(?:only\s+)?json|return\s+the\s+following)\b"
        ),
    ),
    (
        "DELIMITER_SPOOF",
        re.compile(r"<<<|>>>|_BEGIN|_END|</?RESUME>|</?SYSTEM>", re.IGNORECASE),
    ),
]


def mask_pii(text: str) -> str:
    """Mask email, phone, URL, and street address entities in resume text.

    Skills, experience, companies, and professional content are preserved.

    Args:
        text: Raw or cleaned resume text.

    Returns:
        Sanitized text with [EMAIL], [PHONE], [URL], and [ADDRESS] placeholders.
    """
    if not text:
        return ""

    # Replace emails
    masked = EMAIL_PATTERN.sub("[EMAIL]", text)

    # Replace URLs
    masked = URL_PATTERN.sub("[URL]", masked)

    # Replace street addresses
    masked = ADDRESS_PATTERN.sub("[ADDRESS]", masked)

    # Replace phone numbers
    masked = PHONE_PATTERN.sub("[PHONE]", masked)

    return masked


def scan_injection_indicators(text: str) -> list[str]:
    """Scan resume text for heuristic prompt injection and manipulation attempts.

    Produces indicator codes only. Never alters candidate scoring or blocks parsing.

    Args:
        text: Resume text to scan.

    Returns:
        List of unique triggered indicator codes (e.g. ['IGNORE_INSTRUCTIONS']).
    """
    if not text:
        return []

    indicators: list[str] = []

    # 1. Regex pattern scans
    for code, pattern in INJECTION_RULES:
        if pattern.search(text):
            indicators.append(code)

    # 2. Keyword stuffing detection
    lines = text.split("\n")
    for line in lines:
        comma_tokens = [tok.strip() for tok in line.split(",") if tok.strip()]
        if len(comma_tokens) > 40:
            if "KEYWORD_STUFFING" not in indicators:
                indicators.append("KEYWORD_STUFFING")
            break

    return sorted(set(indicators))
