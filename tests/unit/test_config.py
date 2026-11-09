"""Unit tests for configuration loading, validation, and Settings models (UT-CFG-*)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resume_analyzer.config.settings import (
    Settings,
    config_snapshot,
    load_settings,
)
from resume_analyzer.exceptions import ConfigurationError


def test_default_settings_load_and_sample_yaml(valid_config_yaml: Path) -> None:
    """UT-CFG-01: Verify default settings load and sample config.yaml validates cleanly."""
    settings = load_settings(valid_config_yaml)
    assert settings.app.name == "Intelligent Resume Analyzer Test"
    assert settings.files.max_size_mb == 5
    assert settings.scoring.strategy == "weighted"
    assert settings.scoring.weights.required_skills == 0.50
    assert settings.scoring.bands.strong_min == 80.0
    assert settings.ai.enabled is False
    assert settings.ai.provider == "null"


def test_invalid_weights_sum_raises_configuration_error(tmp_path: Path) -> None:
    """UT-CFG-02: Verify invalid score weights sum raises ConfigurationError naming the key."""
    bad_yaml = tmp_path / "bad_weights.yaml"
    bad_yaml.write_text(
        """
scoring:
  weights:
    required_skills: 0.50
    experience: 0.30
    education: 0.20
    optional_skills: 0.20
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(bad_yaml)

    assert (
        "scoring.weights" in exc_info.value.message
        or exc_info.value.details.get("key") == "scoring.weights"
    )
    assert exc_info.value.error_code == "E-CFG-001"


def test_unordered_band_thresholds_raises_configuration_error(tmp_path: Path) -> None:
    """UT-CFG-02: Verify non-descending band thresholds raise ConfigurationError."""
    bad_yaml = tmp_path / "bad_bands.yaml"
    bad_yaml.write_text(
        """
scoring:
  bands:
    strong_min: 60.0
    moderate_min: 70.0
    limited_min: 40.0
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(bad_yaml)

    assert "scoring.bands" in exc_info.value.message or "scoring.bands" in str(
        exc_info.value
    )
    assert exc_info.value.error_code == "E-CFG-001"


def test_negative_file_limits_raises_configuration_error(tmp_path: Path) -> None:
    """UT-CFG-02: Verify negative file limits raise ConfigurationError."""
    bad_yaml = tmp_path / "bad_file.yaml"
    bad_yaml.write_text(
        """
files:
  max_size_mb: -1
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(bad_yaml)

    assert "files.max_size_mb" in exc_info.value.message or "files.max_size_mb" in str(
        exc_info.value
    )
    assert exc_info.value.error_code == "E-CFG-001"


def test_unknown_scoring_strategy_raises_configuration_error(tmp_path: Path) -> None:
    """UT-CFG-02: Verify unknown scoring strategy name raises ConfigurationError."""
    bad_yaml = tmp_path / "bad_strategy.yaml"
    bad_yaml.write_text(
        """
scoring:
  strategy: "quantum_scoring"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(bad_yaml)

    assert "scoring.strategy" in exc_info.value.message or "scoring.strategy" in str(
        exc_info.value
    )


def test_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-CFG-03: Verify RESUME_ANALYZER_DATA_DIR and RESUME_ANALYZER_LOG_LEVEL overrides."""
    custom_dir = tmp_path / "custom_data"
    monkeypatch.setenv("RESUME_ANALYZER_DATA_DIR", str(custom_dir))
    monkeypatch.setenv("RESUME_ANALYZER_LOG_LEVEL", "DEBUG")

    settings = load_settings()
    assert settings.app.data_dir == custom_dir
    assert settings.storage.results_dir == custom_dir / "results"
    assert settings.storage.reports_dir == custom_dir / "reports"
    assert settings.storage.feedback_dir == custom_dir / "feedback"
    assert settings.logging.level == "DEBUG"


def test_no_api_keys_in_settings_or_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-CFG-03: Verify API keys are never present in Settings or config_snapshot."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyFakeSecretKey123456789")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-FakeOpenAIKey987654321")

    settings = load_settings()
    snapshot = config_snapshot(settings)

    # Convert to string to scan all fields recursively
    settings_dump = str(settings.model_dump())
    snapshot_str = str(snapshot)

    assert "AIza" not in settings_dump
    assert "sk-" not in settings_dump
    assert "api_key" not in settings_dump
    assert "AIza" not in snapshot_str
    assert "sk-" not in snapshot_str
    assert "api_key" not in snapshot_str


def test_missing_config_fallback_and_explicit_not_found(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """UT-CFG-04: Verify missing default file falls back with warning, explicit path raises."""
    non_existent = tmp_path / "does_not_exist.yaml"

    # Explicit missing path must raise ConfigurationError
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(non_existent)
    assert exc_info.value.error_code == "E-CFG-001"

    # Fallback to default when no file exists at default location
    settings = load_settings(path=None)
    assert isinstance(settings, Settings)


def test_unknown_top_level_keys_rejected(tmp_path: Path) -> None:
    """UT-CFG-05: Verify typo protection rejecting unknown top-level keys."""
    bad_yaml = tmp_path / "typo_config.yaml"
    bad_yaml.write_text(
        """
scorring:
  strategy: "weighted"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(bad_yaml)

    assert "scorring" in exc_info.value.message or "scorring" in str(exc_info.value)
