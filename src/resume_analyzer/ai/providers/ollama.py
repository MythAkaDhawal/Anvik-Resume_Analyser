"""Local Ollama provider implementation (DR-AI-2, §8.3)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from resume_analyzer.exceptions import AIProviderUnavailableError

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Provider for locally running Ollama instances."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout_s: float = 60.0,
    ) -> None:
        """Initialize OllamaProvider."""
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Execute completion via Ollama /api/generate endpoint."""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

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
                response_text = resp_data.get("response")
                if response_text is None:
                    raise AIProviderUnavailableError(
                        "Ollama response missing 'response' text field.",
                        details={"provider": "ollama"},
                    )
                return str(response_text)

        except Exception as err:
            raise AIProviderUnavailableError(
                f"Failed to communicate with local Ollama service at {self.base_url}: {err}",
                details={"provider": "ollama"},
            ) from err
