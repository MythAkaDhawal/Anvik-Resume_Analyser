"""Resume parsing, section splitting, entity extraction, and PII masking package."""

from __future__ import annotations

from resume_analyzer.parsing.contact_extractor import extract_email, extract_name
from resume_analyzer.parsing.education_parser import (
    detect_education_level,
    parse_education,
)
from resume_analyzer.parsing.experience_parser import (
    compute_duration_months,
    parse_experience,
    total_experience_years,
)
from resume_analyzer.parsing.pii import mask_pii, scan_injection_indicators
from resume_analyzer.parsing.resume_parser import PARSER_VERSION, ResumeParser
from resume_analyzer.parsing.section_splitter import split_sections
from resume_analyzer.parsing.skills_extractor import extract_skills
from resume_analyzer.parsing.text_cleaner import clean_text

__all__ = [
    "PARSER_VERSION",
    "ResumeParser",
    "clean_text",
    "compute_duration_months",
    "detect_education_level",
    "extract_email",
    "extract_name",
    "extract_skills",
    "mask_pii",
    "parse_education",
    "parse_experience",
    "scan_injection_indicators",
    "split_sections",
    "total_experience_years",
]
