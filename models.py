"""Shared data models for the water meter analysis application."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class AnalysisConfig:
    """Configurable thresholds used by the analysis state machine."""

    max_oscillation: float = 0.3
    normal_opening_volume: float = 0.3
    normal_opening_window_minutes: float = 30.0
    slow_opening_volume: float = 0.5
    slow_opening_window_minutes: float = 180.0
    slow_opening_min_increments: int = 4
    rapid_single_increment: float = 0.5
    closure_confirmation_minutes: float = 90.0
    closure_tolerance: float = 0.1
    high_reliability_max_interval_minutes: float = 30.0


@dataclass
class CounterReading:
    """One timestamped counter reading, including preprocessing fields."""

    original_row: int
    timestamp: datetime
    original_value: float
    corrected_value: float | None = None
    delta: float = 0.0
    interval_minutes: float | None = None
    anomaly: str = ""
    segment: int = 1


@dataclass
class OpeningEvent:
    """Detected water opening/closure event."""

    number: int
    opening_time: datetime
    initial_counter: float
    closing_time: datetime
    final_counter: float
    consumption: float
    duration_seconds: int
    opening_type: str
    reliability: str
    positive_increments: int
    max_interval_minutes: float
    notes: str
    opening_row: int
    closing_row: int
    closure_confirmed: bool = True


@dataclass
class IsolatedIncrement:
    """Positive counter movement that did not meet opening criteria."""

    number: int
    start_time: datetime
    start_counter: float
    end_time: datetime
    end_counter: float
    increment: float
    positive_steps: int
    reason: str
    original_rows: str


@dataclass
class AnalysisResult:
    """Complete analysis output consumed by report generators."""

    source_file: Path
    rtu_name: str
    counter_column: str
    readings: list[CounterReading]
    events: list[OpeningEvent]
    isolated_increments: list[IsolatedIncrement]
    config: AnalysisConfig
    discarded_rows: int = 0
    invalid_row_notes: list[str] = field(default_factory=list)

    @property
    def start_time(self) -> datetime | None:
        """Return the first reading timestamp."""

        return self.readings[0].timestamp if self.readings else None

    @property
    def end_time(self) -> datetime | None:
        """Return the last reading timestamp."""

        return self.readings[-1].timestamp if self.readings else None

    @property
    def total_consumption(self) -> float:
        """Return total consumption across detected events."""

        return sum(event.consumption for event in self.events)

    @property
    def reset_count(self) -> int:
        """Return the number of detected resets or major anomalies."""

        return sum(1 for reading in self.readings if "reset" in reading.anomaly.lower())
