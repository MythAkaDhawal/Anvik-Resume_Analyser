"""Fit band categorization based on rounded alignment score (§7.6)."""

from __future__ import annotations

from resume_analyzer.config.settings import BandThresholds
from resume_analyzer.models.enums import FitBand


def fit_band_for(score: float, bands: BandThresholds) -> FitBand:
    """Map a rounded total score to its corresponding FitBand.

    Band assignment operates on the rounded total score (1 decimal place):
    - score >= bands.strong_min (default 80.0) -> FitBand.STRONG
    - score >= bands.moderate_min (default 60.0) -> FitBand.MODERATE
    - score >= bands.limited_min (default 40.0) -> FitBand.LIMITED
    - otherwise -> FitBand.LOW

    Args:
        score: Total alignment score rounded to 1 decimal place (0.0-100.0).
        bands: Configured BandThresholds.

    Returns:
        FitBand enum value.
    """
    if score >= bands.strong_min:
        return FitBand.STRONG
    if score >= bands.moderate_min:
        return FitBand.MODERATE
    if score >= bands.limited_min:
        return FitBand.LIMITED
    return FitBand.LOW
