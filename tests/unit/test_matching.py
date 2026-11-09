"""Unit tests for matching engine, skill matcher, experience evaluator, and education evaluator (UT-MATCH-*, UT-EXPEV-*, UT-EDUEV-*)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resume_analyzer.matching.education_evaluator import evaluate_education
from resume_analyzer.matching.experience_evaluator import evaluate_experience
from resume_analyzer.matching.matching_engine import MatchingEngine
from resume_analyzer.matching.skill_matcher import match_skills
from resume_analyzer.models.candidate import Candidate, EducationEntry, Skill
from resume_analyzer.models.enums import EducationLevel, MatchType
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import SkillTaxonomy

TAXONOMY_PATH = Path("config/skills_taxonomy.json")


@pytest.fixture(scope="module")
def skill_index() -> SkillIndex:
    tax = SkillTaxonomy.from_file(TAXONOMY_PATH)
    return SkillIndex(tax)


@pytest.fixture(scope="module")
def engine(skill_index: SkillIndex) -> MatchingEngine:
    return MatchingEngine(index=skill_index)


def _make_candidate(
    skills: list[str | tuple[str, str | None]],
    total_exp: float | None = None,
    highest_edu: EducationLevel = EducationLevel.UNSPECIFIED,
    edu_entries: list[EducationEntry] | None = None,
) -> Candidate:
    skill_objs: list[Skill] = []
    for item in skills:
        if isinstance(item, tuple):
            name, can = item
            skill_objs.append(Skill(name=name, canonical_name=can))
        else:
            skill_objs.append(Skill(name=item, canonical_name=item))

    return Candidate(
        candidate_id="0123456789ab",
        source_format="txt",
        parser_version="0.1.0",
        skills=skill_objs,
        total_experience_years=total_exp,
        highest_education_level=highest_edu,
        education=edu_entries or [],
    )


def test_ut_match_01_exact_match(skill_index: SkillIndex):
    """UT-MATCH-01: Exact skill match regardless of casing or whitespace."""
    candidate = _make_candidate(["Python", "PostgreSQL", "Docker"])
    job = JobRequirements(
        job_title="Dev",
        required_skills=["python", "  POSTGRESQL  "],
    )
    matches = match_skills(candidate, job, skill_index)
    assert len(matches) == 2
    assert all(m.match_type == MatchType.EXACT for m in matches)
    assert all(m.credit == 1.0 for m in matches)
    assert all(m.similarity == 100.0 for m in matches)


def test_ut_match_02_alias_match(skill_index: SkillIndex):
    """UT-MATCH-02: Target skill resolves to candidate skill via taxonomy alias."""
    # Job requires 'AWS', candidate lists 'Amazon Web Services' (or vice versa)
    candidate = _make_candidate([("Amazon Web Services", "AWS")])
    job = JobRequirements(
        job_title="Cloud Engineer",
        required_skills=["AWS"],
    )
    matches = match_skills(candidate, job, skill_index)
    assert len(matches) == 1
    m = matches[0]
    assert m.match_type == MatchType.ALIAS
    assert m.credit == 1.0
    assert m.similarity == 100.0
    assert m.matched_candidate_skill == "Amazon Web Services"


def test_ut_match_03_fuzzy_match_above_threshold(skill_index: SkillIndex):
    """UT-MATCH-03: Fuzzy matching succeeds when candidate skill is outside taxonomy and exceeds threshold."""
    # Pandas (taxonomy canonical) vs Panda (unrecognized candidate skill, canonical=None)
    candidate = _make_candidate([("Panda", None)])
    job = JobRequirements(
        job_title="Data Analyst",
        required_skills=["Pandas"],
    )
    matches = match_skills(candidate, job, skill_index)
    assert len(matches) == 1
    m = matches[0]
    assert m.match_type == MatchType.FUZZY
    assert m.similarity >= 85.0
    assert m.credit > 0.85
    assert m.matched_candidate_skill == "Panda"


def test_ut_match_04_fuzzy_guards_reject_none(skill_index: SkillIndex):
    """UT-MATCH-04: Length < 4, first-character mismatch, confusable pair, or below threshold yield NONE."""
    # 1. Length < 4 guard: "Go" (len 2) vs "No" (len 2)
    candidate_short = _make_candidate([("No", None)])
    job_short = JobRequirements(job_title="Dev", required_skills=["Go"])
    matches_short = match_skills(candidate_short, job_short, skill_index)
    assert matches_short[0].match_type == MatchType.NONE

    # 2. First-character mismatch: "Bandas" vs "Pandas" (different initial letter)
    candidate_diff_char = _make_candidate([("Bandas", None)])
    job_diff_char = JobRequirements(job_title="Dev", required_skills=["Pandas"])
    matches_diff = match_skills(candidate_diff_char, job_diff_char, skill_index)
    assert matches_diff[0].match_type == MatchType.NONE

    # 3. Confusable pair rejection: "Java" vs "JavaScript"
    candidate_confusable = _make_candidate([("JavaScript", "JavaScript")])
    job_confusable = JobRequirements(job_title="Dev", required_skills=["Java"])
    matches_conf = match_skills(candidate_confusable, job_confusable, skill_index)
    assert matches_conf[0].match_type == MatchType.NONE


def test_ut_match_05_both_sides_known_taxonomy_skills_no_fuzzy(skill_index: SkillIndex):
    """UT-MATCH-05: If both skills are in the taxonomy, no fuzzy match is permitted even if similar."""
    # React and React Native are both valid distinct taxonomy skills
    candidate = _make_candidate([("React Native", "React Native")])
    job = JobRequirements(job_title="Frontend Dev", required_skills=["React"])
    matches = match_skills(candidate, job, skill_index)
    assert len(matches) == 1
    # Must NOT fuzzy match React to React Native because both are known taxonomy skills
    assert matches[0].match_type == MatchType.NONE


def test_ut_match_06_skill_match_invariant_and_order(skill_index: SkillIndex):
    """UT-MATCH-06: Invariant that each job skill yields exactly one match in exact job order."""
    candidate = _make_candidate(["Python", "Docker"])
    job = JobRequirements(
        job_title="Backend",
        required_skills=["PostgreSQL", "Python", "Kubernetes"],
        optional_skills=["Docker", "AWS"],
    )
    matches = match_skills(candidate, job, skill_index)
    assert len(matches) == 5
    assert [m.target for m in matches] == [
        "PostgreSQL",
        "Python",
        "Kubernetes",
        "Docker",
        "AWS",
    ]
    assert [m.is_required for m in matches] == [True, True, True, False, False]


def test_ut_match_07_worked_example_calculation(engine: MatchingEngine):
    """UT-MATCH-07: Reproduce worked example from TECHNICAL_SPECIFICATION §7.5.

    Job required: Python, SQL, Docker, AWS, Pandas
    Job optional: Git, Streamlit, Tableau
    Candidate: Python, SQL, Amazon Web Services, Panda (unrecognized), Git, Streamlit
    Candidate experience: 1.5 years (job min: 2.0 years)
    Candidate education: Bachelor (job min: Bachelor)
    Expected required_credit ≈ 0.7818, optional_credit ≈ 0.6667
    """
    candidate = _make_candidate(
        skills=[
            ("Python", "Python"),
            ("SQL", "SQL"),
            ("Amazon Web Services", "AWS"),
            ("Panda", None),  # Unrecognized -> fuzzy matches Pandas
            ("Git", "Git"),
            ("Streamlit", "Streamlit"),
        ],
        total_exp=1.5,
        highest_edu=EducationLevel.BACHELOR,
        edu_entries=[EducationEntry(degree="BS in CS", level=EducationLevel.BACHELOR)],
    )

    job = JobRequirements(
        job_title="Senior Data Analyst",
        required_skills=["Python", "SQL", "Docker", "AWS", "Pandas"],
        optional_skills=["Git", "Streamlit", "Tableau"],
        min_experience_years=2.0,
        min_education_level=EducationLevel.BACHELOR,
    )

    result = engine.match(candidate, job)

    # Check skill match types and credits
    matches_by_target = {m.target: m for m in result.skill_matches}
    assert matches_by_target["Python"].match_type == MatchType.EXACT
    assert matches_by_target["Python"].credit == 1.0

    assert matches_by_target["SQL"].match_type == MatchType.EXACT
    assert matches_by_target["SQL"].credit == 1.0

    assert matches_by_target["Docker"].match_type == MatchType.NONE
    assert matches_by_target["Docker"].credit == 0.0

    assert matches_by_target["AWS"].match_type == MatchType.ALIAS
    assert matches_by_target["AWS"].credit == 1.0

    assert matches_by_target["Pandas"].match_type == MatchType.FUZZY
    assert pytest.approx(matches_by_target["Pandas"].credit, abs=0.001) == 0.9091

    # required_credit should match 0.7818
    assert pytest.approx(result.required_credit, abs=0.0005) == 0.7818

    # Optional skills credit: Git (1.0) + Streamlit (1.0) + Tableau (0.0) / 3 = 0.6667
    assert pytest.approx(result.optional_credit, abs=0.0005) == 0.6667

    # Experience: 1.5 / 2.0 = 0.75, gap = 0.5
    assert result.experience.status == "partial"
    assert result.experience.subscore == 0.75
    assert result.experience.gap_years == 0.5

    # Education: met, 1.0
    assert result.education.status == "met"
    assert result.education.subscore == 1.0


def test_ut_expev_01_experience_not_required():
    """UT-EXPEV-01: When required_years == 0, experience is not_required with None subscore."""
    res = evaluate_experience(candidate_years=5.0, required_years=0.0)
    assert res.status == "not_required"
    assert res.subscore is None
    assert res.gap_years == 0.0


def test_ut_expev_02_experience_met_exceeded():
    """UT-EXPEV-02: When candidate experience meets or exceeds requirement, status is met."""
    res1 = evaluate_experience(candidate_years=3.0, required_years=3.0)
    assert res1.status == "met"
    assert res1.subscore == 1.0
    assert res1.gap_years == 0.0

    res2 = evaluate_experience(candidate_years=6.0, required_years=3.0)
    assert res2.status == "met"
    assert res2.subscore == 1.0
    assert res2.gap_years == 0.0


def test_ut_expev_03_experience_partial_and_unmet():
    """UT-EXPEV-03: Partial experience produces candidate/required subscore; 0 experience is unmet."""
    res_partial = evaluate_experience(candidate_years=2.0, required_years=4.0)
    assert res_partial.status == "partial"
    assert res_partial.subscore == 0.5
    assert res_partial.gap_years == 2.0

    res_unmet = evaluate_experience(candidate_years=0.0, required_years=4.0)
    assert res_unmet.status == "unmet"
    assert res_unmet.subscore == 0.0
    assert res_unmet.gap_years == 4.0


def test_ut_expev_04_experience_unknown():
    """UT-EXPEV-04: When candidate experience is None, status is unknown with None subscore."""
    res = evaluate_experience(candidate_years=None, required_years=3.0)
    assert res.status == "unknown"
    assert res.subscore is None
    assert res.gap_years is None


def test_ut_eduev_01_education_not_required():
    """UT-EDUEV-01: Unspecified requirement results in not_required status and None subscore."""
    cand = _make_candidate([], highest_edu=EducationLevel.BACHELOR)
    job = JobRequirements(
        job_title="Dev",
        required_skills=["Python"],
        min_education_level=EducationLevel.UNSPECIFIED,
    )
    res = evaluate_education(cand, job)
    assert res.status == "not_required"
    assert res.subscore is None


def test_ut_eduev_02_education_met():
    """UT-EDUEV-02: Candidate meets or exceeds education level, achieving 1.0 subscore."""
    cand = _make_candidate([], highest_edu=EducationLevel.MASTER)
    job = JobRequirements(
        job_title="Dev",
        required_skills=["Python"],
        min_education_level=EducationLevel.BACHELOR,
    )
    res = evaluate_education(cand, job)
    assert res.status == "met"
    assert res.subscore == 1.0


def test_ut_eduev_03_education_below_graduated_penalty():
    """UT-EDUEV-03: Candidate 1 level below gets 0.5 subscore; >=2 levels below gets 0.0."""
    # 1 level below: Diploma (level 2) vs Bachelor (level 3) -> 0.5 subscore
    cand_1_below = _make_candidate([], highest_edu=EducationLevel.DIPLOMA)
    job_bachelor = JobRequirements(
        job_title="Dev",
        required_skills=["Python"],
        min_education_level=EducationLevel.BACHELOR,
    )
    res_1 = evaluate_education(cand_1_below, job_bachelor)
    assert res_1.status == "below"
    assert res_1.subscore == 0.5

    # 2 levels below: High School (level 1) vs Bachelor (level 3) -> 0.0 subscore
    cand_2_below = _make_candidate([], highest_edu=EducationLevel.HIGH_SCHOOL)
    res_2 = evaluate_education(cand_2_below, job_bachelor)
    assert res_2.status == "below"
    assert res_2.subscore == 0.0


def test_ut_eduev_04_preferred_fields_cap():
    """UT-EDUEV-04: Subscore is capped at 0.75 when candidate has a degree in an unrelated field."""
    # Matching field: Computer Science
    cand_matched = _make_candidate(
        [],
        highest_edu=EducationLevel.BACHELOR,
        edu_entries=[
            EducationEntry(
                degree="BS",
                level=EducationLevel.BACHELOR,
                field_of_study="Computer Science",
            )
        ],
    )
    job_pref = JobRequirements(
        job_title="Dev",
        required_skills=["Python"],
        min_education_level=EducationLevel.BACHELOR,
        preferred_fields=["Computer Science", "Software Engineering"],
    )
    res_matched = evaluate_education(cand_matched, job_pref)
    assert res_matched.status == "met"
    assert res_matched.field_match is True
    assert res_matched.subscore == 1.0

    # Unmatched field: History
    cand_unmatched = _make_candidate(
        [],
        highest_edu=EducationLevel.BACHELOR,
        edu_entries=[
            EducationEntry(
                degree="BA", level=EducationLevel.BACHELOR, field_of_study="Art History"
            )
        ],
    )
    res_unmatched = evaluate_education(cand_unmatched, job_pref)
    assert res_unmatched.status == "met"
    assert res_unmatched.field_match is False
    assert res_unmatched.subscore == 0.75  # Capped at 0.75
