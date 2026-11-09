"""Master candidate-job matching engine orchestrator (FR-09, FR-10, FR-11).

Orchestrates deterministic skill matching, experience gap evaluation, and educational
attainment assessment, assembling comprehensive MatchResult outputs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from resume_analyzer.config.settings import Settings, get_settings
from resume_analyzer.matching.education_evaluator import evaluate_education
from resume_analyzer.matching.experience_evaluator import evaluate_experience
from resume_analyzer.matching.skill_matcher import match_skills
from resume_analyzer.models.candidate import Candidate
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import MatchResult
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import SkillTaxonomy
from resume_analyzer.validation.validators import validate_candidate, validate_job

logger = logging.getLogger(__name__)


class MatchingEngine:
    """Deterministic candidate-job matching orchestrator.

    Attributes:
        index: Active SkillIndex.
        settings: Active system settings.
    """

    def __init__(
        self,
        index: SkillIndex | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize MatchingEngine with prebuilt index or load default."""
        self.settings = settings or get_settings()

        if index is not None:
            self.index = index
        else:
            tax_path = Path("config/skills_taxonomy.json")
            taxonomy = SkillTaxonomy.from_file(tax_path)
            self.index = SkillIndex(taxonomy)

    def match(self, candidate: Candidate, job: JobRequirements) -> MatchResult:
        """Evaluate candidate against job requirements.

        Performs semantic validation, skill matching, experience evaluation,
        and education evaluation.

        Args:
            candidate: Candidate profile.
            job: Job requirements.

        Returns:
            Validated MatchResult instance.
        """
        # 1. Validation of inputs
        validated_job = validate_job(job)
        validate_candidate(candidate)

        # 2. Skill matching
        skill_matches = match_skills(
            candidate=candidate,
            job=validated_job,
            index=self.index,
            fuzzy_settings=self.settings.fuzzy,
        )

        # 3. Calculate required and optional credit
        required_matches = [m for m in skill_matches if m.is_required]
        if required_matches:
            required_credit = sum(m.credit for m in required_matches) / len(
                required_matches
            )
        else:
            required_credit = 0.0

        optional_matches = [m for m in skill_matches if not m.is_required]
        if optional_matches:
            optional_credit = sum(m.credit for m in optional_matches) / len(
                optional_matches
            )
        else:
            optional_credit = None

        # 4. Experience evaluation
        exp_analysis = evaluate_experience(
            candidate_years=candidate.total_experience_years,
            required_years=validated_job.min_experience_years,
        )

        # 5. Education evaluation
        edu_analysis = evaluate_education(
            candidate=candidate,
            job=validated_job,
        )

        return MatchResult(
            skill_matches=skill_matches,
            required_credit=round(required_credit, 4),
            optional_credit=round(optional_credit, 4)
            if optional_credit is not None
            else None,
            experience=exp_analysis,
            education=edu_analysis,
        )
