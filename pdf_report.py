"""PDF report generation with ReportLab."""

from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models import AnalysisConfig, AnalysisResult
from utils import format_date, format_datetime, format_duration, make_report_base_name, median


def create_pdf_report(result: AnalysisResult, output_dir: Path, include_original_data: bool = False) -> Path:
    """Create a PDF report and return its path."""

    if result.start_time is None or result.end_time is None:
        raise ValueError("Nessun periodo dati disponibile per il report.")

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{make_report_base_name(result.rtu_name, result.start_time, result.end_time)}.pdf"
    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=1.1 * cm,
        rightMargin=1.1 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = _styles()
    story = []
    story.extend(_summary_story(result, styles))
    story.append(PageBreak())
    story.extend(_events_story(result, styles))
    story.append(PageBreak())
    story.extend(_isolated_story(result, styles))
    story.append(PageBreak())
    story.extend(_logic_story(result.config, styles))
    story.append(PageBreak())
    story.extend(_alerts_story(result, styles))
    if include_original_data:
        story.append(PageBreak())
        story.extend(_original_data_story(result, styles))

    doc.build(story, onFirstPage=_header_footer(result), onLaterPages=_header_footer(result))
    return path


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontSize=18,
            textColor=colors.HexColor("#17365D"),
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "heading": ParagraphStyle(
            "Heading",
            parent=base["Heading2"],
            textColor=colors.HexColor("#17365D"),
            spaceAfter=8,
        ),
        "normal": ParagraphStyle("NormalSmall", parent=base["BodyText"], fontSize=8.5, leading=10),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6.7,
            leading=7.5,
            textColor=colors.white,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontSize=6.7,
            leading=7.8,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
    }


def _summary_story(result: AnalysisResult, styles: dict[str, ParagraphStyle]) -> list:
    intervals = [float(reading.interval_minutes) for reading in result.readings if reading.interval_minutes is not None]
    rows = [
        ["Nome file analizzato", result.source_file.name],
        ["Nome GDC/RTU", result.rtu_name],
        ["Periodo", f"Dal {format_date(result.start_time)} al {format_date(result.end_time)}"],
        ["Messaggi analizzati", str(len(result.readings))],
        ["Righe scartate", str(result.discarded_rows)],
        ["Intervallo mediano tra messaggi (min)", f"{median(intervals) or 0:.1f}"],
        ["Aperture rilevate", str(len(result.events))],
        ["Incrementi isolati", str(len(result.isolated_increments))],
        ["Consumo totale (m3)", f"{result.total_consumption:.1f}"],
        ["Reset o anomalie rilevate", str(result.reset_count)],
    ]
    return [
        Paragraph(f"ANALISI APERTURE E CHIUSURE - RTU {result.rtu_name}", styles["title"]),
        Paragraph(
            f"APERTURE E CHIUSURE RILEVATE DAL {format_date(result.start_time)} AL {format_date(result.end_time)}",
            styles["heading"],
        ),
        _table(rows, [7 * cm, 16 * cm], styles),
    ]


def _events_story(result: AnalysisResult, styles: dict[str, ParagraphStyle]) -> list:
    rows = [[
        "N.",
        "Data e ora apertura",
        "Contatore iniziale",
        "Data e ora chiusura",
        "Contatore finale",
        "Consumo",
        "Durata",
        "Tipo",
        "Affidabilita",
        "Note",
    ]]
    for event in result.events:
        rows.append(
            [
                event.number,
                format_datetime(event.opening_time),
                f"{event.initial_counter:.1f}",
                format_datetime(event.closing_time),
                f"{event.final_counter:.1f}",
                f"{event.consumption:.1f}",
                format_duration(event.duration_seconds),
                event.opening_type,
                event.reliability,
                event.notes,
            ]
        )
    if len(rows) == 1:
        rows.append(["", "Nessuna apertura rilevata", "", "", "", "", "", "", "", ""])
    return [
        Paragraph("Aperture e chiusure", styles["heading"]),
        Paragraph(f"Aperture rilevate nel file: {len(result.events)}", styles["normal"]),
        Paragraph(
            "La chiusura viene registrata sull'ultima variazione del contatore; i 90 minuti successivi servono esclusivamente a confermarla.",
            styles["normal"],
        ),
        Spacer(1, 0.2 * cm),
        _table(
            rows,
            [0.7 * cm, 3.3 * cm, 1.7 * cm, 3.3 * cm, 1.7 * cm, 1.3 * cm, 1.6 * cm, 3.3 * cm, 1.8 * cm, 8.4 * cm],
            styles,
        ),
    ]


