from __future__ import annotations

from csv_reader import load_counter_readings, parse_english_timestamp, parse_number, preview_csv


def test_parse_english_timestamp_preserves_milliseconds() -> None:
    parsed = parse_english_timestamp("Jun 10 2026, 17:07:57.636")

    assert parsed.year == 2026
    assert parsed.month == 6
    assert parsed.microsecond == 636000


def test_csv_with_comma_decimal(tmp_path) -> None:
    path = tmp_path / "comma.csv"
    path.write_text("Dates;CBG_0087 - V1Counter\nJun 10 2026, 10:00:00.000;0,3\n", encoding="utf-8")

    result = load_counter_readings(path, "CBG_0087 - V1Counter")

    assert result.readings[0].original_value == 0.3


def test_csv_with_unordered_rows_is_sorted(tmp_path) -> None:
    path = tmp_path / "unordered.csv"
    path.write_text(
        "Dates;CBG_0087 - V1Counter\n"
        "Jun 10 2026, 10:10:00.000;0.4\n"
        "Jun 10 2026, 10:00:00.000;0.3\n",
        encoding="utf-8",
    )

    result = load_counter_readings(path, "CBG_0087 - V1Counter")

    assert [reading.original_row for reading in result.readings] == [3, 2]


def test_preview_detects_v1counter_and_rtu(tmp_path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("Dates;CBG_0087 - V1Counter\nJun 10 2026, 10:00:00.000;0.3\n", encoding="utf-8")

    preview = preview_csv(path)

    assert preview.counter_candidates == ["CBG_0087 - V1Counter"]
    assert preview.suggested_rtu == "CBG_0087"


def test_parse_number_supports_common_formats() -> None:
    assert parse_number("1,2") == 1.2
    assert parse_number("1.2") == 1.2
    assert parse_number("1.234,5") == 1234.5
