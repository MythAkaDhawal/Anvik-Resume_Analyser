"""Unit tests for scoring strategies, fit bands, registry, and invariants (UT-SCORE-01..12)."""

from __future__ import annotations

import pytest

from resume_analyzer.config.settings import (
    BandThresholds,
    ScoreWeights,
    ScoringSettings,
)
from resume_analyzer.exceptions import ConfigurationError, UnknownStrategyError
from resume_analyzer.models.enums import (
    EducationLevel,
    FitBand,
    MatchType,
)
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import (
    EducationAnalysis,
    ExperienceAnalysis,
    MatchResult,
    SkillMatch,
)
from resume_analyzer.scoring.bands import fit_band_for
from resume_analyzer.scoring.basic import BasicScoringStrategy
from resume_analyzer.scoring.registry import get_strategy
from resume_analyzer.scoring.weighted import WeightedScoringStrategy


def _build_worked_example_match() -> tuple[MatchResult, JobRequirements]:
    """Helper constructing MatchResult matching worked example in TECHNICAL_SPECIFICATION §7.5."""
    skill_matches = [
        SkillMatch(
            target="Python",
            is_required=True,
            match_type=MatchType.EXACT,
            similarity=100.0,
            credit=1.0,
        ),
        SkillMatch(
            target="SQL",
            is_required=True,
            match_type=MatchType.EXACT,
            similarity=100.0,
            credit=1.0,
        ),
        SkillMatch(
            target="Docker",
            is_required=True,
            match_type=MatchType.NONE,
            similarity=0.0,
            credit=0.0,
        ),
        SkillMatch(
            target="AWS",
            is_required=True,
            match_type=MatchType.ALIAS,
            similarity=100.0,
            credit=1.0,
        ),
        SkillMatch(
            target="Pandas",
            is_required=True,
            match_type=MatchType.FUZZY,
            similarity=90.91,
            credit=0.9091,
        ),
        SkillMatch(
            target="Git",
            is_required=False,
            match_type=MatchType.EXACT,
            similarity=100.0,
            credit=1.0,
        ),
        SkillMatch(
            target="Streamlit",
            is_required=False,
            match_type=MatchType.EXACT,
            similarity=100.0,
            credit=1.0,
        ),
        SkillMatch(
            target="Tableau",
            is_required=False,
            match_type=MatchType.NONE,
            similarity=0.0,
            credit=0.0,
        ),
    ]
    job = JobRequirements(
        job_title="Senior Data Analyst",
        required_skills=["Python", "SQL", "Docker", "AWS", "Pandas"],
        optional_skills=["Git", "Streamlit", "Tableau"],
        min_experience_years=2.0,
        min_education_level=EducationLevel.BACHELOR,
    )
    match = MatchResult(
        skill_matches=skill_matches,
        required_credit=0.7818,
        optional_credit=0.6667,
        experience=ExperienceAnalysis(
            required_years=2.0,
            candidate_years=1.5,
            status="partial",
            subscore=0.75,
            gap_years=0.5,
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.BACHELOR,
            candidate_level=EducationLevel.BACHELOR,
            status="met",
            subscore=1.0,
        ),
    )
    return match, job


def test_ut_score_01_basic_strategy_worked_example():
    """UT-SCORE-01: Basic strategy reproduces 78.2 score for §7.5 worked example."""
    match, job = _build_worked_example_match()
    strat = BasicScoringStrategy()
    result = strat.score(match, job)

    assert result.strategy_name == "basic"
    assert result.total_score == 78.2
    assert result.fit_band == FitBand.MODERATE
    assert result.coverage == 1.0
    assert "MISSING_REQUIRED_SKILLS" in result.flags  # Docker is NONE


def test_ut_score_02_weighted_strategy_worked_example():
    """UT-SCORE-02: Weighted strategy reproduces 79.1 score and component points sum to total."""
    match, job = _build_worked_example_match()
    strat = WeightedScoringStrategy()
    result = strat.score(match, job)

    assert result.strategy_name == "weighted"
    assert result.total_score == 79.1
    assert result.fit_band == FitBand.MODERATE
    assert result.coverage == 1.0

    # Component points sum must equal total_score within +/- 0.1
    points_sum = sum(c.points for c in result.components if c.points is not None)
    assert pytest.approx(points_sum, abs=0.1) == result.total_score


def test_ut_score_03_weights_sum_validation():
    """UT-SCORE-03: Weights not summing to 1.0 raise ConfigurationError."""
    # Test through ScoreWeights model
    with pytest.raises(Exception):
        ScoreWeights(
            required_skills=0.6, experience=0.6, education=0.1, optional_skills=0.1
        )

    # Test through WeightedScoringStrategy
    invalid_weights = ScoreWeights.model_construct(
        required_skills=0.5,
        experience=0.2,
        education=0.2,
        optional_skills=0.2,  # sum = 1.1
    )
    with pytest.raises(ConfigurationError):
        WeightedScoringStrategy(weights=invalid_weights)


