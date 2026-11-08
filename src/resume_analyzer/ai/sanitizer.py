"""Prompt sanitization, nonce generation, and delimiter isolation (AI_PROMPTS §2)."""

from __future__ import annotations

import re
import secrets

from resume_analyzer.parsing.pii import mask_pii

# Lookalike delimiter patterns
DELIMITER_OPEN = re.compile(r"<<<")
DELIMITER_CLOSE = re.compile(r">>>")
BEGIN_PATTERN = re.compile(r"_BEGIN", re.IGNORECASE)
END_PATTERN = re.compile(r"_END", re.IGNORECASE)
ROLE_OVERRIDE_LINES = re.compile(r"(?im)^(?:system|assistant|developer|user)\s*:\s*")


def generate_nonce() -> str:
    """Generate a random 16-character hexadecimal nonce for delimiter uniqueness."""
    return secrets.token_hex(8)


def sanitize_prompt_text(text: str, max_chars: int = 100000) -> tuple[str, bool]:
    """Sanitize untrusted text before template interpolation.

    Operations:
    1. Truncate to maximum characters if needed.
    2. Neutralize opening and closing delimiter brackets (<<< and >>>).
    3. Neutralize _BEGIN and _END marker tokens.
    4. Strip fake role prefixes at line beginnings.

    Args:
        text: Raw untrusted resume or candidate text.
        max_chars: Character ceiling.

    Returns:
        Tuple of (sanitized_text, was_truncated).
    """
    if not text:
        return "", False

    truncated = False
    clean = text
    if len(clean) > max_chars:
        clean = clean[:max_chars]
        truncated = True

    # 1. Neutralize angle bracket delimiters
    clean = DELIMITER_OPEN.sub("[DELIM_OPEN]", clean)
    clean = DELIMITER_CLOSE.sub("[DELIM_CLOSE]", clean)

    # 2. Neutralize marker keywords
    clean = BEGIN_PATTERN.sub("[START]", clean)
    clean = END_PATTERN.sub("[STOP]", clean)

    # 3. Strip forged role-override line prefixes
    clean = ROLE_OVERRIDE_LINES.sub("", clean)

    return clean, truncated


def prepare_untrusted_resume(raw_text: str, nonce: str, max_chars: int = 100000) -> str:
    """Mask PII, sanitize delimiters, and wrap untrusted resume in nonce markers."""
    # 1. Mask PII (email, phone, url, address)
    masked = mask_pii(raw_text)

    # 2. Sanitize delimiters and forged markers
    sanitized, _ = sanitize_prompt_text(masked, max_chars=max_chars)

    # 3. Delimit with per-call nonce
    return f"<<<RESUME_{nonce}_BEGIN>>>\n{sanitized}\n<<<RESUME_{nonce}_END>>>"


# Alias for backward compatibility
mask_and_delimit_resume = prepare_untrusted_resume
