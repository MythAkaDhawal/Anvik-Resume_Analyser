"""Unit tests for education parsing and qualification attainment mapping (UT-EDU-01..04)."""

from __future__ import annotations

from resume_analyzer.models.enums import EducationLevel
from resume_analyzer.parsing.education_parser import parse_education


def test_ut_edu_01_degree_level_mapping():
    """UT-EDU-01: Map varied degree terminology to standardized EducationLevel enum values."""
    cases = [
        ("Ph.D. in Computer Science", EducationLevel.DOCTORATE),
        ("Master of Science in Software Engineering", EducationLevel.MASTER),
        ("Bachelor of Technology in Information Technology", EducationLevel.BACHELOR),
        ("Associate Degree in Web Development", EducationLevel.DIPLOMA),
        ("High School Diploma", EducationLevel.HIGH_SCHOOL),
    ]
    for text, expected_level in cases:
        entries, highest, warnings = parse_education(text)
        assert len(entries) >= 1
        assert entries[0].level == expected_level


def test_ut_edu_02_case_sensitive_short_abbreviations():
    """UT-EDU-02: Short abbreviations like 'BE' or 'MS' match degree, while common words do not."""
    # Matches BE (Bachelor of Engineering)
    entry_be, highest_be, _ = parse_education("BE in Electrical Engineering, MIT")
    assert highest_be == EducationLevel.BACHELOR

    # Matches MS (Master of Science)
    entry_ms, highest_ms, _ = parse_education("MS in Data Science, Stanford University")
    assert highest_ms == EducationLevel.MASTER

    # Lowercase 'to be' should not map to Bachelor
    entry_word, highest_word, warnings = parse_education(
        "Aspiring to be an exceptional software leader"
    )
    assert highest_word == EducationLevel.UNSPECIFIED
    assert any(w.code == "UNKNOWN_DEGREE" for w in warnings)


def test_ut_edu_03_field_of_study_and_institution():
    """UT-EDU-03: Extract academic major and educational institution from education lines."""
    text = (
        "Bachelor of Science in Computer Science\n"
        "University of California, Berkeley\n\n"
        "Master of Science in Artificial Intelligence\n"
        "Carnegie Mellon University"
    )
    entries, highest, warnings = parse_education(text)
    assert len(entries) == 2
    assert "Computer Science" in (entries[0].field_of_study or "")
    assert "Berkeley" in (entries[0].institution or "")
    assert "Artificial Intelligence" in (entries[1].field_of_study or "")
    assert "Carnegie Mellon" in (entries[1].institution or "")


def test_ut_edu_04_highest_education_level():
    """UT-EDU-04: Accurately identifies highest qualification level among multiple degrees."""
    text = (
        "B.S. in Mathematics, University of Michigan\n"
        "Ph.D. in Applied Mathematics, Princeton University"
    )
    entries, highest, warnings = parse_education(text)
    assert highest == EducationLevel.DOCTORATE

    empty_entries, highest_empty, warnings_empty = parse_education("")
    assert highest_empty == EducationLevel.UNSPECIFIED
    assert any(w.code == "NO_EDUCATION" for w in warnings_empty)
