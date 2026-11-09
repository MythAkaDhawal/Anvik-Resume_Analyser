"""Abstract base class definition for deterministic scoring strategies (FR-12, §7.5)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from resume_analyzer.models.enums import MatchType
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import MatchResult, ScoreResult


class ScoringStrategy(ABC):
    """Abstract scoring strategy defining the scoring interface.

    Scoring is a deterministic, pure function of candidate-job match outputs,
    job requirements, and configuration parameters. It must never invoke
    or depend on external AI models.
    """

    name: ClassVar[str]

    @abstractmethod
    def score(self, match: MatchResult, job: JobRequirements) -> ScoreResult:
        """Compute alignment score, fit band, components, and diagnostic flags.

        Args:
            match: Evaluated MatchResult from the matching engine.
            job: Validated JobRequirements.

        Returns:
            Validated ScoreResult instance.
        """
        raise NotImplementedError

    @staticmethod
    def check_missing_required_skills(match: MatchResult) -> bool:
        """Check if any required skill failed to match (match_type == NONE).

        Args:
            match: MatchResult containing individual skill matches.

        Returns:
            True if at least one required skill was completely missing.
        """
        return any(
            m.is_required and m.match_type == MatchType.NONE
            for m in match.skill_matches
        )
