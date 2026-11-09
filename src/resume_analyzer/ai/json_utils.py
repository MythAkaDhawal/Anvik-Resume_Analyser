"""Robust JSON parsing for LLM completion responses (AI_PROMPTS §2.5)."""

from __future__ import annotations

import json
import re
from typing import Any

from resume_analyzer.exceptions import AIServiceError

# Markdown fence regex matching ```json ... ``` or ``` ... ```
JSON_FENCE_REGEX = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def parse_json_response(raw_text: str) -> dict[str, Any] | list[Any]:
    """Extract and parse JSON data from raw model completion string.

    Tolerates markdown code fences, leading conversational prose, and trailing notes.
    Guaranteed never to invoke eval() or exec().

    Args:
        raw_text: Raw string returned by an LLM provider.

    Returns:
        Parsed JSON dictionary or list.

    Raises:
        AIServiceError: If valid JSON cannot be extracted and parsed.
    """
    if not raw_text or not raw_text.strip():
        raise AIServiceError("Model returned empty or whitespace-only response.")

    text = raw_text.strip()

    # 1. Attempt extraction from markdown code fences
    fence_match = JSON_FENCE_REGEX.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # 2. Try direct parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Locate innermost/outermost brackets if prose surrounds JSON
    start_brace = text.find("{")
    end_brace = text.rfind("}")
    start_bracket = text.find("[")
    end_bracket = text.rfind("]")

    candidates: list[str] = []
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        candidates.append(text[start_brace : end_brace + 1])
    if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
        candidates.append(text[start_bracket : end_bracket + 1])

    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue

    raise AIServiceError("Failed to extract valid JSON payload from model response.")
