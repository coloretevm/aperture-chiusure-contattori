"""Utility helpers for logging, formatting and filenames."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path


LOG_DIR = Path("logs")


def setup_logging() -> None:
    """Configure application logging."""

    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=LOG_DIR / "app.log",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        encoding="utf-8",
    )


def sanitize_filename_part(value: str) -> str:
    """Return a filesystem-safe filename component."""

    cleaned = re.sub(r"\s+", "_", value.strip())
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "", cleaned)
    return cleaned or "RTU"


def make_report_base_name(rtu_name: str, start: datetime, end: datetime) -> str:
    """Build the common Excel/PDF report filename without extension."""

    safe_rtu = sanitize_filename_part(rtu_name)
    return (
        f"analisi_aperture_chiusure_{safe_rtu}_"
        f"{start:%Y%m%d}_{end:%Y%m%d}"
    )


def format_datetime(value: datetime | None) -> str:
    """Format a timestamp for human-readable reports."""

    if value is None:
        return ""
    return value.strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]


def format_date(value: datetime | None) -> str:
    """Format a date for report subtitles."""

    if value is None:
        return ""
    return value.strftime("%d/%m/%Y")


def format_duration(total_seconds: int) -> str:
    """Format a duration as HH:MM:SS without wrapping after 24 hours."""

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def median(values: list[float]) -> float | None:
    """Return the median of a numeric list."""

    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
