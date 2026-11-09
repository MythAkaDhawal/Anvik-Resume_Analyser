"""Google Gemini API provider implementation (DR-AI-2, §8.2)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from resume_analyzer.exceptions import AIProviderUnavailableError, AIRateLimitError

logger = logging.getLogger(__name__)


class GeminiProvider:
    """Provider for Google Gemini models via REST API."""

    def __init__(
        self,
        model: str = "gemini-1.5-flash",
        api_key: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        """Initialize GeminiProvider with model and API credentials from environment."""
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.timeout_s = timeout_s

        if not self.api_key:
            raise AIProviderUnavailableError(
                "GEMINI_API_KEY environment variable is not set.",
                details={"provider": "gemini"},
            )

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Execute completion via Gemini REST API."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }

        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as response:  # nosec: B310
                resp_data = json.loads(response.read().decode("utf-8"))
                candidates = resp_data.get("candidates", [])
                if not candidates:
                    raise AIProviderUnavailableError(
                        "Gemini returned empty candidate list.",
                        details={"provider": "gemini"},
                    )
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts or "text" not in parts[0]:
                    raise AIProviderUnavailableError(
                        "Gemini response candidate has no text part.",
                        details={"provider": "gemini"},
                    )
                return str(parts[0]["text"])

        except urllib.error.HTTPError as err:
            if err.code == 429:
                raise AIRateLimitError(
                    "Gemini API rate limit exceeded.",
                    details={"provider": "gemini", "retry_after_s": 60.0},
                ) from err
            raise AIProviderUnavailableError(
                f"Gemini API returned HTTP {err.code}: {err.reason}",
                details={"provider": "gemini"},
            ) from err
        except Exception as err:
            raise AIProviderUnavailableError(
                f"Failed to communicate with Gemini API: {err}",
                details={"provider": "gemini"},
            ) from err
