"""Feedback storage and analytics repository (FR-29, TECHNICAL_SPECIFICATION §5.10).

Collects user rating scores, section-level thumbs up/down, skill corrections,
and commentary, with strict PII masking (UT-FB-02) and aggregated analytics (UT-FB-03).
"""

from __future__ import annotations

import collections
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from resume_analyzer.exceptions import InvalidIdentifierError
from resume_analyzer.parsing.pii import mask_pii
from resume_analyzer.storage.paths import REPORT_ID_REGEX

logger = logging.getLogger(__name__)


class FeedbackRecord(BaseModel):
    """User feedback entry submitted for an analysis report (FR-29).

    Attributes:
        report_id: Canonical ID of the associated AnalysisReport.
        rating: Overall star rating from 1 to 5.
        comment: User commentary (max 1000 characters), automatically PII-masked.
        section_feedback: Mapping of section name to boolean (True=positive, False=negative).
        corrected_skills: List of skills manually corrected or adjusted by the reviewer.
        created_at: Submission timestamp in UTC.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    report_id: str
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    section_feedback: dict[str, bool] = Field(default_factory=dict)
    corrected_skills: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("report_id")
    @classmethod
    def validate_report_id_format(cls, v: str) -> str:
        """Validate report_id matches canonical format regex."""
        if not isinstance(v, str) or not REPORT_ID_REGEX.match(v):
            raise InvalidIdentifierError(str(v))
        return v

    @field_validator("comment")
    @classmethod
    def mask_comment_pii(cls, v: str | None) -> str | None:
        """Ensure emails and contact details in user comments are masked (UT-FB-02)."""
        if v is None:
            return None
        return mask_pii(v)


class FeedbackSummary(BaseModel):
    """Aggregated feedback metrics and diagnostics (UT-FB-03).

    Attributes:
        total_submissions: Total feedback records logged.
        average_rating: Mean star rating across submissions.
        section_positive_ratios: Ratio of positive feedback per section name.
        top_corrected_skills: Top skills most frequently corrected by reviewers.
    """

    model_config = ConfigDict(extra="forbid")

    total_submissions: int = 0
    average_rating: float = 0.0
    section_positive_ratios: dict[str, float] = Field(default_factory=dict)
    top_corrected_skills: list[tuple[str, int]] = Field(default_factory=list)


class FeedbackStore:
    """Append-only JSONL repository for user feedback."""

    def __init__(self, feedback_path: Path | str | None = None) -> None:
        """Initialize FeedbackStore with target JSONL file path."""
        p = feedback_path or Path("data/feedback.jsonl")
        self.path = Path(p).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: FeedbackRecord) -> None:
        """Append a validated feedback record to storage (FR-29, UT-FB-01).

        Args:
            record: Validated FeedbackRecord.
        """
        line = record.model_dump_json() + "\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)
        logger.info(
            "Appended user feedback for report_id=%s rating=%d",
            record.report_id,
            record.rating,
        )

    def list_records(self) -> list[FeedbackRecord]:
        """Read all feedback records from the JSONL file."""
        if not self.path.is_file():
            return []

        records: list[FeedbackRecord] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(FeedbackRecord.model_validate_json(stripped))
                except Exception as e:
                    logger.warning("Skipping unparseable feedback record: %s", e)
        return records

    def summarize(self) -> FeedbackSummary:
        """Calculate aggregated metrics across all recorded feedback (UT-FB-03).

        Returns:
            FeedbackSummary with counts, mean rating, section ratios, and top corrected skills.
        """
        records = self.list_records()
        if not records:
            return FeedbackSummary()

        total = len(records)
        avg_rating = sum(r.rating for r in records) / float(total)

        # Section feedback positive ratios
        section_pos: collections.defaultdict[str, int] = collections.defaultdict(int)
        section_total: collections.defaultdict[str, int] = collections.defaultdict(int)

        skill_counter: collections.Counter[str] = collections.Counter()

        for r in records:
            for sec, is_pos in r.section_feedback.items():
                section_total[sec] += 1
                if is_pos:
                    section_pos[sec] += 1

            for sk in r.corrected_skills:
                norm_sk = sk.strip()
                if norm_sk:
                    skill_counter[norm_sk] += 1

        ratios: dict[str, float] = {}
        for sec, count in section_total.items():
            ratios[sec] = section_pos[sec] / float(count) if count > 0 else 0.0

        top_skills = skill_counter.most_common(10)

        return FeedbackSummary(
            total_submissions=total,
            average_rating=round(avg_rating, 2),
            section_positive_ratios=ratios,
            top_corrected_skills=top_skills,
        )

    def purge_all(self) -> None:
        """Clear all stored feedback entries."""
        if self.path.is_file():
            self.path.unlink()
