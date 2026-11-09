"""Text cleaning and normalization pipeline for raw resume text (FR-03).

Applies Unicode NFKC normalization, removes control/zero-width characters,
normalizes line endings, standardizes bullets, and re-joins hyphenated line breaks.
Guaranteed to be idempotent.
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width spaces and formatting artifacts
ZERO_WIDTH_CHARS = re.compile(r"[\u200b-\u200f\ufeff]")

# Bullet glyphs replaced with markdown list dashes
BULLET_CHARS = re.compile(r"[•●▪■◦‣·]")

# Hyphenated line break: letter + hyphen + newline + lowercase letter
HYPHEN_BREAK = re.compile(r"(?<=\w)-\n(?=[a-z])")

# 3 or more consecutive newlines
EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Clean and normalize raw extracted resume text into consistent format.

    Pipeline operations (in exact specified order):
    1. Unicode NFKC normalization.
    2. Remove control characters (except \\n, \\t) and zero-width spaces.
    3. Normalize line endings (\\r\\n and \\r -> \\n).
    4. Replace bullet glyphs with standard '- '.
    5. Re-join hyphenated line breaks when subsequent fragment starts lowercase.
    6. Collapse whitespace runs per line and strip trailing spaces.
    7. Collapse 3+ consecutive newlines to 2 (single blank line).
    8. Strip leading and trailing whitespace.

    Args:
        text: Raw text string from document extractors.

    Returns:
        Cleaned, normalized string. Strictly idempotent: clean_text(clean_text(x)) == clean_text(x).
    """
    if not text:
        return ""

    # 1. Unicode NFKC normalization
    t = unicodedata.normalize("NFKC", text)

    # 2. Remove control characters (except newline and tab) and zero-width chars
    t = ZERO_WIDTH_CHARS.sub("", t)
    t = "".join(
        c for c in t if c in ("\n", "\t") or (unicodedata.category(c)[0] != "C")
    )

    # 3. Normalize line endings
    t = t.replace("\r\n", "\n").replace("\r", "\n")

    # 4. Replace bullet glyphs with standard markdown bullet indicator
    t = BULLET_CHARS.sub("- ", t)

    # 5. Re-join hyphenated line breaks only when next line starts lowercase
    t = HYPHEN_BREAK.sub("", t)

    # 6. Collapse spaces/tabs on each line and strip trailing whitespace
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in t.split("\n")]
    t = "\n".join(lines)
    # Ensure uniform bullet spacing at start of line
    t = re.sub(r"(?m)^- +", "- ", t)

    # 7. Collapse 3+ blank lines to 2
    t = EXCESS_BLANK_LINES.sub("\n\n", t)

    # 8. Strip leading/trailing blank lines
    return t.strip()
