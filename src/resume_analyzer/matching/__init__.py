"""Matching engine package for candidate-job requirements evaluation."""

from __future__ import annotations

from resume_analyzer.matching.education_evaluator import evaluate_education
from resume_analyzer.matching.experience_evaluator import evaluate_experience
from resume_analyzer.matching.matching_engine import MatchingEngine
from resume_analyzer.matching.skill_matcher import match_skills

__all__ = [
    "MatchingEngine",
    "evaluate_education",
    "evaluate_experience",
    "match_skills",
]
