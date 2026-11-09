"""AnalysisService orchestrator implementing the end-to-end analysis pipeline.

Coordinates file validation, text extraction, deterministic parsing, optional AI augmentation,
validation, matching, scoring, report generation, and optional persistence.
Enforces that deterministic scoring never depends on AI availability (FR-32).
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from resume_analyzer.ai.ai_service import AIService
from resume_analyzer.ai.provider_factory import get_provider
from resume_analyzer.ai.providers.null import NullProvider
from resume_analyzer.config.settings import Settings, get_settings
from resume_analyzer.ingestion.file_loader import load_resume
from resume_analyzer.matching.matching_engine import MatchingEngine
from resume_analyzer.models.candidate import (
    Candidate,
    EducationEntry,
    ExperienceEntry,
    Skill,
)
from resume_analyzer.models.enums import EducationLevel, FeatureStatus, Provenance
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.models.results import (
    AIInsights,
    AnalysisReport,
    FeatureResult,
    MatchResult,
    ScoreResult,
)
from resume_analyzer.parsing.education_parser import detect_education_level
from resume_analyzer.parsing.experience_parser import (
    compute_duration_months,
    total_experience_years,
)
from resume_analyzer.parsing.resume_parser import ResumeParser
from resume_analyzer.reporting.report_builder import ReportBuilder
from resume_analyzer.scoring.registry import get_strategy
from resume_analyzer.skills.normalizer import normalize_skill
from resume_analyzer.skills.skill_index import SkillIndex, get_skill_index
from resume_analyzer.validation.validators import (
    assess_parse_quality,
    validate_candidate,
    validate_job,
)

logger = logging.getLogger(__name__)


DEFAULT_TAXONOMY_PATH = Path("config/skills_taxonomy.json")


class AnalysisOptions(BaseModel):
    """User-configurable options controlling analysis execution."""

    strategy: str = "weighted"
    ai_features: set[str] = Field(default_factory=set)
    persist: bool = False

    def __init__(
        self,
        strategy: str = "weighted",
        ai_features: set[str] | None = None,
        persist: bool = False,
        ai_enabled: bool | None = None,
        ai_extract_candidate: bool = False,
        ai_categorize_skills: bool = False,
        ai_explain_match: bool = False,
        ai_recommendations: bool = False,
        ai_interview_questions: bool = False,
        **data: Any,
    ) -> None:
        if ai_features is None:
            features: set[str] = set()
            if ai_enabled or (
                ai_enabled is None
                and any(
                    [
                        ai_extract_candidate,
                        ai_categorize_skills,
                        ai_explain_match,
                        ai_recommendations,
                        ai_interview_questions,
                    ]
                )
            ):
                if ai_extract_candidate:
                    features.add("extraction")
                if ai_categorize_skills:
                    features.add("categorization")
                if ai_explain_match:
                    features.add("explanation")
                if ai_recommendations:
                    features.add("recommendations")
                if ai_interview_questions:
                    features.add("interview_questions")
                if not features and ai_enabled:
                    features = {
                        "extraction",
                        "categorization",
                        "explanation",
                        "recommendations",
                        "interview_questions",
                    }
        else:
            features = set(ai_features)

        super().__init__(
            strategy=strategy, ai_features=features, persist=persist, **data
        )

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_features)


class AnalysisService:
    """High-level application facade for analyzing candidate resumes against jobs."""

    def __init__(
        self,
        settings: Settings | None = None,
        skill_index: SkillIndex | None = None,
        ai_service: AIService | None = None,
        result_store: Any | None = None,
    ) -> None:
        """Initialize analysis service with domain components.

        Args:
            settings: Optional custom application settings.
            skill_index: Optional pre-loaded skill index.
            ai_service: Optional configured AI service facade.
            result_store: Optional result store for persisting reports.
        """
        self.settings = settings or get_settings()
        self.skill_index = skill_index or get_skill_index(DEFAULT_TAXONOMY_PATH)

        if ai_service is not None:
            self.ai_service: AIService | None = ai_service
        else:
            try:
                provider = get_provider(self.settings.ai)
                self.ai_service = AIService(
                    settings=self.settings.ai, provider=provider
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize AI provider (%s); defaulting to NullProvider",
                    e,
                )
                self.ai_service = AIService(
                    settings=self.settings.ai, provider=NullProvider()
                )

        self.result_store = result_store

    def _merge_p1_extraction(
        self,
        candidate: Candidate,
        extraction_res: Any,
        ref_date: date,
    ) -> None:
        """Merge rule-precedent AI extraction results into parsed candidate profile."""
        if (
            extraction_res.status not in (FeatureStatus.OK, FeatureStatus.PARTIAL)
            or not extraction_res.data
        ):
            return

        if candidate.name is None and extraction_res.data.name:
            candidate.name = extraction_res.data.name

        existing_keys = {
            s.canonical_name or normalize_skill(s.name) for s in candidate.skills
        }
        for ai_sk in extraction_res.data.skills:
            norm = normalize_skill(ai_sk.name)
            canon = self.skill_index.get_canonical(norm)
            key = canon or norm
            if key not in existing_keys:
                category = self.skill_index.get_category(canon) if canon else None
                candidate.skills.append(
                    Skill(
                        name=ai_sk.name,
                        canonical_name=canon,
                        category=category,
                        category_provenance=Provenance.EXTRACTED_AI
                        if category
                        else None,
                        provenance=Provenance.EXTRACTED_AI,
                        mentions=ai_sk.mentions,
                    )
                )
                existing_keys.add(key)

        if not candidate.experience and extraction_res.data.experience:
            new_exp: list[ExperienceEntry] = []
            for e in extraction_res.data.experience:
                dur = compute_duration_months(
                    e.start, e.end, e.is_current, reference_date=ref_date
                )
                new_exp.append(
                    ExperienceEntry(
                        job_title=e.job_title,
                        company=e.company,
                        start=e.start,
                        end=e.end,
                        is_current=e.is_current,
                        duration_months=dur,
                        provenance=Provenance.EXTRACTED_AI,
                    )
                )
            candidate.experience = new_exp
            candidate.total_experience_years = total_experience_years(
                new_exp, reference_date=ref_date
            )

        if not candidate.education and extraction_res.data.education:
            new_edu: list[EducationEntry] = []
            for edu in extraction_res.data.education:
                lvl = (
                    detect_education_level(edu.degree)
                    if edu.degree
                    else EducationLevel.UNSPECIFIED
                )
                new_edu.append(
                    EducationEntry(
                        degree=edu.degree,
                        level=lvl,
                        field_of_study=edu.field_of_study,
                        institution=edu.institution,
                        provenance=Provenance.EXTRACTED_AI,
                    )
                )
            candidate.education = new_edu
            if new_edu:
                candidate.highest_education_level = max(e.level for e in new_edu)

    def _run_ai_insights(
        self,
        opts: AnalysisOptions,
        candidate: Candidate,
        job: JobRequirements,
        match_result: MatchResult,
        score_result: ScoreResult,
        ai_insights: AIInsights,
    ) -> None:
        """Run requested P2-P5 generative insights with grounding and provenance."""
        ai_available = bool(self.ai_service and self.ai_service.is_available())
        if not ai_available or not self.ai_service:
            disabled_or_unavail = (
                FeatureStatus.DISABLED
                if (
                    not self.settings.ai.enabled
                    or (
                        self.ai_service
                        and isinstance(self.ai_service.provider, NullProvider)
                    )
                )
                else FeatureStatus.UNAVAILABLE
            )
            ai_insights.categorization = FeatureResult(
                feature="categorization", status=disabled_or_unavail
            )
            ai_insights.explanation = FeatureResult(
                feature="explanation", status=disabled_or_unavail
            )
            ai_insights.recommendations = FeatureResult(
                feature="recommendations", status=disabled_or_unavail
            )
            ai_insights.interview_questions = FeatureResult(
                feature="interview_questions", status=disabled_or_unavail
            )
            return

        # P2: Categorization
        if "categorization" in opts.ai_features:
            unrecognized = [s.name for s in candidate.skills if not s.category]
            cat_res = self.ai_service.categorize_skills(
                unrecognized, allowed_categories=self.skill_index.categories
            )
            ai_insights.categorization = FeatureResult(
                feature="categorization",
                status=cat_res.status,
                data=cat_res.data.categories if cat_res.data else None,
                error_code=cat_res.error_code,
                prompt_id=cat_res.prompt_id,
                prompt_version=cat_res.prompt_version,
                model=cat_res.model,
                provenance=cat_res.provenance,
                dropped_items=cat_res.dropped_items,
            )
        else:
            ai_insights.categorization = FeatureResult(
                feature="categorization", status=FeatureStatus.DISABLED
            )

        # P3: Explanation
        if "explanation" in opts.ai_features:
            ai_insights.explanation = self.ai_service.explain_match(
                match_result, score_result, job
            )
        else:
            ai_insights.explanation = FeatureResult(
                feature="explanation", status=FeatureStatus.DISABLED
            )

        # P4: Recommendations
        if "recommendations" in opts.ai_features:
            rec_res = self.ai_service.generate_recommendations(match_result, job)
            ai_insights.recommendations = FeatureResult(
                feature="recommendations",
                status=rec_res.status,
                data=rec_res.data.recommendations if rec_res.data else None,
                error_code=rec_res.error_code,
                prompt_id=rec_res.prompt_id,
                prompt_version=rec_res.prompt_version,
                model=rec_res.model,
                provenance=rec_res.provenance,
                dropped_items=rec_res.dropped_items,
            )
        else:
            ai_insights.recommendations = FeatureResult(
                feature="recommendations", status=FeatureStatus.DISABLED
            )

        # P5: Interview Questions
        if "interview_questions" in opts.ai_features:
            iq_res = self.ai_service.generate_interview_questions(match_result, job)
            ai_insights.interview_questions = FeatureResult(
                feature="interview_questions",
                status=iq_res.status,
                data=iq_res.data.questions if iq_res.data else None,
                error_code=iq_res.error_code,
                prompt_id=iq_res.prompt_id,
                prompt_version=iq_res.prompt_version,
                model=iq_res.model,
                provenance=iq_res.provenance,
                dropped_items=iq_res.dropped_items,
            )
        else:
            ai_insights.interview_questions = FeatureResult(
                feature="interview_questions", status=FeatureStatus.DISABLED
            )

    def analyze(
        self,
        filename: str,
        data: bytes,
        job: JobRequirements,
        options: AnalysisOptions | None = None,
        reference_date: date | None = None,
    ) -> AnalysisReport:
        """Execute complete resume analysis pipeline for a single resume.

        Pipeline Stages:
            1. Validate job specification.
            2. Validate upload bytes (mime, size, archive safety).
            3. Extract raw text from file format (PDF, DOCX, TXT).
            4. Deterministic parsing (skills, dates, degree levels).
            5. Optional P1 AI extraction (with strict grounding and rule-precedence merge).
            6. Candidate quality validation.
            7. Deterministic candidate-job matching.
            8. Deterministic scoring and fit-band evaluation.
            9. Optional P2-P5 AI insights.
            10. Report assembly and validation.
            11. Optional persistence.
        """
        opts = options or AnalysisOptions()
        ref_date = reference_date or date.today()

        # Stage 1: Validate Job Specification
        validate_job(job)

        # Stage 2 & 3: Validate File and Extract Text
        loaded_resume = load_resume(filename, data, settings=self.settings.files)
        raw_text = loaded_resume.raw_text

        # Stage 4: Deterministic Parsing
        parser = ResumeParser(index=self.skill_index)
        candidate = parser.parse(loaded_resume, reference_date=ref_date)
        candidate.parse_warnings.extend(assess_parse_quality(candidate))

        ai_insights = AIInsights()

        # Stage 5: Optional AI Extraction (P1)
        ai_available = bool(self.ai_service and self.ai_service.is_available())
        if ai_available and "extraction" in opts.ai_features and self.ai_service:
            extraction_res = self.ai_service.extract_candidate(raw_text)
            ai_insights.extraction_status = FeatureResult[None](
                feature="extraction",
                status=extraction_res.status,
                data=None,
                error_code=extraction_res.error_code,
                prompt_id=extraction_res.prompt_id,
                prompt_version=extraction_res.prompt_version,
                model=extraction_res.model,
                provenance=extraction_res.provenance,
                dropped_items=extraction_res.dropped_items,
            )
            self._merge_p1_extraction(candidate, extraction_res, ref_date)
        else:
            status = (
                FeatureStatus.DISABLED
                if (not self.settings.ai.enabled or not ai_available)
                else FeatureStatus.UNAVAILABLE
            )
            ai_insights.extraction_status = FeatureResult[None](
                feature="extraction",
                status=status,
                data=None,
            )

        # Stage 6: Candidate Quality Validation
        validate_candidate(candidate)

        # Stage 7: Deterministic Matching
        matching_engine = MatchingEngine(
            index=self.skill_index,
            settings=self.settings,
        )
        match_result = matching_engine.match(candidate, job)

        # Stage 8: Deterministic Scoring
        strategy = get_strategy(opts.strategy, settings=self.settings.scoring)
        score_result = strategy.score(match_result, job)

        # Stage 9: Optional AI Insights (P2 - P5)
        self._run_ai_insights(
            opts, candidate, job, match_result, score_result, ai_insights
        )

        # Stage 10: Assemble Report
        report = ReportBuilder.build(
            candidate=candidate,
            job=job,
            match=match_result,
            score=score_result,
            ai=ai_insights,
            settings=self.settings,
        )

        # Stage 11: Optional Persistence
        if opts.persist and self.result_store is not None:
            try:
                self.result_store.save(report)
            except Exception as e:
                logger.error(
                    "Failed to persist analysis report %s: %s", report.report_id, e
                )

        return report
