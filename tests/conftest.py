"""Shared test fixtures for Intelligent Resume Analyzer.

Provides cache reset, deterministic reference dates, isolated temporary directories,
and sample configuration fixtures.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date
from pathlib import Path

import pytest

from resume_analyzer.config.settings import clear_settings_cache


@pytest.fixture(autouse=True)
def reset_caches() -> Generator[None, None, None]:
    """Ensure all LRU caches are cleared before and after each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def reference_date() -> date:
    """Provide a fixed reference date (2026-11-07) for deterministic date arithmetic."""
    return date(2026, 11, 7)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide an isolated temporary directory."""
    return tmp_path


@pytest.fixture
def valid_config_yaml(tmp_path: Path) -> Path:
    """Create a temporary valid config.yaml file."""
    config_content = """
app:
  name: "Intelligent Resume Analyzer Test"
  version: "0.1.0"
  data_dir: "data"

files:
  max_size_mb: 5
  max_pdf_pages: 20
  max_docx_uncompressed_mb: 25
  min_text_chars: 50
  max_text_chars: 100000
  allowed_extensions:
    - ".pdf"
    - ".docx"
    - ".txt"
  store_uploaded_files: false

fuzzy:
  enabled: true
  threshold: 85.0
  min_length: 4

scoring:
  strategy: "weighted"
  unknown_policy: "exclude"
  weights:
    required_skills: 0.50
    experience: 0.20
    education: 0.15
    optional_skills: 0.15
  bands:
    strong_min: 80.0
    moderate_min: 60.0
    limited_min: 40.0

ai:
  enabled: false
  provider: "null"
  model: "gemini-1.5-flash"
  temperature: 0.1
  max_output_tokens: 2048
  timeout_s: 30.0
  base_url: null
  question_count: 8
  features:
    extraction: true
    categorization: true
    explanation: true
    recommendations: false
    interview_questions: false

storage:
  results_dir: "data/results"
  reports_dir: "data/reports"
  feedback_dir: "data/feedback"
  store_raw_text: false
  retention_days: 90

logging:
  level: "INFO"
  log_dir: "logs"
  file_name: "test_analyzer.log"
  max_bytes: 10485760
  backup_count: 3
"""
    config_file = tmp_path / "valid_config.yaml"
    config_file.write_text(config_content.strip(), encoding="utf-8")
    return config_file