def _isolated_story(result: AnalysisResult, styles: dict[str, ParagraphStyle]) -> list:
    rows = [["N.", "Inizio", "Fine", "Incremento", "Passi", "Motivo", "Righe"]]
    for item in result.isolated_increments:
        rows.append(
            [
                item.number,
                format_datetime(item.start_time),
                format_datetime(item.end_time),
                f"{item.increment:.1f}",
                item.positive_steps,
                item.reason,
                item.original_rows,
            ]
        )
    if len(rows) == 1:
        rows.append(["", "Nessun incremento isolato", "", "", "", "", ""])
    return [Paragraph("Incrementi isolati", styles["heading"]), _table(rows, [0.8 * cm, 4 * cm, 4 * cm, 2 * cm, 1.4 * cm, 9 * cm, 3 * cm], styles)]


def _logic_story(config: AnalysisConfig, styles: dict[str, ParagraphStyle]) -> list:
    rows = [["Parametro", "Logica applicata"]]
    rows.extend(_logic_rows(config))
    return [Paragraph("Logica applicata", styles["heading"]), _table(rows, [6 * cm, 20 * cm], styles)]


def _alerts_story(result: AnalysisResult, styles: dict[str, ParagraphStyle]) -> list:
    rows = [["Tipo", "Dettaglio"]]
    for note in result.invalid_row_notes:
        rows.append(["Riga scartata", note])
    for reading in result.readings:
        if reading.anomaly:
            rows.append(["Anomalia", f"Riga {reading.original_row}: {reading.anomaly}"])
    for event in result.events:
        if event.reliability == "DA VERIFICARE":
            rows.append(["Apertura da verificare", f"N. {event.number}: {event.notes}"])
    if len(rows) == 1:
        rows.append(["Nessuna", "Non sono state rilevate anomalie critiche."])
    return [Paragraph("Alert e anomalie", styles["heading"]), _table(rows, [5 * cm, 21 * cm], styles)]


def _original_data_story(result: AnalysisResult, styles: dict[str, ParagraphStyle]) -> list:
    rows = [["Riga", "Data e ora", "Originale", "Corretto", "Delta", "Intervallo", "Anomalia", "Segmento"]]
    for reading in result.readings:
        rows.append(
            [
                reading.original_row,
                format_datetime(reading.timestamp),
                f"{reading.original_value:.3f}",
                f"{(reading.corrected_value or 0):.3f}",
                f"{reading.delta:.3f}",
                "" if reading.interval_minutes is None else f"{reading.interval_minutes:.1f}",
                reading.anomaly,
                reading.segment,
            ]
        )
    return [Paragraph("Appendice dati originali", styles["heading"]), _table(rows, [1.2 * cm, 4 * cm, 2 * cm, 2 * cm, 1.6 * cm, 2 * cm, 10 * cm, 1.5 * cm], styles)]


def _logic_rows(config: AnalysisConfig) -> list[list[str]]:
    return [
        ["Correzione oscillazioni", f"Diminuzioni fino a {config.max_oscillation} m3 vengono corrette mantenendo il valore precedente."],
        ["Apertura normale", f"Almeno {config.normal_opening_volume} m3 entro {config.normal_opening_window_minutes} minuti."],
        ["Apertura lenta", f"Almeno {config.slow_opening_volume} m3 entro {config.slow_opening_window_minutes} minuti e {config.slow_opening_min_increments} incrementi positivi."],
        ["Apertura rapida", f"Singolo incremento almeno pari a {config.rapid_single_increment} m3."],
        ["Chiusura", f"Confermata dopo {config.closure_confirmation_minutes} minuti senza nuova sequenza valida."],
        ["Tolleranza", f"Tolleranza di consumo durante chiusura: {config.closure_tolerance} m3."],
        ["Incrementi isolati", "Incrementi di 0.1 o 0.2 m3 senza continuita restano separati dalle aperture."],
        ["Reset", "Diminuzioni importanti interrompono il segmento e impediscono consumi negativi."],
        ["Affidabilita", f"ALTA con intervalli non superiori a {config.high_reliability_max_interval_minutes} minuti e nessuna anomalia."],
    ]


def _table(rows: list[list[object]], col_widths: list[float], styles: dict[str, ParagraphStyle]) -> Table:
    wrapped_rows = _wrap_table_cells(rows, styles)
    table = Table(wrapped_rows, colWidths=col_widths, repeatRows=1, splitByRow=True)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B7C9D6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F7FB")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _wrap_table_cells(rows: list[list[object]], styles: dict[str, ParagraphStyle]) -> list[list[Paragraph]]:
    wrapped_rows: list[list[Paragraph]] = []
    for row_index, row in enumerate(rows):
        style = styles["table_header"] if row_index == 0 else styles["table_cell"]
        wrapped_rows.append([Paragraph(escape("" if value is None else str(value)), style) for value in row])
    return wrapped_rows


def _header_footer(result: AnalysisResult):
    def draw(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#17365D"))
        header = f"RTU {result.rtu_name} - Periodo {format_date(result.start_time)} / {format_date(result.end_time)}"
        canvas.drawString(doc.leftMargin, landscape(A4)[1] - 0.8 * cm, header)
        canvas.drawRightString(landscape(A4)[0] - doc.rightMargin, 0.6 * cm, f"Pagina {doc.page}")
        canvas.restoreState()

    return draw
