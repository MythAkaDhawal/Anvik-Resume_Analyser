"""Skill normalization and cached fuzzy similarity routines (FR-05, NFR-03).

Provides deterministic NFKC normalization, punctuation trimming preserving
syntactically meaningful symbols (C++, C#, .NET, Node.js), and LRU-cached operations.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from rapidfuzz import fuzz

# Precompiled regular expressions for skill string cleanup
PAREN_RE = re.compile(r"\(.*?\)")
DASHES_RE = re.compile(r"[\u2010\u2012\u2013\u2014\u2015\u2212]")
WHITESPACE_RE = re.compile(r"\s+")
LEADING_PUNCT_RE = re.compile(r"^[\s,;:!?'\"*()\[\]{}|\\_~`]+")
TRAILING_PUNCT_RE = re.compile(r"[\s,;:!?'\"*()\[\]{}|\\_~`.]+$")

# Punctuation to strip from ends, keeping meaningful +, #, ., / when internal or prefix/suffix
LEADING_PUNCT_CHARS = r"^[\s,;:!?'\"*()\[\]{}|\\_~`]+"
TRAILING_PUNCT_CHARS = r"[\s,;:!?'\"*()\[\]{}|\\_~`.]+$"

# Specific preserved tokens where leading dot or trailing dot is essential
PRESERVED_PREFIX_DOTS = {".net"}


@lru_cache(maxsize=8192)
def normalize_skill(text: str) -> str:
    """Normalize a skill string into a canonical search key.

    Operations applied:
    1. Unicode NFKC normalization.
    2. Lowercase conversion.
    3. Remove parenthetical descriptions (e.g., 'Python (3 yrs)' -> 'python').
    4. Normalize varied unicode dashes to standard hyphen.
    5. Strip extraneous punctuation while preserving C++, C#, .NET, Node.js.
    6. Collapse whitespace runs.

    Args:
        text: Raw skill text as found in resume or job description.

    Returns:
        Normalized string suitable for dictionary lookups and comparison.
    """
    if not text:
        return ""

    # 1. Unicode NFKC normalization
    norm = unicodedata.normalize("NFKC", text)

    # 2. Lowercase
    norm = norm.lower()

    # 3. Remove parenthetical notes
    norm = PAREN_RE.sub("", norm)

    # 4. Normalize dashes (em-dash, en-dash, minus)
    norm = DASHES_RE.sub("-", norm)

    # 5. Collapse spaces and strip
    norm = WHITESPACE_RE.sub(" ", norm).strip()

    # 6. Punctuation stripping with exceptions for .net, c++, c#
    if norm.startswith(".") and not any(
        norm.startswith(p) for p in PRESERVED_PREFIX_DOTS
    ):
        norm = norm.lstrip(".")

    # Strip unwanted boundary punctuation
    norm = LEADING_PUNCT_RE.sub("", norm)

    # Strip trailing punctuation, but protect trailing '+' or '#' (C++, C#)
    # Also allow 'node.js' (internal dot) but strip trailing period like 'python.'
    if not norm.endswith(("+", "#")):
        norm = TRAILING_PUNCT_RE.sub("", norm)

    # Final whitespace cleanup
    norm = WHITESPACE_RE.sub(" ", norm).strip()
    return norm


@lru_cache(maxsize=65536)
def fuzzy_similarity(a: str, b: str) -> float:
    """Calculate normalized similarity ratio between two strings on a 0-100 scale.

    Pure function wrapped in LRU cache to accelerate repeat comparisons across batches.

    Args:
        a: First normalized string.
        b: Second normalized string.

    Returns:
        Similarity score between 0.0 and 100.0.
    """
    if a == b:
        return 100.0
    if not a or not b:
        return 0.0
    return float(fuzz.ratio(a, b))


def clear_normalizer_caches() -> None:
    """Clear normalizer and fuzzy similarity LRU caches (called in test fixtures)."""
    normalize_skill.cache_clear()
    fuzzy_similarity.cache_clear()
