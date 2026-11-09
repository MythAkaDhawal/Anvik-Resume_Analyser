"""Unit tests for master ResumeParser orchestrator (UT-PARSE-01..06)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from resume_analyzer.config.settings import get_settings
from resume_analyzer.exceptions import EmptyResumeError
from resume_analyzer.ingestion.file_loader import LoadedResume, load_resume
from resume_analyzer.models.candidate import Candidate
from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.parsing.resume_parser import ResumeParser
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import SkillTaxonomy

TAXONOMY_PATH = Path("config/skills_taxonomy.json")
REF_DATE = date(2024, 6, 1)


@pytest.fixture(scope="module")
def parser() -> ResumeParser:
    tax = SkillTaxonomy.from_file(TAXONOMY_PATH)
    index = SkillIndex(tax)
    return ResumeParser(index)


def _make_loaded_resume(text: str, filename: str = "test_resume.txt") -> LoadedResume:
    content = text.encode("utf-8")
    settings = get_settings()
    return load_resume(filename, content, settings=settings.files)


def test_ut_parse_01_complete_resume_end_to_end(parser: ResumeParser):
    """UT-PARSE-01: End-to-end parsing of complete resume produces valid Candidate matching schema."""
    text = (
        "Sarah Jenkins\n"
        "sarah.jenkins@example.com\n\n"
        "SUMMARY\n"
        "Full-stack engineer with 5 years experience designing microservices.\n\n"
        "SKILLS\n"
        "Python, FastApi, PostgreSQL, Docker, AWS\n\n"
        "EXPERIENCE\n"
        "Senior Developer at Acme Tech\n"
        "Jan 2021 - Present\n"
        "- Built REST APIs using FastApi and PostgreSQL.\n\n"
        "Software Engineer at Beta Solutions\n"
        "Jan 2019 - Dec 2020\n"
        "- Developed backend microservices with Python and Docker.\n\n"
        "EDUCATION\n"
        "Bachelor of Science in Computer Science\n"
        "University of California, Davis\n"
    )
    loaded = _make_loaded_resume(text)
    candidate = parser.parse(loaded, reference_date=REF_DATE)

    assert isinstance(candidate, Candidate)
    assert candidate.name == "Sarah Jenkins"
    assert candidate.email == "sarah.jenkins@example.com"
    canonical_skills = {s.canonical_name for s in candidate.skills}
    assert "Python" in canonical_skills
    assert "FastAPI" in canonical_skills
    assert "PostgreSQL" in canonical_skills
    assert "Docker" in canonical_skills
    assert "AWS" in canonical_skills
    assert len(candidate.experience) == 2
    assert candidate.highest_education_level == EducationLevel.BACHELOR
    assert candidate.total_experience_years is not None
    assert candidate.total_experience_years >= 5.0


def test_ut_parse_02_missing_sections(parser: ResumeParser):
    """UT-PARSE-02: Parsing resumes with missing sections degrades gracefully without exceptions."""
    text = "Alex Hunter\nalex.hunter@example.com\n\nPython, Docker, SQL"
    loaded = _make_loaded_resume(text)
    candidate = parser.parse(loaded, reference_date=REF_DATE)

    assert candidate.name == "Alex Hunter"
    assert candidate.email == "alex.hunter@example.com"
    assert len(candidate.skills) >= 2
    assert len(candidate.experience) == 0
    assert candidate.highest_education_level == EducationLevel.UNSPECIFIED
    assert any(w.code == "NO_EDUCATION" for w in candidate.parse_warnings)


def test_ut_parse_03_low_text_quality(parser: ResumeParser):
    """UT-PARSE-03: Garbled or highly non-alphanumeric text triggers LOW_TEXT_QUALITY warning."""
    text = "@@@%%% $$$$ #### ^^^^ &&&& **** (((( )))) ____ ++++ ==== |||| ~~~~ ````"
    loaded = _make_loaded_resume(text)
    candidate = parser.parse(loaded, reference_date=REF_DATE)
    assert any(w.code == "LOW_TEXT_QUALITY" for w in candidate.parse_warnings)


def test_ut_parse_04_empty_resume_raises_error():
    """UT-PARSE-04: Empty resume text is caught during load_resume, raising EmptyResumeError."""
    content = b"   \n\t  "
    settings = get_settings()
    with pytest.raises(EmptyResumeError):
        load_resume("empty.txt", content, settings=settings.files)


def test_ut_parse_05_no_fabrication(parser: ResumeParser):
    """UT-PARSE-05: Strict no-fabrication check; all extracted skills appear in raw text."""
    text = (
        "Devon Vance\n"
        "devon@example.org\n\n"
        "SKILLS\n"
        "Rust, WebAssembly\n\n"
        "EXPERIENCE\n"
        "Systems Engineer at RustWorks\n"
        "Jan 2022 - Dec 2023\n"
    )
    loaded = _make_loaded_resume(text)
    candidate = parser.parse(loaded, reference_date=REF_DATE)

    # All extracted skills must be grounded in the raw text
    for skill in candidate.skills:
        assert skill.name.lower() in text.lower() or (
            skill.canonical_name and skill.canonical_name.lower() in text.lower()
        )


def test_ut_parse_06_fairness_protected_attributes_absence():
    """UT-PARSE-06: Verify Candidate model strictly excludes demographic and protected attributes."""
    forbidden_fields = {
        "date_of_birth",
        "dob",
        "age",
        "gender",
        "sex",
        "marital_status",
        "nationality",
        "race",
        "ethnicity",
        "religion",
        "photo",
        "street_address",
        "phone",
        "phone_number",
        "graduation_year",
        "grad_year",
    }
    candidate_fields = set(Candidate.model_fields.keys())
    intersection = forbidden_fields.intersection(candidate_fields)
    assert not intersection, (
        f"Candidate model improperly contains protected attributes: {intersection}"
    )
