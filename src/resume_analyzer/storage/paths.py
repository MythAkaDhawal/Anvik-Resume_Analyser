"""Filesystem safety and identifier validation helpers (TECHNICAL_SPECIFICATION §5.10).

Prevents directory traversal, path injection, and validates report identifiers
against the canonical naming regex (NFR-05).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from resume_analyzer.exceptions import InvalidIdentifierError

REPORT_ID_PATTERN = r"^\d{8}T\d{6}Z_[0-9a-f]{8}_[0-9a-f]{4}$"
REPORT_ID_REGEX = re.compile(REPORT_ID_PATTERN)


def validate_report_id(report_id: str) -> str:
    """Validate that report_id strictly matches canonical regex.

    Args:
        report_id: Proposed report identifier string.

    Returns:
        Validated report identifier string.

    Raises:
        InvalidIdentifierError: If report_id does not conform to regex.
    """
    if not isinstance(report_id, str) or not REPORT_ID_REGEX.match(report_id):
        raise InvalidIdentifierError(str(report_id))
    return report_id


def safe_join(base: Path | str, name: str) -> Path:
    """Safely combine a base directory with an untrusted filename.

    Rejects path separators ('/', '\\'), parent directory references ('..'),
    absolute paths, and ensures the resolved path remains strictly within base.

    Args:
        base: Target directory boundary.
        name: Proposed filename to join.

    Returns:
        Resolved Path inside base.

    Raises:
        InvalidIdentifierError: If path traversal or illegal separators detected.
    """
    if not isinstance(name, str) or not name.strip():
        raise InvalidIdentifierError(str(name))

    # Reject path separators, parent directory traversal tokens, colons and absolute paths
    if (
        "/" in name
        or "\\" in name
        or ".." in name
        or ":" in name
        or Path(name).is_absolute()
        or os.path.isabs(name)
    ):
        raise InvalidIdentifierError(name)

    base_path = Path(base).resolve()
    target = (base_path / name).resolve()

    # Verify target stays strictly inside base
    try:
        target.relative_to(base_path)
    except ValueError:
        raise InvalidIdentifierError(name) from None

    return target
