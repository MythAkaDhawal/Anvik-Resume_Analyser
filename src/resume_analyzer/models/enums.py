"""Enumerations defining system-wide provenance, education, matching, and scoring bands.

All string enums inherit from str and Enum for transparent JSON serialization.
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Provenance(str, Enum):
    """Provenance attribution label for every reported fact or interpretation."""

    EXTRACTED_RULE = "extracted_rule"
    EXTRACTED_AI = "extracted_ai"
    COMPUTED = "computed"
    AI_GENERATED = "ai_generated"


class EducationLevel(IntEnum):
    """Ordinal hierarchy of educational attainment."""

    UNSPECIFIED = 0
    HIGH_SCHOOL = 1
    DIPLOMA = 2  # Diploma, Associate degree, Polytechnic
    BACHELOR = 3
    MASTER = 4
    DOCTORATE = 5

    @classmethod
    def from_string(cls, val: str | int | EducationLevel) -> EducationLevel:
        """Parse string or integer into an EducationLevel member."""
        if isinstance(val, EducationLevel):
            return val
        if isinstance(val, int):
            return cls(val)
        val_str = str(val).strip().upper()
        mapping = {
            "UNSPECIFIED": cls.UNSPECIFIED,
            "0": cls.UNSPECIFIED,
            "HIGH_SCHOOL": cls.HIGH_SCHOOL,
            "HIGH SCHOOL": cls.HIGH_SCHOOL,
            "1": cls.HIGH_SCHOOL,
            "DIPLOMA": cls.DIPLOMA,
            "ASSOCIATE": cls.DIPLOMA,
            "2": cls.DIPLOMA,
            "BACHELOR": cls.BACHELOR,
            "BACHELORS": cls.BACHELOR,
            "3": cls.BACHELOR,
            "MASTER": cls.MASTER,
            "MASTERS": cls.MASTER,
            "4": cls.MASTER,
            "DOCTORATE": cls.DOCTORATE,
            "PHD": cls.DOCTORATE,
            "5": cls.DOCTORATE,
        }
        if val_str in mapping:
            return mapping[val_str]
        try:
            return cls(int(val_str))
        except (ValueError, TypeError):
            return cls.UNSPECIFIED


class MatchType(str, Enum):
    """Type of match determined between candidate skill and job requirement."""

    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    NONE = "none"


class FitBand(str, Enum):
    """Coarse alignment categories computed from rounded total score."""

    STRONG = "strong"
    MODERATE = "moderate"
    LIMITED = "limited"
    LOW = "low"

    @property
    def display_name(self) -> str:
        """User-facing friendly display name."""
        names = {
            FitBand.STRONG: "Strong alignment",
            FitBand.MODERATE: "Moderate alignment",
            FitBand.LIMITED: "Limited alignment",
            FitBand.LOW: "Low alignment",
        }
        return names.get(self, "Unknown alignment")


class FeatureStatus(str, Enum):
    """Status of an AI augmentation feature invocation."""

    OK = "ok"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    BLOCKED = "blocked"


class ComponentStatus(str, Enum):
    """Evaluation status of individual scoring dimensions."""

    EVALUATED = "evaluated"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
    NOT_USED = "not_used"
