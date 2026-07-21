"""CSV loading and normalization for counter readings."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover - dependency is declared in requirements.
    pd = None

from models import CounterReading

LOGGER = logging.getLogger(__name__)

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
DELIMITERS = (";", ",", "\t")
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass(frozen=True)
class CsvLoadResult:
    """Result of loading a CSV file."""

    readings: list[CounterReading]
    discarded_rows: int
    invalid_row_notes: list[str]
    headers: list[str]


@dataclass(frozen=True)
class CsvPreview:
    """Lightweight CSV metadata used by the UI."""

    headers: list[str]
    counter_candidates: list[str]
    suggested_rtu: str


def preview_csv(path: Path) -> CsvPreview:
    """Read only CSV headers and infer counter column candidates."""

    encoding, text = _read_text(path)
    delimiter = detect_delimiter(text)
    LOGGER.info("Previewing CSV %s with encoding %s and delimiter %r", path, encoding, delimiter)
    sample = text.splitlines()
    if not sample:
        return CsvPreview([], [], "")
    reader = csv.reader([sample[0]], delimiter=delimiter)
    headers = next(reader, [])
    candidates = find_counter_columns(headers)
    return CsvPreview(headers, candidates, infer_rtu_name(candidates[0]) if candidates else "")


def load_counter_readings(path: Path, counter_column: str) -> CsvLoadResult:
    """Load, parse and sort counter readings from a CSV file."""

    encoding, text = _read_text(path)
    delimiter = detect_delimiter(text)
    rows = _read_rows(text, delimiter)
    if not rows:
        raise ValueError("CSV vuoto.")

    headers = rows[0]
    if counter_column not in headers:
        raise ValueError(f"Colonna contatore non trovata: {counter_column}")

    date_column = find_date_column(headers)
    if not date_column:
        raise ValueError("Colonna date non trovata.")

    raw_records = []
    invalid_notes: list[str] = []
    for line_number, row in enumerate(rows[1:], start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        record = {header: row[index].strip() if index < len(row) else "" for index, header in enumerate(headers)}
        try:
            timestamp = parse_english_timestamp(record.get(date_column, ""))
            value = parse_number(record.get(counter_column, ""))
        except ValueError as exc:
            invalid_notes.append(f"Riga {line_number}: {exc}")
            LOGGER.warning("Discarding row %s: %s", line_number, exc)
            continue
        raw_records.append(
            {
                "original_row": line_number,
                "timestamp": timestamp,
                "original_value": value,
            }
        )

    if not raw_records:
        raise ValueError("Nessuna lettura valida trovata nel CSV.")

    if pd is not None:
        frame = pd.DataFrame(raw_records).sort_values(["timestamp", "original_row"])
        records = frame.to_dict("records")
    else:
        records = sorted(raw_records, key=lambda item: (item["timestamp"], item["original_row"]))

    readings = [
        CounterReading(
            original_row=int(record["original_row"]),
            timestamp=record["timestamp"],
            original_value=float(record["original_value"]),
        )
        for record in records
    ]
    return CsvLoadResult(
        readings=readings,
        discarded_rows=len(invalid_notes),
        invalid_row_notes=invalid_notes,
        headers=headers,
    )


def detect_delimiter(text: str) -> str:
    """Detect the most likely CSV delimiter."""

    first_lines = [line for line in text.splitlines()[:10] if line.strip()]
    if not first_lines:
        return ";"
    scores = {delimiter: sum(line.count(delimiter) for line in first_lines) for delimiter in DELIMITERS}
    return max(scores, key=scores.get)


def find_counter_columns(headers: list[str]) -> list[str]:
    """Return columns whose name looks like a V1Counter column."""

    return [header for header in headers if "v1counter" in header.lower()]


def find_date_column(headers: list[str]) -> str | None:
    """Find the most likely date/time column."""

    for header in headers:
        lowered = header.lower()
        if lowered in {"dates", "date", "data", "timestamp", "time"}:
            return header
    for header in headers:
        lowered = header.lower()
        if "date" in lowered or "time" in lowered or "data" in lowered:
            return header
    return headers[0] if headers else None


def infer_rtu_name(counter_column: str) -> str:
    """Infer the RTU/GDC name from a counter column label."""

    if " - " in counter_column:
        return counter_column.split(" - ", 1)[0].strip()
    return re.sub(r"\s*v1counter\s*", "", counter_column, flags=re.IGNORECASE).strip(" -_")


def parse_number(value: str) -> float:
    """Parse a counter value supporting comma or dot decimals."""

    cleaned = value.strip().replace(" ", "")
    if not cleaned:
        raise ValueError("valore contatore vuoto")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"valore contatore non numerico: {value}") from exc


def parse_english_timestamp(value: str) -> datetime:
    """Parse timestamps such as 'Jun 10 2026, 17:07:57.636' without OS locale."""

    cleaned = " ".join(value.strip().split())
    pattern = (
        r"^(?P<month>[A-Za-z]{3})\s+"
        r"(?P<day>\d{1,2})\s+"
        r"(?P<year>\d{4}),?\s+"
        r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})"
        r"(?:\.(?P<fraction>\d{1,6}))?$"
    )
    match = re.match(pattern, cleaned)
    if not match:
        raise ValueError(f"data non valida: {value}")
    month_key = match.group("month").lower()
    if month_key not in MONTHS:
        raise ValueError(f"mese non riconosciuto: {value}")
    fraction = (match.group("fraction") or "0").ljust(6, "0")[:6]
    return datetime(
        year=int(match.group("year")),
        month=MONTHS[month_key],
        day=int(match.group("day")),
        hour=int(match.group("hour")),
        minute=int(match.group("minute")),
        second=int(match.group("second")),
        microsecond=int(fraction),
    )


def _read_text(path: Path) -> tuple[str, str]:
    for encoding in ENCODINGS:
        try:
            return encoding, path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Impossibile leggere il CSV con le codifiche supportate.")


def _read_rows(text: str, delimiter: str) -> list[list[str]]:
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    return [row for row in reader]
