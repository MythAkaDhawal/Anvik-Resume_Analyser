"""Provider factory instantiating LLM backends according to configuration (DR-AI-1)."""

from __future__ import annotations

import logging
import os

from resume_analyzer.ai.provider_base import LLMProvider
from resume_analyzer.ai.providers.gemini import GeminiProvider
from resume_analyzer.ai.providers.null import NullProvider
from resume_analyzer.ai.providers.ollama import OllamaProvider
from resume_analyzer.ai.providers.openai_compatible import OpenAICompatibleProvider
from resume_analyzer.config.settings import AISettings

logger = logging.getLogger(__name__)


def get_provider(settings: AISettings) -> LLMProvider:
    """Instantiate and return the configured LLMProvider.

    Keys are read only from environment variables, never hardcoded.
    If AI is disabled or keys are absent, cleanly falls back to NullProvider.

    Args:
        settings: Active AISettings configuration.

    Returns:
        LLMProvider instance.
    """
    if not settings.enabled or settings.provider.lower() == "null":
        logger.debug("AI integration disabled; using NullProvider.")
        return NullProvider()

    provider_name = settings.provider.lower()

    if provider_name == "fake":
        from resume_analyzer.ai.providers.fake import FakeProvider

        return FakeProvider()

    if provider_name == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            logger.warning(
                "Gemini provider configured but GEMINI_API_KEY environment variable is missing. "
                "Falling back to NullProvider."
            )
            return NullProvider()
        return GeminiProvider(
            model=settings.model,
            api_key=key,
            timeout_s=settings.timeout_s,
        )

    if provider_name == "ollama":
        base_url = settings.base_url or "http://localhost:11434"
        return OllamaProvider(
            model=settings.model,
            base_url=base_url,
            timeout_s=settings.timeout_s,
        )

    if provider_name in ("openai", "openai_compatible"):
        base_url = settings.base_url or "https://api.openai.com/v1"
        return OpenAICompatibleProvider(
            model=settings.model,
            base_url=base_url,
            timeout_s=settings.timeout_s,
        )

    logger.warning(
        "Unknown AI provider '%s' requested. Defaulting to NullProvider.",
        settings.provider,
    )
    return NullProvider()
