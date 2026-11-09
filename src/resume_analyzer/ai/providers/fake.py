"""Fake LLM provider for deterministic unit and integration testing (UT-AI-*)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class FakeProvider:
    """Configurable mock LLM provider for testing without external API requests.

    Attributes:
        responses: List of queued string responses to return sequentially.
        response_map: Dictionary mapping substring in prompt to response.
        error: Optional Exception to raise on generate().
        calls: Log of all generate invocations.
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        response_map: dict[str, str] | None = None,
        error: Exception | None = None,
        callback: Callable[..., str] | None = None,
    ) -> None:
        """Initialize FakeProvider with pre-canned responses or error behaviors."""
        self.responses: list[str] = list(responses or [])
        self.response_map: dict[str, str] = dict(response_map or {})
        self.error: Exception | None = error
        self.callback: Callable[..., str] | None = callback
        self.calls: list[dict[str, Any]] = []

    def set_error(self, error: Exception | None) -> None:
        """Configure an error to raise on subsequent calls."""
        self.error = error

    def queue_response(self, response: str) -> None:
        """Add a response to the sequential return queue."""
        self.responses.append(response)

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Record the call and return queued response or raise configured error."""
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )

        if self.error is not None:
            raise self.error

        if self.callback is not None:
            return self.callback(prompt, system_prompt, temperature, max_tokens)

        # Check response map
        for key, resp in self.response_map.items():
            if key in prompt or (system_prompt and key in system_prompt):
                return resp

        # Check sequential queue
        if self.responses:
            return self.responses.pop(0)

        # Default fallback valid empty JSON
        return '{"schema_version": "1.0"}'
