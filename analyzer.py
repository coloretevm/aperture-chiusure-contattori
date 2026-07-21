"""State-machine based detection of water meter openings and closures."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from models import AnalysisConfig, AnalysisResult, CounterReading, IsolatedIncrement, OpeningEvent

LOGGER = logging.getLogger(__name__)

STATE_CLOSED = "CHIUSO"
STATE_POSSIBLE_OPENING = "POSSIBILE_APERTURA"
STATE_OPEN = "APERTO"


def analyze_readings(
    readings: list[CounterReading],
    config: AnalysisConfig,
    source_file: Path,
    rtu_name: str,
    counter_column: str,
    discarded_rows: int = 0,
    invalid_row_notes: list[str] | None = None,
) -> AnalysisResult:
    """Preprocess readings and detect openings, closures and isolated increments."""

    if not readings:
        raise ValueError("Nessuna lettura da analizzare.")

    ordered = sorted(readings, key=lambda item: (item.timestamp, item.original_row))
    processed = preprocess_readings(ordered, config)
    events, isolated = detect_openings(processed, config)
    return AnalysisResult(
        source_file=source_file,
        rtu_name=rtu_name,
        counter_column=counter_column,
        readings=processed,
        events=events,
        isolated_increments=isolated,
        config=config,
        discarded_rows=discarded_rows,
        invalid_row_notes=invalid_row_notes or [],
    )


def preprocess_readings(readings: list[CounterReading], config: AnalysisConfig) -> list[CounterReading]:
    """Calculate corrected counter values, deltas, intervals, anomalies and segments."""

    processed: list[CounterReading] = []
    segment = 1
    previous_corrected: float | None = None
    previous_timestamp: datetime | None = None

    for index, source in enumerate(readings):
        reading = CounterReading(
            original_row=source.original_row,
            timestamp=source.timestamp,
            original_value=source.original_value,
        )
        if previous_timestamp is not None:
            reading.interval_minutes = (reading.timestamp - previous_timestamp).total_seconds() / 60

        if index == 0 or previous_corrected is None:
            reading.corrected_value = reading.original_value
            reading.delta = 0.0
            reading.segment = segment
        else:
            raw_delta = reading.original_value - previous_corrected
            if raw_delta >= 0:
                reading.corrected_value = reading.original_value
                reading.delta = raw_delta
                reading.segment = segment
            elif abs(raw_delta) <= config.max_oscillation:
                reading.corrected_value = previous_corrected
                reading.delta = 0.0
                reading.anomaly = "Oscillazione corretta"
                reading.segment = segment
            else:
                segment += 1
                reading.corrected_value = reading.original_value
                reading.delta = 0.0
                reading.anomaly = "Possibile reset o anomalia del contatore"
                reading.segment = segment

        previous_corrected = reading.corrected_value
        previous_timestamp = reading.timestamp
        processed.append(reading)

    return processed


def detect_openings(
    readings: list[CounterReading],
    config: AnalysisConfig,
) -> tuple[list[OpeningEvent], list[IsolatedIncrement]]:
    """Detect opening events with a CHIUSO/POSSIBILE_APERTURA/APERTO state machine."""

    events: list[OpeningEvent] = []
    isolated: list[IsolatedIncrement] = []
    event_number = 1
    isolated_number = 1

    for segment_readings in _split_by_segment(readings):
        state = STATE_CLOSED
        candidate: dict[str, object] | None = None
        open_event: dict[str, object] | None = None
        index = 1

        while index < len(segment_readings):
            reading = segment_readings[index]
            delta = max(0.0, reading.delta)

            if state == STATE_CLOSED:
                if delta > 0:
                    candidate = _new_candidate(segment_readings, index)
                    _add_positive(candidate, index, delta)
                    opening_type = _candidate_opening_type(candidate, segment_readings, config)
                    if opening_type:
                        state = STATE_OPEN
                        open_event = _candidate_to_open_event(candidate, opening_type)
                    else:
                        state = STATE_POSSIBLE_OPENING

            elif state == STATE_POSSIBLE_OPENING and candidate is not None:
                if delta > 0:
                    _add_positive(candidate, index, delta)
                    opening_type = _candidate_opening_type(candidate, segment_readings, config)
                    if opening_type:
                        state = STATE_OPEN
                        open_event = _candidate_to_open_event(candidate, opening_type)
                elif _minutes_since_last_positive(candidate, segment_readings, index) >= config.closure_confirmation_minutes:
                    isolated.append(_candidate_to_isolated(isolated_number, candidate, segment_readings))
                    isolated_number += 1
                    candidate = None
                    state = STATE_CLOSED

            elif state == STATE_OPEN and open_event is not None:
                if delta > 0:
                    _extend_open_event(open_event, index, delta)
                elif _minutes_since_open_event_variation(open_event, segment_readings, index) >= config.closure_confirmation_minutes:
                    events.append(_finalize_event(event_number, open_event, segment_readings, config, True))
                    event_number += 1
                    open_event = None
                    candidate = None
                    state = STATE_CLOSED

            index += 1

        if state == STATE_POSSIBLE_OPENING and candidate is not None:
            isolated.append(_candidate_to_isolated(isolated_number, candidate, segment_readings))
            isolated_number += 1
        elif state == STATE_OPEN and open_event is not None:
            events.append(_finalize_event(event_number, open_event, segment_readings, config, False))
            event_number += 1

    return events, isolated


def _split_by_segment(readings: list[CounterReading]) -> list[list[CounterReading]]:
    segments: list[list[CounterReading]] = []
    current_segment: int | None = None
    current: list[CounterReading] = []
    for reading in readings:
        if current_segment is None or reading.segment == current_segment:
            current.append(reading)
            current_segment = reading.segment
        else:
            if len(current) > 1:
                segments.append(current)
            current = [reading]
            current_segment = reading.segment
    if len(current) > 1:
        segments.append(current)
    return segments


def _new_candidate(readings: list[CounterReading], positive_index: int) -> dict[str, object]:
    start_index = max(0, positive_index - 1)
    return {
        "start_index": start_index,
        "last_positive_index": positive_index,
        "positive_indices": [],
        "consumption": 0.0,
        "max_single_delta": 0.0,
    }


def _add_positive(candidate: dict[str, object], index: int, delta: float) -> None:
    positive_indices = candidate["positive_indices"]
    assert isinstance(positive_indices, list)
    positive_indices.append(index)
    candidate["last_positive_index"] = index
    candidate["consumption"] = float(candidate["consumption"]) + delta
    candidate["max_single_delta"] = max(float(candidate["max_single_delta"]), delta)


def _candidate_opening_type(
    candidate: dict[str, object],
    readings: list[CounterReading],
    config: AnalysisConfig,
) -> str | None:
    start = readings[int(candidate["start_index"])]
    last = readings[int(candidate["last_positive_index"])]
    minutes = (last.timestamp - start.timestamp).total_seconds() / 60
    consumption = float(candidate["consumption"])
    positives = len(candidate["positive_indices"])

    if float(candidate["max_single_delta"]) >= config.rapid_single_increment:
        return "APERTURA RAPIDA"
    if consumption >= config.normal_opening_volume and minutes <= config.normal_opening_window_minutes:
        return "APERTURA NORMALE"
    if (
        consumption >= config.slow_opening_volume
        and minutes <= config.slow_opening_window_minutes
        and positives >= config.slow_opening_min_increments
    ):
        return "APERTURA A BASSA PORTATA"
    return None


def _candidate_to_open_event(candidate: dict[str, object], opening_type: str) -> dict[str, object]:
    return {
        "start_index": candidate["start_index"],
        "last_positive_index": candidate["last_positive_index"],
        "positive_indices": list(candidate["positive_indices"]),
        "consumption": candidate["consumption"],
        "opening_type": opening_type,
    }


def _extend_open_event(open_event: dict[str, object], index: int, delta: float) -> None:
    positive_indices = open_event["positive_indices"]
    assert isinstance(positive_indices, list)
    positive_indices.append(index)
    open_event["last_positive_index"] = index
    open_event["consumption"] = float(open_event["consumption"]) + delta


def _minutes_since_last_positive(
    candidate: dict[str, object],
    readings: list[CounterReading],
    index: int,
) -> float:
    last = readings[int(candidate["last_positive_index"])]
    return (readings[index].timestamp - last.timestamp).total_seconds() / 60


def _minutes_since_open_event_variation(
    open_event: dict[str, object],
    readings: list[CounterReading],
    index: int,
) -> float:
    last = readings[int(open_event["last_positive_index"])]
    return (readings[index].timestamp - last.timestamp).total_seconds() / 60


def _candidate_to_isolated(
    number: int,
    candidate: dict[str, object],
    readings: list[CounterReading],
) -> IsolatedIncrement:
    start = readings[int(candidate["start_index"])]
    end = readings[int(candidate["last_positive_index"])]
    rows = [str(readings[index].original_row) for index in candidate["positive_indices"]]
    return IsolatedIncrement(
        number=number,
        start_time=start.timestamp,
        start_counter=float(start.corrected_value or 0.0),
        end_time=end.timestamp,
        end_counter=float(end.corrected_value or 0.0),
        increment=max(0.0, float(candidate["consumption"])),
        positive_steps=len(candidate["positive_indices"]),
        reason="Incremento insufficiente per confermare una apertura",
        original_rows=", ".join(rows),
    )


def _finalize_event(
    number: int,
    open_event: dict[str, object],
    readings: list[CounterReading],
    config: AnalysisConfig,
    closure_confirmed: bool,
) -> OpeningEvent:
    start = readings[int(open_event["start_index"])]
    end = readings[int(open_event["last_positive_index"])]
    duration_seconds = max(0, int((end.timestamp - start.timestamp).total_seconds()))
    intervals = [
        reading.interval_minutes or 0.0
        for reading in readings[int(open_event["start_index"]) + 1 : int(open_event["last_positive_index"]) + 1]
    ]
    max_interval = max(intervals, default=0.0)
    anomalies = [
        reading.anomaly
        for reading in readings[int(open_event["start_index"]) : int(open_event["last_positive_index"]) + 1]
        if reading.anomaly
    ]
    reliability, notes = _classify_reliability(closure_confirmed, max_interval, anomalies, config)
    return OpeningEvent(
        number=number,
        opening_time=start.timestamp,
        initial_counter=float(start.corrected_value or 0.0),
        closing_time=end.timestamp,
        final_counter=float(end.corrected_value or 0.0),
        consumption=max(0.0, float(end.corrected_value or 0.0) - float(start.corrected_value or 0.0)),
        duration_seconds=duration_seconds,
        opening_type=str(open_event["opening_type"]),
        reliability=reliability,
        positive_increments=len(open_event["positive_indices"]),
        max_interval_minutes=max_interval,
        notes=notes,
        opening_row=start.original_row,
        closing_row=end.original_row,
        closure_confirmed=closure_confirmed,
    )


def _classify_reliability(
    closure_confirmed: bool,
    max_interval: float,
    anomalies: list[str],
    config: AnalysisConfig,
) -> tuple[str, str]:
    if not closure_confirmed:
        return "DA VERIFICARE", "File terminato prima della conferma di chiusura"
    if any("reset" in anomaly.lower() for anomaly in anomalies):
        return "DA VERIFICARE", "Reset o anomalia importante dentro l'evento"
    if max_interval > config.high_reliability_max_interval_minutes:
        return "MEDIA", "Intervallo tra messaggi superiore alla soglia per affidabilita alta"
    if anomalies:
        return "MEDIA", "; ".join(sorted(set(anomalies)))
    return "ALTA", "Apertura e chiusura confermate"
