"""Generative AI integration and provider abstraction layer."""

from __future__ import annotations

from resume_analyzer.ai.ai_service import AIService
from resume_analyzer.ai.provider_base import LLMProvider
from resume_analyzer.ai.provider_factory import get_provider
from resume_analyzer.ai.providers.fake import FakeProvider
from resume_analyzer.ai.providers.gemini import GeminiProvider
from resume_analyzer.ai.providers.null import NullProvider
from resume_analyzer.ai.providers.ollama import OllamaProvider
from resume_analyzer.ai.providers.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "AIService",
    "FakeProvider",
    "GeminiProvider",
    "LLMProvider",
    "NullProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "get_provider",
]
