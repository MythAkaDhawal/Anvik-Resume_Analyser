"""Scoring strategies, fit bands, and strategy registry."""

from __future__ import annotations

from resume_analyzer.scoring.bands import fit_band_for
from resume_analyzer.scoring.base import ScoringStrategy
from resume_analyzer.scoring.basic import BasicScoringStrategy
from resume_analyzer.scoring.registry import STRATEGY_REGISTRY, get_strategy
from resume_analyzer.scoring.weighted import WeightedScoringStrategy

__all__ = [
    "STRATEGY_REGISTRY",
    "BasicScoringStrategy",
    "ScoringStrategy",
    "WeightedScoringStrategy",
    "fit_band_for",
    "get_strategy",
]
