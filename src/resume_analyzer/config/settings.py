"""Centralized configuration loading, validation, and typed Settings models.

Implements strict validation of config keys, score weights, band thresholds,
and environment variable overrides while ensuring no secrets are exposed.
"""

from __future__ import annotations

import logging
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from resume_analyzer.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class BaseConfigModel(BaseModel):
    """Base model forbidding unexpected extra keys to catch typos."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AppSettings(BaseConfigModel):
    """Application metadata and base paths."""

    name: str = "Intelligent Resume Analyzer"
    version: str = "0.1.0"
    data_dir: Path = Path("data")


class FileSettings(BaseConfigModel):
    """Constraints and settings for file validation and ingestion."""

    max_size_mb: int = Field(default=5, gt=0)
    max_pdf_pages: int = Field(default=20, gt=0)
    max_docx_uncompressed_mb: int = Field(default=25, gt=0)
    min_text_chars: int = Field(default=50, gt=0)
    max_text_chars: int = Field(default=100000, gt=0)
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".txt"]
    )
    store_uploaded_files: bool = False

    @model_validator(mode="after")
    def validate_char_limits(self) -> FileSettings:
        """Validate text character limits."""
        if self.max_text_chars <= self.min_text_chars:
            raise ValueError(
                f"max_text_chars ({self.max_text_chars}) must be greater than "
                f"min_text_chars ({self.min_text_chars}) (key: files.max_text_chars)"
            )
        return self


class FuzzySettings(BaseConfigModel):
    """Configuration for fuzzy matching logic."""

    enabled: bool = True
    threshold: float = Field(default=85.0, ge=0.0, le=100.0)
    min_length: int = Field(default=4, gt=0)


class ScoreWeights(BaseConfigModel):
    """Configurable weights for weighted scoring strategy."""

    required_skills: float = Field(default=0.50, ge=0.0, le=1.0)
    experience: float = Field(default=0.20, ge=0.0, le=1.0)
    education: float = Field(default=0.15, ge=0.0, le=1.0)
    optional_skills: float = Field(default=0.15, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_sum(self) -> ScoreWeights:
        """Verify that score weights sum exactly to 1.0 within floating tolerance."""
        total = (
            self.required_skills
            + self.experience
            + self.education
            + self.optional_skills
        )
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(
                f"Score weights must sum to 1.0 ± 1e-6, got {total:.6f} "
                "(key: scoring.weights)"
            )
        return self


class BandThresholds(BaseConfigModel):
    """Score thresholds defining candidate fit bands."""

    strong_min: float = Field(default=80.0, ge=0.0, le=100.0)
    moderate_min: float = Field(default=60.0, ge=0.0, le=100.0)
    limited_min: float = Field(default=40.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_order(self) -> BandThresholds:
        """Verify strict descending order of band thresholds."""
        if not (100.0 >= self.strong_min > self.moderate_min > self.limited_min > 0.0):
            raise ValueError(
                f"Band thresholds must satisfy 100 >= strong_min ({self.strong_min}) "
                f"> moderate_min ({self.moderate_min}) > limited_min ({self.limited_min}) > 0 "
                "(key: scoring.bands)"
            )
        return self


class ScoringSettings(BaseConfigModel):
    """Configuration for scoring strategies and policies."""

    strategy: Literal["basic", "weighted"] = "weighted"
    unknown_policy: Literal["exclude", "zero"] = "exclude"
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    bands: BandThresholds = Field(default_factory=BandThresholds)


class AIFeatureSettings(BaseConfigModel):
    """Toggles for individual AI augmentation features."""

    extraction: bool = True
    categorization: bool = True
    explanation: bool = True
    recommendations: bool = False
    interview_questions: bool = False


class AISettings(BaseConfigModel):
    """AI provider and inference parameters. Never stores API keys."""

    enabled: bool = False
    provider: Literal["null", "gemini", "ollama", "openai_compatible", "fake"] = "null"
    model: str = "gemini-1.5-flash"
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=2048, gt=0)
    timeout_s: float = Field(default=30.0, gt=0.0)
    base_url: str | None = None
    question_count: int = Field(default=8, ge=5, le=12)
    features: AIFeatureSettings = Field(default_factory=AIFeatureSettings)


class StorageSettings(BaseConfigModel):
    """Paths and policies for persistence and retention."""

    results_dir: Path = Path("data/results")
    reports_dir: Path = Path("data/reports")
    feedback_dir: Path = Path("data/feedback")
    store_raw_text: bool = False
    retention_days: int = Field(default=90, gt=0)


class LoggingSettings(BaseConfigModel):
    """Logging level, rotation, and output parameters."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_dir: Path = Path("logs")
    file_name: str = "resume_analyzer.log"
    max_bytes: int = Field(default=10485760, gt=0)  # 10 MB
    backup_count: int = Field(default=5, ge=1)


