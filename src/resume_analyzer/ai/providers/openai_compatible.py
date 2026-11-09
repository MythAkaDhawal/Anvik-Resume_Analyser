"""OpenAI-compatible HTTP provider implementation (DR-AI-2, §8.4)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from resume_analyzer.exceptions import AIProviderUnavailableError, AIRateLimitError

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible completions endpoints."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        """Initialize OpenAICompatibleProvider."""
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout_s = timeout_s

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Execute chat completion via /chat/completions endpoint."""
        url = f"{self.base_url}/chat/completions"

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as response:  # nosec: B310
                resp_data = json.loads(response.read().decode("utf-8"))
                choices = resp_data.get("choices", [])
                if not choices:
                    raise AIProviderUnavailableError(
                        "OpenAI-compatible endpoint returned empty choices list.",
                        details={"provider": "openai_compatible"},
                    )
                content = choices[0].get("message", {}).get("content")
                if content is None:
                    raise AIProviderUnavailableError(
                        "OpenAI-compatible endpoint choice message has no content.",
                        details={"provider": "openai_compatible"},
                    )
                return str(content)

        except urllib.error.HTTPError as err:
            if err.code == 429:
                raise AIRateLimitError(
                    "OpenAI-compatible API rate limit exceeded.",
                    details={"provider": "openai_compatible", "retry_after_s": 60.0},
                ) from err
            raise AIProviderUnavailableError(
                f"OpenAI-compatible endpoint returned HTTP {err.code}: {err.reason}",
                details={"provider": "openai_compatible"},
            ) from err
        except Exception as err:
            raise AIProviderUnavailableError(
                f"Failed to communicate with OpenAI-compatible endpoint: {err}",
                details={"provider": "openai_compatible"},
            ) from err
