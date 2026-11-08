"""Provider protocol and base abstraction for generative AI providers (DR-AI-2)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for provider-agnostic LLM completion backends.

    All concrete providers (Gemini, Ollama, OpenAI-compatible, Null, Fake)
    implement this contract. The deterministic application core must never
    depend on external AI APIs directly.
    """

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Execute a completion request and return the raw response text.

        Args:
            prompt: User-facing prompt containing sanitized data and instructions.
            system_prompt: Optional system persona instructions.
            temperature: Sampling temperature (default 0.1 for high determinism).
            max_tokens: Maximum completion tokens to generate.

        Returns:
            Raw string response (expected to contain JSON).

        Raises:
            ResumeAnalyzerError: On connection timeout, rate limit, or service error.
        """
        ...
