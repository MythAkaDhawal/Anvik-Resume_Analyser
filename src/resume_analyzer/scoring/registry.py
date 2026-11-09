"""Strategy registry and factory for candidate scoring (FR-12, §7.5)."""

from __future__ import annotations

from resume_analyzer.config.settings import ScoringSettings
from resume_analyzer.exceptions import UnknownStrategyError
from resume_analyzer.scoring.base import ScoringStrategy
from resume_analyzer.scoring.basic import BasicScoringStrategy
from resume_analyzer.scoring.weighted import WeightedScoringStrategy

STRATEGY_REGISTRY: dict[str, type[ScoringStrategy]] = {
    BasicScoringStrategy.name: BasicScoringStrategy,
    WeightedScoringStrategy.name: WeightedScoringStrategy,
}


def get_strategy(name: str, settings: ScoringSettings) -> ScoringStrategy:
    """Retrieve and configure a ScoringStrategy instance by name.

    Args:
        name: Name of scoring strategy ('basic' or 'weighted').
        settings: Active scoring configuration settings.

    Returns:
        Configured ScoringStrategy instance.

    Raises:
        UnknownStrategyError: If requested strategy name is not registered.
    """
    if name not in STRATEGY_REGISTRY:
        raise UnknownStrategyError(
            strategy_name=name,
            available=list(STRATEGY_REGISTRY.keys()),
        )

    if name == BasicScoringStrategy.name:
        return BasicScoringStrategy(bands=settings.bands)

    # Weighted strategy
    return WeightedScoringStrategy(
        weights=settings.weights,
        unknown_policy=settings.unknown_policy,
        bands=settings.bands,
    )
