from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from analyzer import analyze_readings, preprocess_readings
from models import AnalysisConfig, CounterReading
from utils import format_duration


def reading(row: int, timestamp: datetime, value: float) -> CounterReading:
    return CounterReading(original_row=row, timestamp=timestamp, original_value=value)


def run(values: list[tuple[int, float]]) :
    base = datetime(2026, 6, 10, 10, 0, 0, 0)
    readings = [reading(index + 2, base + timedelta(minutes=minute), value) for index, (minute, value) in enumerate(values)]
    return analyze_readings(readings, AnalysisConfig(), Path("input.csv"), "RTU_TEST", "RTU_TEST - V1Counter")


def test_normal_opening() -> None:
    result = run([(0, 1.0), (10, 1.2), (20, 1.3), (40, 1.3), (130, 1.3)])

    assert len(result.events) == 1
    event = result.events[0]
    assert event.opening_type == "APERTURA NORMALE"
    assert round(event.consumption, 1) == 0.3
    assert event.closure_confirmed


def test_slow_opening() -> None:
    result = run([(0, 1.0), (20, 1.1), (55, 1.2), (90, 1.35), (130, 1.5), (220, 1.5)])

    assert len(result.events) == 1
    assert result.events[0].opening_type == "APERTURA A BASSA PORTATA"
    assert result.events[0].positive_increments == 4


def test_rapid_opening() -> None:
    result = run([(0, 1.0), (8, 1.6), (120, 1.6)])

    assert len(result.events) == 1
    assert result.events[0].opening_type == "APERTURA RAPIDA"


def test_isolated_increment_of_point_one() -> None:
    result = run([(0, 1.0), (5, 1.1), (100, 1.1)])

    assert len(result.events) == 0
    assert len(result.isolated_increments) == 1
    assert round(result.isolated_increments[0].increment, 1) == 0.1


def test_negative_oscillation_is_corrected() -> None:
    readings = [
        reading(2, datetime(2026, 6, 10, 10, 0), 2.0),
        reading(3, datetime(2026, 6, 10, 10, 5), 1.9),
    ]

    processed = preprocess_readings(readings, AnalysisConfig())

    assert processed[1].corrected_value == 2.0
    assert processed[1].delta == 0.0
    assert processed[1].anomaly == "Oscillazione corretta"


def test_large_reset_starts_new_segment() -> None:
    readings = [
        reading(2, datetime(2026, 6, 10, 10, 0), 5.0),
        reading(3, datetime(2026, 6, 10, 10, 5), 1.0),
    ]

    processed = preprocess_readings(readings, AnalysisConfig())

    assert processed[1].segment == 2
    assert "reset" in processed[1].anomaly.lower()
    assert processed[1].delta == 0.0


def test_interval_over_30_minutes_sets_medium_reliability() -> None:
    result = run([(0, 1.0), (40, 1.6), (140, 1.6)])

    assert len(result.events) == 1
    assert result.events[0].reliability == "MEDIA"


def test_opening_without_closure_at_end_is_to_verify() -> None:
    result = run([(0, 1.0), (5, 1.6)])

    assert len(result.events) == 1
    assert result.events[0].reliability == "DA VERIFICARE"
    assert not result.events[0].closure_confirmed


def test_known_case_detects_expected_consumption_and_duration() -> None:
    start = datetime(2026, 6, 10, 17, 7, 57, 636000)
    end = datetime(2026, 6, 10, 20, 32, 45, 584000)
    readings = [
        reading(10, datetime(2026, 6, 10, 15, 2, 7, 636000), 0.3),
        reading(11, start, 0.3),
        reading(12, end, 3.2),
        reading(13, end + timedelta(minutes=95), 3.2),
    ]

    result = analyze_readings(readings, AnalysisConfig(), Path("known.csv"), "CBG_0087", "CBG_0087 - V1Counter")

    assert len(result.events) == 1
    event = result.events[0]
    assert event.opening_time == start
    assert event.initial_counter == 0.3
    assert event.closing_time == end
    assert event.final_counter == 3.2
    assert round(event.consumption, 1) == 2.9
    assert format_duration(event.duration_seconds) == "03:24:47"
