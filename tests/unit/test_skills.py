"""Unit tests for skill taxonomy, normalization, and extraction (UT-SKILL-01..08)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resume_analyzer.models.enums import Provenance
from resume_analyzer.parsing.skills_extractor import extract_skills
from resume_analyzer.skills.normalizer import normalize_skill
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import SkillTaxonomy

TAXONOMY_PATH = Path("config/skills_taxonomy.json")


@pytest.fixture(scope="module")
def skill_index() -> SkillIndex:
    taxonomy = SkillTaxonomy.from_file(TAXONOMY_PATH)
    return SkillIndex(taxonomy)


def test_ut_skill_01_taxonomy_integrity(skill_index: SkillIndex):
    """UT-SKILL-01: Verify skills taxonomy structure, categories, and alias uniqueness."""
    tax = skill_index.taxonomy
    assert len(tax.skills) >= 300
    assert len(tax.categories) == 9
    expected_categories = {
        "Programming Languages",
        "Frameworks & Libraries",
        "Databases",
        "Cloud & DevOps",
        "Data Science & ML",
        "Tools & Platforms",
        "Soft Skills",
        "Domain Knowledge",
        "Other",
    }
    assert set(tax.categories) == expected_categories
    assert len(tax.confusable_pairs) > 0


def test_ut_skill_02_normalization_preserved_symbols():
    """UT-SKILL-02: Normalize handles C++, C#, .NET, Node.js, parentheticals, and punctuation."""
    assert normalize_skill("C++") == "c++"
    assert normalize_skill("c#") == "c#"
    assert normalize_skill(".NET Core") == ".net core"
    assert normalize_skill("Node.js") == "node.js"
    assert normalize_skill("Python (3.11, advanced)") == "python"
    assert normalize_skill("   Docker; ") == "docker"
    assert normalize_skill("CI/CD") == "ci/cd"


def test_ut_skill_03_exact_skill_match_from_section(skill_index: SkillIndex):
    """UT-SKILL-03: Exact skill matches extracted from skills section with canonical names."""
    sections = {"skills": "Python, Docker, Kubernetes, PostgreSQL"}
    skills, warnings = extract_skills(sections, skill_index)
    canonical_names = {s.canonical_name for s in skills}
    assert "Python" in canonical_names
    assert "Docker" in canonical_names
    assert "Kubernetes" in canonical_names
    assert "PostgreSQL" in canonical_names
    assert all(s.provenance == Provenance.EXTRACTED_RULE for s in skills)


def test_ut_skill_04_alias_resolution(skill_index: SkillIndex):
    """UT-SKILL-04: Skill aliases resolve to canonical names."""
    sections = {"skills": "k8s, postgres, reactjs, aws, tf"}
    skills, warnings = extract_skills(sections, skill_index)
    canonical_names = {s.canonical_name for s in skills}
    assert "Kubernetes" in canonical_names
    assert "PostgreSQL" in canonical_names
    assert "React" in canonical_names
    assert "AWS" in canonical_names
    assert "TensorFlow" in canonical_names


def test_ut_skill_05_ngram_body_scanning(skill_index: SkillIndex):
    """UT-SKILL-05: Multi-word skills scanned accurately from experience and summary body text."""
    sections = {
        "summary": "Specialist in Natural Language Processing and Machine Learning.",
        "experience": "Architected distributed systems using Apache Spark and Apache Kafka.",
    }
    skills, warnings = extract_skills(sections, skill_index)
    canonical_names = {s.canonical_name for s in skills}
    assert "Natural Language Processing" in canonical_names
    assert "Machine Learning" in canonical_names
    assert "Apache Spark" in canonical_names
    assert "Apache Kafka" in canonical_names


def test_ut_skill_06_confusable_disambiguation(skill_index: SkillIndex):
    """UT-SKILL-06: Distinct skills with overlapping names (Java vs JavaScript) are distinguished."""
    sections = {"skills": "JavaScript, TypeScript"}
    skills, warnings = extract_skills(sections, skill_index)
    canonical_names = {s.canonical_name for s in skills}
    assert "JavaScript" in canonical_names
    assert "Java" not in canonical_names


def test_ut_skill_07_no_fabrication(skill_index: SkillIndex):
    """UT-SKILL-07: Unmentioned skills are never fabricated."""
    sections = {"skills": "Python, FastApi, Redis"}
    skills, warnings = extract_skills(sections, skill_index)
    canonical_names = {s.canonical_name for s in skills}
    assert "Rust" not in canonical_names
    assert "Go" not in canonical_names
    assert "Kubernetes" not in canonical_names


def test_ut_skill_08_skill_stuffing_cap(skill_index: SkillIndex):
    """UT-SKILL-08: Extremely long skill lists are capped at 300 with SKILL_LIST_TRUNCATED warning."""
    # Fabricate 350 distinct skills
    synthetic_skills = [f"SkillNumber{i}" for i in range(350)]
    sections = {"skills": ", ".join(synthetic_skills)}
    skills, warnings = extract_skills(sections, skill_index)
    assert len(skills) <= 300
    assert any(w.code == "SKILL_LIST_TRUNCATED" for w in warnings)
