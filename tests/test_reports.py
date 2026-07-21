from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from analyzer import analyze_readings
from excel_report import create_excel_report
from models import AnalysisConfig, CounterReading
from pdf_report import create_pdf_report


def test_excel_and_pdf_reports_are_created(tmp_path) -> None:
    start = datetime(2026, 6, 10, 17, 7, 57, 636000)
    end = datetime(2026, 6, 10, 20, 32, 45, 584000)
    readings = [
        CounterReading(2, start, 0.3),
        CounterReading(3, end, 3.2),
        CounterReading(4, end + timedelta(minutes=95), 3.2),
    ]
    result = analyze_readings(
        readings,
        AnalysisConfig(),
        Path("known.csv"),
        "CBG_0087",
        "CBG_0087 - V1Counter",
    )

    excel_path = create_excel_report(result, tmp_path)
    pdf_path = create_pdf_report(result, tmp_path)

    assert excel_path.exists()
    assert pdf_path.exists()
    assert excel_path.suffix == ".xlsx"
    assert pdf_path.suffix == ".pdf"
