"""Unit tests for documentation integrity and structure synchronization (UT-DOC-01, UT-DOC-02, NFR-17)."""

from __future__ import annotations

import re
from pathlib import Path


def test_ut_doc_01_top_level_directories_exist() -> None:
    """UT-DOC-01: Top-level project directories listed in PROJECT_STRUCTURE.md exist."""
    required_dirs = [
        "config",
        "docs",
        "src",
        "src/resume_analyzer",
        "tests",
        "samples",
    ]
    for d in required_dirs:
        p = Path(d)
        assert p.is_dir(), f"Expected directory '{d}' does not exist"


def test_ut_doc_02_all_markdown_relative_links_resolve() -> None:
    """UT-DOC-02: All relative Markdown links in README.md and docs/*.md resolve."""
    md_files = [Path("README.md")] + list(Path("docs").glob("*.md"))
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    broken = []
    for md in md_files:
        content = md.read_text(encoding="utf-8")
        for match in link_pattern.finditer(content):
            raw_target = match.group(2)
            if not raw_target or raw_target.startswith(
                ("http://", "https://", "mailto:", "#")
            ):
                continue
            target = raw_target.split("#")[0]
            if not target:
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                broken.append((str(md), raw_target, str(resolved)))

    assert len(broken) == 0, (
        f"Found {len(broken)} broken relative Markdown links: {broken}"
    )
