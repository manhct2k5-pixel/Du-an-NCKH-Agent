"""Locate current reports while retaining read access to archived experiments."""
from __future__ import annotations

from pathlib import Path

from .config import REPORT_DIR, ROOT_DIR


ARCHIVE_REPORT_DIR = ROOT_DIR / "archive" / "artifacts" / "reports"


def existing_report_path(path: str | Path) -> Path:
    """Prefer a current report; use its archived snapshot when it was moved."""
    current = Path(path)
    if not current.is_absolute():
        current = ROOT_DIR / current
    if current.exists():
        return current
    try:
        relative = current.relative_to(REPORT_DIR)
    except ValueError:
        return current
    archived = ARCHIVE_REPORT_DIR / relative
    return archived if archived.is_file() else current