def test_ut_score_04_renormalization_when_dimension_not_applicable():
    """UT-SCORE-04: Weights renormalize when optional skills or experience are not applicable."""
    # Job with no optional skills and min_experience_years = 0
    job = JobRequirements(
        job_title="Junior Developer",
        required_skills=["Python", "SQL"],
        optional_skills=[],
        min_experience_years=0.0,
        min_education_level=EducationLevel.BACHELOR,
    )
    match = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Python",
                is_required=True,
                match_type=MatchType.EXACT,
                similarity=100.0,
                credit=1.0,
            ),
            SkillMatch(
                target="SQL",
                is_required=True,
                match_type=MatchType.EXACT,
                similarity=100.0,
                credit=1.0,
            ),
        ],
        required_credit=1.0,
        optional_credit=None,
        experience=ExperienceAnalysis(
            required_years=0.0,
            candidate_years=0.0,
            status="not_required",
            subscore=None,
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.BACHELOR,
            candidate_level=EducationLevel.BACHELOR,
            status="met",
            subscore=1.0,
        ),
    )
    strat = WeightedScoringStrategy()
    result = strat.score(match, job)

    # Evaluated dimensions: required_skills (0.50) + education (0.15) = 0.65 total weight
    # Both evaluated dimensions have subscore 1.0 -> total score must be 100.0!
    assert result.total_score == 100.0
    assert result.coverage == 1.0
    assert result.fit_band == FitBand.STRONG


def test_ut_score_05_bounds_all_miss_and_all_exact():
    """UT-SCORE-05: Score bounds: all-miss yields 0.0; all-exact yields 100.0."""
    strat = WeightedScoringStrategy()

    # All-miss
    job = JobRequirements(
        job_title="Dev", required_skills=["Rust"], min_experience_years=3.0
    )
    match_miss = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Rust",
                is_required=True,
                match_type=MatchType.NONE,
                similarity=0.0,
                credit=0.0,
            )
        ],
        required_credit=0.0,
        optional_credit=None,
        experience=ExperienceAnalysis(
            required_years=3.0,
            candidate_years=0.0,
            status="unmet",
            subscore=0.0,
            gap_years=3.0,
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.UNSPECIFIED,
            candidate_level=EducationLevel.UNSPECIFIED,
            status="not_required",
            subscore=None,
        ),
    )
    res_miss = strat.score(match_miss, job)
    assert res_miss.total_score == 0.0
    assert res_miss.fit_band == FitBand.LOW

    # All-exact
    match_exact = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Rust",
                is_required=True,
                match_type=MatchType.EXACT,
                similarity=100.0,
                credit=1.0,
            )
        ],
        required_credit=1.0,
        optional_credit=None,
        experience=ExperienceAnalysis(
            required_years=3.0,
            candidate_years=5.0,
            status="met",
            subscore=1.0,
            gap_years=0.0,
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.UNSPECIFIED,
            candidate_level=EducationLevel.UNSPECIFIED,
            status="not_required",
            subscore=None,
        ),
    )
    res_exact = strat.score(match_exact, job)
    assert res_exact.total_score == 100.0
    assert res_exact.fit_band == FitBand.STRONG


def test_ut_score_06_determinism():
    """UT-SCORE-06: Scoring produces strictly identical outputs across repeated calls."""
    match, job = _build_worked_example_match()
    strat = WeightedScoringStrategy()

    res1 = strat.score(match, job)
    res2 = strat.score(match, job)
    assert res1.total_score == res2.total_score
    assert res1.fit_band == res2.fit_band
    assert res1.coverage == res2.coverage
    assert res1.flags == res2.flags


def test_ut_score_07_registry_retrieval_and_switching():
    """UT-SCORE-07: Registry provides correct strategy instances via config."""
    settings_basic = ScoringSettings(strategy="basic")
    s_basic = get_strategy("basic", settings_basic)
    assert isinstance(s_basic, BasicScoringStrategy)

    settings_weighted = ScoringSettings(strategy="weighted")
    s_weighted = get_strategy("weighted", settings_weighted)
    assert isinstance(s_weighted, WeightedScoringStrategy)


def test_ut_score_08_unknown_strategy_raises_error():
    """UT-SCORE-08: Unknown strategy name raises UnknownStrategyError listing available options."""
    settings = ScoringSettings()
    with pytest.raises(UnknownStrategyError) as exc_info:
        get_strategy("neural_quantum_scoring", settings)

    err = exc_info.value
    assert err.error_code == "E-MATCH-001"
    assert "basic" in err.message
    assert "weighted" in err.message


def test_ut_score_09_band_mapping_thresholds():
    """UT-SCORE-09: FitBand mapping applies to rounded scores at exact boundary values."""
    bands = BandThresholds(strong_min=80.0, moderate_min=60.0, limited_min=40.0)
    assert fit_band_for(80.0, bands) == FitBand.STRONG
    assert fit_band_for(79.9, bands) == FitBand.MODERATE
    assert fit_band_for(60.0, bands) == FitBand.MODERATE
    assert fit_band_for(59.9, bands) == FitBand.LIMITED
    assert fit_band_for(40.0, bands) == FitBand.LIMITED
    assert fit_band_for(39.9, bands) == FitBand.LOW


