"""Null provider for fully offline / AI-disabled operation (DR-AI-1, DR-AI-2)."""

from __future__ import annotations

import logging

from resume_analyzer.exceptions import AIProviderUnavailableError

logger = logging.getLogger(__name__)


class NullProvider:
    """Provider backend active when AI integration is disabled or unconfigured.

    Allows the complete deterministic parsing, matching, and scoring pipeline
    to operate without external network requests or language model dependencies.
    """

    def __init__(self) -> None:
        """Initialize NullProvider."""
        self.is_null: bool = True

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Raise AIProviderUnavailableError since AI is disabled."""
        logger.debug("NullProvider invoked; AI operations are disabled.")
        raise AIProviderUnavailableError(
            "AI features are disabled or no active provider is configured.",
            details={"provider": "null"},
        )
