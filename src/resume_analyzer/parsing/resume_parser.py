"""Master deterministic resume parser orchestrator (FR-03–FR-08).

Assembles Candidate model from cleaned text, sections, contacts, skills,
experience, education, and injection security scans. Never raises on missing sections.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from resume_analyzer.ingestion.file_loader import LoadedResume
from resume_analyzer.models.candidate import Candidate, ParseWarning
from resume_analyzer.parsing.contact_extractor import extract_email, extract_name
from resume_analyzer.parsing.education_parser import parse_education
from resume_analyzer.parsing.experience_parser import (
    parse_experience,
    total_experience_years,
)
from resume_analyzer.parsing.pii import scan_injection_indicators
from resume_analyzer.parsing.section_splitter import split_sections
from resume_analyzer.parsing.skills_extractor import extract_skills
from resume_analyzer.parsing.text_cleaner import clean_text
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import SkillTaxonomy

logger = logging.getLogger(__name__)

PARSER_VERSION = "0.1.0"


class ResumeParser:
    """Orchestrates deterministic parsing of validated resumes into Candidate records.

    Attributes:
        index: SkillIndex used for taxonomy lookups and body scans.
    """

    def __init__(self, index: SkillIndex | None = None) -> None:
        """Initialize ResumeParser with prebuilt SkillIndex or load default taxonomy."""
        if index is not None:
            self.index = index
        else:
            default_tax_path = Path("config/skills_taxonomy.json")
            if default_tax_path.exists():
                taxonomy = SkillTaxonomy.from_file(default_tax_path)
                self.index = SkillIndex(taxonomy)
            else:
                raise RuntimeError(
                    f"Default skill taxonomy not found at {default_tax_path}. "
                    "Provide a SkillIndex or ensure taxonomy file exists."
                )

    def parse(
        self,
        loaded: LoadedResume,
        reference_date: date | None = None,
    ) -> Candidate:
        """Parse LoadedResume into structured Candidate profile.

        Never raises an exception on partial or missing sections (FR-08).

        Args:
            loaded: In-memory LoadedResume from ingestion layer.
            reference_date: Date used for resolving 'Present' employment.
                Defaults to date.today().

        Returns:
            Validated Candidate instance with all extracted facts and warnings.
        """
        ref_date = reference_date or date.today()
        all_warnings: list[ParseWarning] = list(loaded.warnings)

        # 1. Clean and normalize raw text
        cleaned_text = clean_text(loaded.raw_text)

        # 2. Assess text quality
        quality_warning = _assess_text_quality(cleaned_text)
        if quality_warning:
            all_warnings.append(quality_warning)

        # 3. Split into sections
        sections, section_warn_codes = split_sections(cleaned_text)
        for code in section_warn_codes:
            all_warnings.append(
                ParseWarning(
                    code=code,
                    message="No standard section headings detected in resume text.",
                    field="sections",
                )
            )

        header_text = sections.get("header", "")
        if not header_text:
            header_text = "\n".join(cleaned_text.split("\n")[:10])

        # 4. Extract contact information
        email, email_warnings = extract_email(header_text, cleaned_text)
        all_warnings.extend(email_warnings)

        name, name_warnings = extract_name(header_text, email)
        all_warnings.extend(name_warnings)

        # 5. Extract skills
        skills, skill_warnings = extract_skills(sections, self.index)
        all_warnings.extend(skill_warnings)

        # 6. Extract experience
        exp_text = sections.get("experience", "")
        exp_entries, exp_warnings = parse_experience(exp_text, ref_date)
        all_warnings.extend(exp_warnings)
        total_exp = total_experience_years(exp_entries, ref_date)

        # 7. Extract education
        edu_text = sections.get("education", "")
        edu_entries, highest_edu, edu_warnings = parse_education(edu_text)
        all_warnings.extend(edu_warnings)

        # 8. Scan for prompt injection indicators
        injection_codes = scan_injection_indicators(cleaned_text)
        if injection_codes:
            all_warnings.append(
                ParseWarning(
                    code="INJECTION_INDICATORS",
                    message=f"Prompt injection indicators detected: {', '.join(injection_codes)}.",
                    field="injection_indicators",
                )
            )

        # 9. Assemble candidate profile
        candidate = Candidate(
            candidate_id=loaded.validated_file.candidate_id,
            name=name,
            email=email,
            skills=skills,
            experience=exp_entries,
            education=edu_entries,
            total_experience_years=total_exp,
            highest_education_level=highest_edu,
            source_format=loaded.validated_file.format,
            parse_warnings=all_warnings,
            injection_indicators=injection_codes,
            parser_version=PARSER_VERSION,
        )

        logger.info(
            "Parsed candidate cid=%s name=%s skills=%d exp_years=%s edu=%s warnings=%d",
            candidate.candidate_id,
            candidate.name or "None",
            len(candidate.skills),
            str(candidate.total_experience_years),
            candidate.highest_education_level.name,
            len(candidate.parse_warnings),
        )

        return candidate


def _assess_text_quality(text: str) -> ParseWarning | None:
    """Detect garbled, corrupted, or low-quality text representations."""
    if not text:
        return None

    # Check ratio of alphanumeric characters to total characters
    total_chars = len(text)
    alnum_chars = sum(1 for c in text if c.isalnum() or c.isspace())
    ratio = alnum_chars / total_chars if total_chars > 0 else 1.0

    if ratio < 0.60:
        return ParseWarning(
            code="LOW_TEXT_QUALITY",
            message="Extracted text has a high density of non-alphanumeric symbols or encoding noise.",
            field="raw_text",
        )

    # Check average line length across multi-line documents
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 20:
        avg_line_len = sum(len(line) for line in lines) / len(lines)
        if avg_line_len < 5:
            return ParseWarning(
                code="LOW_TEXT_QUALITY",
                message="Extracted text contains unusually short lines suggesting broken layout or OCR fragmentation.",
                field="raw_text",
            )

    return None
