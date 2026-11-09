"""Prompt template rendering and version registry (AI_PROMPTS §1-§7, UT-AI-01)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from resume_analyzer.ai.sanitizer import generate_nonce

PROMPT_TEMPLATES_DIR = Path(__file__).parent / "prompt_templates"

PROMPT_VERSIONS: dict[str, str] = {
    "p1_extract": "1.0.0",
    "p2_categorize": "1.0.0",
    "p3_explain": "1.0.0",
    "p4_recommend": "1.0.0",
    "p5_interview": "1.0.0",
}

_jinja_env = Environment(
    loader=FileSystemLoader(str(PROMPT_TEMPLATES_DIR)),
    autoescape=False,  # nosec: B701
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(
    prompt_id: str,
    context: dict[str, Any],
    nonce: str | None = None,
) -> tuple[str, str, str]:
    """Render system and user prompt strings with an isolated nonce.

    Args:
        prompt_id: Unique prompt identifier ('p1_extract', 'p2_categorize', etc.).
        context: Template rendering parameters.
        nonce: Optional nonce; if None, generates a fresh random 16-hex nonce.

    Returns:
        Tuple of (system_prompt, user_prompt, active_nonce).
    """
    if prompt_id not in PROMPT_VERSIONS:
        raise KeyError(
            f"Unknown prompt_id '{prompt_id}'. Available: {list(PROMPT_VERSIONS.keys())}"
        )

    active_nonce = nonce or generate_nonce()
    ctx = dict(context)
    ctx["nonce"] = active_nonce

    template = _jinja_env.get_template(f"{prompt_id}.j2")
    rendered = template.render(**ctx)

    # Split into SYSTEM and USER blocks
    parts = rendered.split("USER:\n")
    if len(parts) == 2:
        system_part = parts[0].replace("SYSTEM:\n", "").strip()
        user_part = parts[1].strip()
    else:
        system_part = ""
        user_part = rendered.strip()

    return system_part, user_part, active_nonce
