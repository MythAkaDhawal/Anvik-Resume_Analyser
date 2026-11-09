"""Provenance definitions, badges, and validation rules.

Enforces clear origin attribution for every data point (FR-22) and ensures
absence of automated employment verdicts or recommendation language (FR-16, NFR-15).
"""

from __future__ import annotations

import re

from resume_analyzer.models.enums import Provenance
from resume_analyzer.models.results import DEFAULT_HUMAN_REVIEW_NOTICE

HUMAN_REVIEW_NOTICE = DEFAULT_HUMAN_REVIEW_NOTICE
AI_UNVERIFIED_NOTICE = "AI-generated — not verified"
AI_UNAVAILABLE_NOTICE_TEMPLATE = "AI-generated content unavailable ({status})"

PROVENANCE_DISPLAY_NAMES: dict[Provenance, str] = {
    Provenance.EXTRACTED_RULE: "Rule-based extraction",
    Provenance.EXTRACTED_AI: "AI extraction",
    Provenance.COMPUTED: "Deterministic computation",
    Provenance.AI_GENERATED: AI_UNVERIFIED_NOTICE,
}

PROVENANCE_BADGE_CSS: dict[Provenance, str] = {
    Provenance.EXTRACTED_RULE: "badge-rule",
    Provenance.EXTRACTED_AI: "badge-ai-extracted",
    Provenance.COMPUTED: "badge-computed",
    Provenance.AI_GENERATED: "badge-ai-generated",
}

# Regex to detect prohibited automated employment verdict words
VERDICT_LANGUAGE_PATTERN = re.compile(
    r"\b(hire|hired|hiring|reject|rejected|rejecting|unhireable|hireable)\b",
    re.IGNORECASE,
)


def get_provenance_display(provenance: Provenance) -> str:
    """Return the standardized user-facing display label for a provenance tier."""
    return PROVENANCE_DISPLAY_NAMES.get(provenance, str(provenance.value))


def get_badge_css_class(provenance: Provenance) -> str:
    """Return the CSS class for rendering provenance badges."""
    return PROVENANCE_BADGE_CSS.get(provenance, "badge-default")


def contains_verdict_language(text: str) -> bool:
    """Check whether a text string contains prohibited automated employment verdicts."""
    return bool(VERDICT_LANGUAGE_PATTERN.search(text))


def validate_no_verdict_language(text: str, context: str = "rendered text") -> None:
    """Validate that text does not contain prohibited employment verdict language.

    Raises:
        ValueError: If verdict words ('hire', 'reject', etc.) are present.
    """
    matches = VERDICT_LANGUAGE_PATTERN.findall(text)
    if matches:
        raise ValueError(
            f"Prohibited employment verdict language detected in {context}: {matches}. "
            "Automated verdicts violate NFR-15."
        )
