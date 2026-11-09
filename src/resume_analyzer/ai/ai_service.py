"""Master Generative AI service coordinating P1–P5 features (DR-AI-1..4)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import ValidationError

from resume_analyzer.ai.grounding import (
    ground_p1_extraction,
    ground_p2_categorization,
    ground_p3_explanation,
    ground_p4_recommendations,
    ground_p5_interview_questions,
)
from resume_analyzer.ai.json_utils import parse_json_response
from resume_analyzer.ai.prompt_registry import PROMPT_VERSIONS, render_prompt
from resume_analyzer.ai.provider_base import LLMProvider
from resume_analyzer.ai.provider_factory import get_provider
from resume_analyzer.ai.providers.null import NullProvider
from resume_analyzer.ai.rate_limiter import AIRateLimiter
from resume_analyzer.ai.sanitizer import sanitize_prompt_text
from resume_analyzer.ai.schemas import (
    ExtractionResult,
    ImprovementRecommendations,
    InterviewQuestionsResult,
    MatchExplanation,
    SkillCategorizationResult,
)
from resume_analyzer.config.settings import AISettings, get_settings
from resume_analyzer.exceptions import (
    AIProviderUnavailableError,
    AIRateLimitError,
    AIServiceError,
)
from resume_analyzer.models.enums import FeatureStatus, MatchType
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import FeatureResult, MatchResult, ScoreResult

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AIService:
    """Orchestrates optional, provider-agnostic GenAI enhancements.

    Guaranteed principles:
    1. AI never alters scoring, candidate identity, or fit bands.
    2. Operates seamlessly with NullProvider when AI is disabled.
    3. Handles rate limiting, retries, one repair attempt, and strict fact grounding.
    """

    def __init__(
        self,
        settings: AISettings | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        """Initialize AIService with provider and configuration."""
        self.settings = settings or get_settings().ai
        self.provider = provider or get_provider(self.settings)
        self.rate_limiter = AIRateLimiter(requests_per_minute=30)

    def is_available(self) -> bool:
        """Check whether AI operations are enabled and supported by active provider."""
        return self.settings.enabled and not isinstance(self.provider, NullProvider)

    # -------------------------------------------------------------------------
    # P1: Resume Information Extraction
    # -------------------------------------------------------------------------
    def extract_candidate(
        self,
        raw_resume_text: str,
    ) -> FeatureResult[ExtractionResult]:
        """P1: Extract candidate facts to supplement deterministic parser."""
        feature_name = "extraction"
        prompt_id = "p1_extract"

        if (
            not self.settings.enabled
            or not self.settings.features.extraction
            or isinstance(self.provider, NullProvider)
        ):
            return self._disabled_result(feature_name, prompt_id)

        # Sanitize and mask PII
        sanitized_resume, _ = sanitize_prompt_text(raw_resume_text)
        from resume_analyzer.parsing.pii import mask_pii

        masked_resume = mask_pii(sanitized_resume)

        context = {"masked_sanitized_resume_text": masked_resume}

        def ground_fn(parsed: ExtractionResult) -> tuple[ExtractionResult, int]:
            return ground_p1_extraction(parsed, raw_resume_text)

        return self._execute_feature(
            feature_name=feature_name,
            prompt_id=prompt_id,
            context=context,
            schema_cls=ExtractionResult,
            ground_fn=ground_fn,
        )

    # -------------------------------------------------------------------------
    # P2: Skill Categorization
    # -------------------------------------------------------------------------
    def categorize_skills(
        self,
        skills: list[str],
        allowed_categories: list[str],
    ) -> FeatureResult[SkillCategorizationResult]:
        """P2: Assign categories to unrecognized skills."""
        feature_name = "categorization"
        prompt_id = "p2_categorize"

        if (
            not self.settings.enabled
            or not self.settings.features.categorization
            or isinstance(self.provider, NullProvider)
        ):
            return self._disabled_result(feature_name, prompt_id)

        if not skills:
            return FeatureResult(
                feature=feature_name,
                status=FeatureStatus.OK,
                data=SkillCategorizationResult(categories=[]),
                prompt_id=prompt_id,
                prompt_version=PROMPT_VERSIONS[prompt_id],
                model=self.settings.model,
                dropped_items=0,
            )

        context = {
            "categories_json_array": json.dumps(allowed_categories),
            "skills_json_array": json.dumps(skills[:100]),
        }

        def ground_fn(
            parsed: SkillCategorizationResult,
        ) -> tuple[SkillCategorizationResult, int]:
            return ground_p2_categorization(
                parsed,
                input_skills=skills[:100],
                allowed_categories=allowed_categories,
                min_confidence=0.5,
            )

        return self._execute_feature(
            feature_name=feature_name,
            prompt_id=prompt_id,
            context=context,
            schema_cls=SkillCategorizationResult,
            ground_fn=ground_fn,
        )

    # -------------------------------------------------------------------------
    # P3: Match Explanation
    # -------------------------------------------------------------------------
    def explain_match(
        self,
        match: MatchResult,
        score: ScoreResult,
        job: JobRequirements,
    ) -> FeatureResult[MatchExplanation]:
        """P3: Generate natural language explanation citing deterministic facts."""
        feature_name = "explanation"
        prompt_id = "p3_explain"

        if (
            not self.settings.enabled
            or not self.settings.features.explanation
            or isinstance(self.provider, NullProvider)
        ):
            return self._disabled_result(feature_name, prompt_id)

        # Build numbered facts list
        facts: list[dict[str, Any]] = [
            {"id": "F1", "fact": f"Job Title: {job.job_title}"},
            {"id": "F2", "fact": f"Required Skills Total: {len(job.required_skills)}"},
            {"id": "F3", "fact": f"Total Score: {score.total_score:.1f} out of 100"},
            {"id": "F4", "fact": f"Fit Band: {score.fit_band.name}"},
            {
                "id": "F5",
                "fact": f"Experience Requirement: {job.min_experience_years} years, Candidate: {match.experience.candidate_years or 'unknown'} years (Status: {match.experience.status})",
            },
            {
                "id": "F6",
                "fact": f"Education Requirement: {job.min_education_level.name}, Candidate: {match.education.candidate_level.name} (Status: {match.education.status})",
            },
        ]

        fact_counter = 7
        matched_req = [
            m.target
            for m in match.skill_matches
            if m.is_required and m.match_type != MatchType.NONE
        ]
        if matched_req:
            facts.append(
                {
                    "id": f"F{fact_counter}",
                    "fact": f"Matched Required Skills: {', '.join(matched_req)}",
                }
            )
            fact_counter += 1

        missing_req = [
            m.target
            for m in match.skill_matches
            if m.is_required and m.match_type == MatchType.NONE
        ]
        if missing_req:
            facts.append(
                {
                    "id": f"F{fact_counter}",
                    "fact": f"Missing Required Skills: {', '.join(missing_req)}",
                }
            )
            fact_counter += 1

        facts_json = json.dumps(facts, indent=2)
        valid_fact_ids = {f["id"] for f in facts}

        # Collect all number tokens appearing in facts
        allowed_numbers: set[str] = set()
        for f in facts:
            allowed_numbers.update(re.findall(r"\b\d+(?:\.\d+)?\b", f["fact"]))
            allowed_numbers.add(f["id"][1:])  # fact digit

        context = {"facts_json": facts_json}

        def ground_fn(parsed: MatchExplanation) -> tuple[MatchExplanation, int]:
            return ground_p3_explanation(parsed, valid_fact_ids, allowed_numbers)

        return self._execute_feature(
            feature_name=feature_name,
            prompt_id=prompt_id,
            context=context,
            schema_cls=MatchExplanation,
            ground_fn=ground_fn,
        )

    # -------------------------------------------------------------------------
    # P4: Recommendations
    # -------------------------------------------------------------------------
    def generate_recommendations(
        self,
        match: MatchResult,
        job: JobRequirements,
    ) -> FeatureResult[ImprovementRecommendations]:
        """P4: Suggest concrete candidate improvements for identified gaps."""
        feature_name = "recommendations"
        prompt_id = "p4_recommend"

        if (
            not self.settings.enabled
            or not self.settings.features.recommendations
            or isinstance(self.provider, NullProvider)
        ):
            return self._disabled_result(feature_name, prompt_id)

        # Build gap facts
        gaps: list[dict[str, Any]] = []
        gap_counter = 1

        for m in match.skill_matches:
            if m.is_required and m.match_type == MatchType.NONE:
                gaps.append(
                    {
                        "id": f"G{gap_counter}",
                        "type": "missing_required_skill",
                        "skill": m.target,
                    }
                )
                gap_counter += 1
            elif not m.is_required and m.match_type == MatchType.NONE:
                gaps.append(
                    {
                        "id": f"G{gap_counter}",
                        "type": "missing_optional_skill",
                        "skill": m.target,
                    }
                )
                gap_counter += 1
            elif m.match_type == MatchType.FUZZY:
                gaps.append(
                    {
                        "id": f"G{gap_counter}",
                        "type": "weak_match",
                        "skill": m.target,
                        "note": f"matched partially to '{m.matched_candidate_skill}'",
                    }
                )
                gap_counter += 1

        if match.experience.status in ("partial", "unmet"):
            gaps.append(
                {
                    "id": f"G{gap_counter}",
                    "type": "experience_gap",
                    "required_years": match.experience.required_years,
                    "candidate_years": match.experience.candidate_years or 0.0,
                }
            )
            gap_counter += 1

        if not gaps:
            return FeatureResult(
                feature=feature_name,
                status=FeatureStatus.OK,
                data=ImprovementRecommendations(recommendations=[]),
                prompt_id=prompt_id,
                prompt_version=PROMPT_VERSIONS[prompt_id],
                model=self.settings.model,
                dropped_items=0,
            )

        gap_facts = {
            "job_title": job.job_title,
            "gaps": gaps[:6],
            "existing_strengths": [
                m.target for m in match.skill_matches if m.credit >= 1.0
            ][:5],
        }

        valid_gap_ids = {g["id"] for g in gaps[:6]}
        context = {"gap_facts_json": json.dumps(gap_facts, indent=2)}

        def ground_fn(
            parsed: ImprovementRecommendations,
        ) -> tuple[ImprovementRecommendations, int]:
            return ground_p4_recommendations(parsed, valid_gap_ids)

        return self._execute_feature(
            feature_name=feature_name,
            prompt_id=prompt_id,
            context=context,
            schema_cls=ImprovementRecommendations,
            ground_fn=ground_fn,
        )

    # -------------------------------------------------------------------------
    # P5: Interview Questions
    # -------------------------------------------------------------------------
    def generate_interview_questions(
        self,
        match: MatchResult,
        job: JobRequirements,
        question_count: int | None = None,
    ) -> FeatureResult[InterviewQuestionsResult]:
        """P5: Generate structured, bias-free interview questions."""
        feature_name = "interview_questions"
        prompt_id = "p5_interview"

        if (
            not self.settings.enabled
            or not self.settings.features.interview_questions
            or isinstance(self.provider, NullProvider)
        ):
            return self._disabled_result(feature_name, prompt_id)

        count = question_count or self.settings.question_count or 8
        count = max(5, min(12, count))

        strength_skills = [m.target for m in match.skill_matches if m.credit >= 1.0]
        gap_skills = [
            m.target for m in match.skill_matches if m.match_type == MatchType.NONE
        ]
        uncertain_skills = [
            m.target for m in match.skill_matches if m.match_type == MatchType.FUZZY
        ]

        interview_facts = {
            "job_title": job.job_title,
            "required_skills": job.required_skills,
            "strength_skills": strength_skills,
            "gap_skills": gap_skills,
            "uncertain_skills": uncertain_skills,
            "experience": {
                "required_years": job.min_experience_years,
                "candidate_years": match.experience.candidate_years,
            },
            "question_count": count,
        }

        allowed_skills = set(job.required_skills + job.optional_skills)
        context = {
            "interview_facts_json": json.dumps(interview_facts, indent=2),
            "question_count": count,
        }

        def ground_fn(
            parsed: InterviewQuestionsResult,
        ) -> tuple[InterviewQuestionsResult, int]:
            return ground_p5_interview_questions(
                parsed, allowed_skills, target_count=count
            )

        return self._execute_feature(
            feature_name=feature_name,
            prompt_id=prompt_id,
            context=context,
            schema_cls=InterviewQuestionsResult,
            ground_fn=ground_fn,
        )

    # -------------------------------------------------------------------------
    # Internal Pipeline Execution with Retries and Repair
    # -------------------------------------------------------------------------
    def _execute_feature(
        self,
        feature_name: str,
        prompt_id: str,
        context: dict[str, Any],
        schema_cls: type[T],
        ground_fn: Callable[[T], tuple[T, int]],
    ) -> FeatureResult[T]:
        """Execute standard prompt rendering, inference, repair, and grounding."""
        system_prompt, user_prompt, nonce = render_prompt(prompt_id, context)

        # 1. First completion attempt with rate limiting
        raw_response = ""
        try:
            self.rate_limiter.acquire(blocking=True)
            raw_response = self.provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_output_tokens,
            )
        except (AIRateLimitError, AIProviderUnavailableError) as err:
            logger.warning("AI provider error for %s: %s", feature_name, err)
            return FeatureResult(
                feature=feature_name,  # type: ignore[arg-type]
                status=FeatureStatus.UNAVAILABLE,
                error_code=err.error_code,
                prompt_id=prompt_id,
                prompt_version=PROMPT_VERSIONS[prompt_id],
                model=self.settings.model,
            )
        except Exception as err:
            logger.error(
                "Unexpected failure invoking AI provider for %s: %s", feature_name, err
            )
            return FeatureResult(
                feature=feature_name,  # type: ignore[arg-type]
                status=FeatureStatus.UNAVAILABLE,
                error_code="E-AI-001",
                prompt_id=prompt_id,
                prompt_version=PROMPT_VERSIONS[prompt_id],
                model=self.settings.model,
            )

        # 2. Parse JSON response
        parsed_obj, parse_failed = None, False
        try:
            json_dict = parse_json_response(raw_response)
            parsed_obj = schema_cls.model_validate(json_dict)
        except (AIServiceError, ValidationError, Exception) as err:
            logger.info(
                "First response validation failed for %s: %s. Initiating repair retry.",
                feature_name,
                err,
            )
            parse_failed = True

        # 3. Exactly one repair retry on JSON validation failure (UT-AI-05)
        if parse_failed:
            repair_prompt = (
                f"Your previous response could not be parsed as valid JSON matching the required schema.\n"
                f"Please fix and output ONLY the single valid JSON object adhering strictly to the schema:\n"
                f"{raw_response[:500]}"
            )
            try:
                self.rate_limiter.acquire(blocking=True)
                repaired_response = self.provider.generate(
                    prompt=repair_prompt,
                    system_prompt=system_prompt,
                    temperature=0.0,
                    max_tokens=self.settings.max_output_tokens,
                )
                json_dict = parse_json_response(repaired_response)
                parsed_obj = schema_cls.model_validate(json_dict)
            except Exception as repair_err:
                logger.warning(
                    "Repair retry failed for %s: %s", feature_name, repair_err
                )
                return FeatureResult(
                    feature=feature_name,  # type: ignore[arg-type]
                    status=FeatureStatus.UNAVAILABLE,
                    error_code="E-AI-003",
                    prompt_id=prompt_id,
                    prompt_version=PROMPT_VERSIONS[prompt_id],
                    model=self.settings.model,
                )

        # 4. Post-inference grounding and safety checks
        grounded_data, dropped_count = ground_fn(parsed_obj)

        return FeatureResult(
            feature=feature_name,  # type: ignore[arg-type]
            status=FeatureStatus.OK,
            data=grounded_data,
            prompt_id=prompt_id,
            prompt_version=PROMPT_VERSIONS[prompt_id],
            model=self.settings.model,
            dropped_items=dropped_count,
        )

    def _disabled_result(self, feature_name: str, prompt_id: str) -> FeatureResult[T]:
        """Generate standardized FeatureResult for disabled AI features."""
        return FeatureResult(
            feature=feature_name,  # type: ignore[arg-type]
            status=FeatureStatus.DISABLED,
            data=None,
            prompt_id=prompt_id,
            prompt_version=PROMPT_VERSIONS.get(prompt_id, "1.0.0"),
            model=self.settings.model,
            dropped_items=0,
        )
