"""Unit tests for experience parsing, date extraction, and interval merging (UT-EXP-01..06)."""

from __future__ import annotations

from datetime import date

from resume_analyzer.models.candidate import ExperienceEntry
from resume_analyzer.models.enums import Provenance
from resume_analyzer.parsing.experience_parser import (
    parse_date_fragment,
    parse_experience,
    total_experience_years,
)

REF_DATE = date(2024, 6, 1)


def test_ut_exp_01_date_formats():
    """UT-EXP-01: Support varied date formats (Month YYYY, MM/YYYY, YYYY)."""
    d1, is_curr1 = parse_date_fragment("Jan 2020", REF_DATE)
    assert d1 == date(2020, 1, 1)
    assert not is_curr1

    d2, is_curr2 = parse_date_fragment("03/2021", REF_DATE)
    assert d2 == date(2021, 3, 1)
    assert not is_curr2

    d3, is_curr3 = parse_date_fragment("2018", REF_DATE)
    assert d3 == date(2018, 7, 1)
    assert not is_curr3


def test_ut_exp_02_present_resolution():
    """UT-EXP-02: 'Present' keyword resolves to reference date with is_current=True and stored end=None."""
    text = "Senior Software Engineer at Acme Corp\nMarch 2022 - Present"
    entries, warnings = parse_experience(text, REF_DATE)
    assert len(entries) == 1
    e = entries[0]
    assert e.job_title == "Senior Software Engineer"
    assert e.company == "Acme Corp"
    assert e.start == date(2022, 3, 1)
    assert e.end is None
    assert e.is_current is True
    assert e.duration_months == (2024 - 2022) * 12 + (6 - 3)  # 27 months


def test_ut_exp_03_interval_merging():
    """UT-EXP-03: Overlapping intervals merge into accurate non-double-counted total years."""
    # Role A: Jan 2020 - Dec 2021 (24 months)
    # Role B: Jun 2021 - Jun 2022 (Overlaps Role A by 6 months; extends it by 6 months -> total Jan 2020 to Jun 2022 = 29 months = 2.4 years)
    entries = [
        ExperienceEntry(
            job_title="Software Engineer",
            company="Company A",
            start=date(2020, 1, 1),
            end=date(2021, 12, 1),
            is_current=False,
            duration_months=23,
            provenance=Provenance.EXTRACTED_RULE,
        ),
        ExperienceEntry(
            job_title="Consultant",
            company="Company B",
            start=date(2021, 6, 1),
            end=date(2022, 6, 1),
            is_current=False,
            duration_months=12,
            provenance=Provenance.EXTRACTED_RULE,
        ),
    ]
    years = total_experience_years(entries, REF_DATE)
    # Jan 2020 to Jun 2022 is 29 months -> 29/12 = 2.4166 -> 2.4 years
    assert years == 2.4


def test_ut_exp_04_invalid_and_future_dates():
    """UT-EXP-04: Start date in future or end before start triggers warning."""
    # Future start
    text_future = "Architect at Nova\nJan 2030 - Dec 2031"
    entries_f, warnings_f = parse_experience(text_future, REF_DATE)
    assert any(w.code == "FUTURE_DATE" for w in warnings_f)

    # Inverted range
    text_inverted = "Developer at Nova\nJan 2022 - Jan 2020"
    entries_i, warnings_i = parse_experience(text_inverted, REF_DATE)
    assert any(w.code == "INVALID_DATE_RANGE" for w in warnings_i)


def test_ut_exp_05_missing_or_unparseable_dates():
    """UT-EXP-05: Missing experience dates handle gracefully without crash."""
    text = "Developer at TechCorp\nBuilt web applications using Python."
    entries, warnings = parse_experience(text, REF_DATE)
    assert len(entries) == 0
    assert any(w.code == "NO_EXPERIENCE_DATES" for w in warnings)


def test_ut_exp_06_intern_handling():
    """UT-EXP-06: Intern roles can be selectively excluded or included."""
    entries = [
        ExperienceEntry(
            job_title="Software Engineer Intern",
            company="Acme",
            start=date(2022, 1, 1),
            end=date(2022, 6, 1),
            is_current=False,
            duration_months=5,
            provenance=Provenance.EXTRACTED_RULE,
        ),
        ExperienceEntry(
            job_title="Software Engineer",
            company="Acme",
            start=date(2022, 7, 1),
            end=date(2023, 7, 1),
            is_current=False,
            duration_months=12,
            provenance=Provenance.EXTRACTED_RULE,
        ),
    ]
    with_intern = total_experience_years(entries, REF_DATE, count_internships=True)
    without_intern = total_experience_years(entries, REF_DATE, count_internships=False)
    assert with_intern is not None and without_intern is not None
    assert with_intern > without_intern