class Settings(BaseConfigModel):
    """Root configuration holding all typed subsystem settings."""

    app: AppSettings = Field(default_factory=AppSettings)
    files: FileSettings = Field(default_factory=FileSettings)
    fuzzy: FuzzySettings = Field(default_factory=FuzzySettings)
    scoring: ScoringSettings = Field(default_factory=ScoringSettings)
    ai: AISettings = Field(default_factory=AISettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


def _format_validation_key(loc: tuple[Any, ...]) -> str:
    """Format Pydantic error loc tuple into a dot-separated string."""
    return ".".join(str(item) for item in loc)


def load_settings(path: Path | str | None = None) -> Settings:
    """Load and validate configuration from YAML file and environment overrides.

    Precedence: defaults < YAML file < environment variables.

    Args:
        path: Optional explicit path to configuration YAML file.

    Returns:
        Validated Settings instance.

    Raises:
        ConfigurationError: If file not found (when explicitly given) or if
            configuration values violate schema/bounds.
    """
    explicitly_provided = path is not None
    target_path: Path | None = None

    if explicitly_provided:
        target_path = Path(path)  # type: ignore[arg-type]
        if not target_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {target_path}",
                key="config_path",
            )
    else:
        env_config = os.getenv("RESUME_ANALYZER_CONFIG")
        if env_config:
            target_path = Path(env_config)
            if not target_path.exists():
                raise ConfigurationError(
                    f"Configuration file specified in RESUME_ANALYZER_CONFIG not found: {target_path}",
                    key="RESUME_ANALYZER_CONFIG",
                )
        else:
            default_path = Path("config/config.yaml")
            if default_path.exists():
                target_path = default_path
            else:
                logger.warning(
                    "Default configuration file %s not found. Falling back to defaults.",
                    default_path,
                )

    raw_data: dict[str, Any] = {}
    if target_path and target_path.exists():
        try:
            with open(target_path, encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if content is not None:
                    if not isinstance(content, dict):
                        raise ConfigurationError(
                            f"Configuration root in {target_path} must be a mapping, got {type(content).__name__}",
                            key="root",
                        )
                    raw_data = content
        except yaml.YAMLError as err:
            raise ConfigurationError(
                f"YAML parsing error in {target_path}: {err}",
                key="yaml_syntax",
            ) from err

    # Validate raw data through Pydantic model
    try:
        settings = Settings.model_validate(raw_data)
    except ValidationError as val_err:
        first_error = val_err.errors()[0]
        key = _format_validation_key(first_error["loc"])
        msg = first_error["msg"]
        raise ConfigurationError(
            f"Invalid configuration for '{key}': {msg}",
            key=key,
            details={"errors": val_err.errors()},
        ) from val_err

    # Apply environment variable overrides
    env_data_dir = os.getenv("RESUME_ANALYZER_DATA_DIR")
    if env_data_dir:
        new_data_dir = Path(env_data_dir)
        settings.app.data_dir = new_data_dir
        settings.storage.results_dir = new_data_dir / "results"
        settings.storage.reports_dir = new_data_dir / "reports"
        settings.storage.feedback_dir = new_data_dir / "feedback"

    env_log_level = os.getenv("RESUME_ANALYZER_LOG_LEVEL")
    if env_log_level:
        norm_level = env_log_level.strip().upper()
        if norm_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            settings.logging.level = norm_level  # type: ignore[assignment]
        else:
            raise ConfigurationError(
                f"Invalid log level in RESUME_ANALYZER_LOG_LEVEL: {env_log_level}",
                key="RESUME_ANALYZER_LOG_LEVEL",
            )

    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance for application entry points.

    Returns:
        Cached Settings instance.
    """
    return load_settings()


def clear_settings_cache() -> None:
    """Clear cached settings instance (used in tests and dynamic reload)."""
    get_settings.cache_clear()


def config_snapshot(settings: Settings) -> dict[str, Any]:
    """Extract a safe, serializable snapshot of analysis configuration.

    Guarantees no API keys, credentials, or sensitive secrets are included.

    Args:
        settings: Active Settings instance.

    Returns:
        Dictionary suitable for embedding in AnalysisReport and persisting.
    """
    return {
        "strategy": settings.scoring.strategy,
        "unknown_policy": settings.scoring.unknown_policy,
        "weights": settings.scoring.weights.model_dump(),
        "bands": settings.scoring.bands.model_dump(),
        "fuzzy": settings.fuzzy.model_dump(),
        "ai": {
            "enabled": settings.ai.enabled,
            "provider": settings.ai.provider,
            "model": settings.ai.model,
        },
    }