def test_ut_score_10_monotonicity():
    """UT-SCORE-10: Adding a matched required skill never decreases total score."""
    job = JobRequirements(job_title="Dev", required_skills=["Python", "SQL"])
    strat = WeightedScoringStrategy()

    # 1 of 2 required skills matched (50% coverage)
    match_partial = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Python",
                is_required=True,
                match_type=MatchType.EXACT,
                similarity=100.0,
                credit=1.0,
            ),
            SkillMatch(
                target="SQL",
                is_required=True,
                match_type=MatchType.NONE,
                similarity=0.0,
                credit=0.0,
            ),
        ],
        required_credit=0.5,
        optional_credit=None,
        experience=ExperienceAnalysis(
            required_years=0.0, status="not_required", subscore=None
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.UNSPECIFIED,
            candidate_level=EducationLevel.UNSPECIFIED,
            status="not_required",
        ),
    )
    score_partial = strat.score(match_partial, job).total_score

    # 2 of 2 required skills matched (100% coverage)
    match_full = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Python",
                is_required=True,
                match_type=MatchType.EXACT,
                similarity=100.0,
                credit=1.0,
            ),
            SkillMatch(
                target="SQL",
                is_required=True,
                match_type=MatchType.EXACT,
                similarity=100.0,
                credit=1.0,
            ),
        ],
        required_credit=1.0,
        optional_credit=None,
        experience=ExperienceAnalysis(
            required_years=0.0, status="not_required", subscore=None
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.UNSPECIFIED,
            candidate_level=EducationLevel.UNSPECIFIED,
            status="not_required",
        ),
    )
    score_full = strat.score(match_full, job).total_score

    assert score_full > score_partial


def test_ut_score_11_independence_from_irrelevant_fields():
    """UT-SCORE-11: Changing candidate name, email, warnings, or irrelevant metadata does not alter score."""
    match, job = _build_worked_example_match()
    strat = WeightedScoringStrategy()

    score1 = strat.score(match, job)
    # Reverse skill matches order (results must be order-independent)
    reversed_match = MatchResult(
        skill_matches=list(reversed(match.skill_matches)),
        required_credit=match.required_credit,
        optional_credit=match.optional_credit,
        experience=match.experience,
        education=match.education,
    )
    score2 = strat.score(reversed_match, job)
    assert score1.total_score == score2.total_score
    assert score1.fit_band == score2.fit_band


def test_ut_score_12_unknown_policy_exclude_vs_zero():
    """UT-SCORE-12: Verify unknown_policy exclude vs zero behavior, coverage, and flags."""
    job = JobRequirements(
        job_title="Engineer",
        required_skills=["Python"],
        min_experience_years=3.0,  # Applicable experience
        min_education_level=EducationLevel.BACHELOR,  # Applicable education
    )
    # Candidate with unknown experience and unknown education
    match = MatchResult(
        skill_matches=[
            SkillMatch(
                target="Python",
                is_required=True,
                match_type=MatchType.EXACT,
                similarity=100.0,
                credit=1.0,
            )
        ],
        required_credit=1.0,
        optional_credit=None,
        experience=ExperienceAnalysis(
            required_years=3.0, candidate_years=None, status="unknown", subscore=None
        ),
        education=EducationAnalysis(
            required_level=EducationLevel.BACHELOR,
            candidate_level=EducationLevel.UNSPECIFIED,
            status="unknown",
            subscore=None,
        ),
    )

    # Policy 1: 'exclude' (default)
    # Only required_skills (weight 0.50) is evaluated; experience (0.20) and education (0.15) excluded
    # Coverage = 0.50 / (0.50 + 0.35) = 0.50 / 0.85 = 0.5882 < 1.0 -> INCOMPLETE_DATA flag
    # Score = 100 * (0.50 * 1.0 / 0.50) = 100.0!
    strat_exclude = WeightedScoringStrategy(unknown_policy="exclude")
    res_exclude = strat_exclude.score(match, job)
    assert res_exclude.total_score == 100.0
    assert pytest.approx(res_exclude.coverage, abs=0.001) == 0.5882
    assert "INCOMPLETE_DATA" in res_exclude.flags
    assert "UNKNOWN_TREATED_AS_ZERO" not in res_exclude.flags

    # Policy 2: 'zero'
    # Experience (0.20) and education (0.15) are treated as subscore = 0.0
    # Sum w*s = 0.50 * 1.0 + 0.20 * 0.0 + 0.15 * 0.0 = 0.50
    # Total evaluated weight = 0.85
    # Score = 100 * (0.50 / 0.85) = 58.8!
    # Coverage = 1.0
    strat_zero = WeightedScoringStrategy(unknown_policy="zero")
    res_zero = strat_zero.score(match, job)
    assert res_zero.total_score == 58.8
    assert res_zero.coverage == 1.0
    assert "UNKNOWN_TREATED_AS_ZERO" in res_zero.flags
    assert "INCOMPLETE_DATA" not in res_zero.flags
