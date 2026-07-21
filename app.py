"""Desktop application for water meter opening/closure analysis."""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import traceback
from ctypes import windll
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk

from analyzer import analyze_readings
from csv_reader import CsvPreview, load_counter_readings, preview_csv
from excel_report import create_excel_report
from models import AnalysisConfig
from pdf_report import create_pdf_report
from utils import setup_logging

LOGGER = logging.getLogger(__name__)
APP_ICON_NAME = "tecnidro_app_icon.ico"
APP_ICON_SOURCE_NAME = "tecnidro_app_icon.png"
APP_USER_MODEL_ID = "Tecnidro.AnalisiContatore"


def enable_high_dpi_awareness() -> None:
    """Ask Windows to render the application without bitmap scaling blur."""

    if sys.platform != "win32":
        return
    try:
        windll.user32.SetProcessDpiAwarenessContext(-4)
        return
    except Exception:
        LOGGER.debug("Per-monitor v2 DPI awareness not available", exc_info=True)
    try:
        windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        LOGGER.debug("Per-monitor DPI awareness not available", exc_info=True)
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        LOGGER.exception("Unable to enable Windows DPI awareness")


def set_windows_app_user_model_id() -> None:
    """Set a stable Windows app id so taskbar icons use the bundled icon."""

    if sys.platform != "win32":
        return
    try:
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        LOGGER.exception("Unable to set Windows AppUserModelID")


def resource_path(filename: str) -> Path:
    """Return a path that works both from source and from a PyInstaller bundle."""

    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / filename


def apply_window_icon(root: Tk) -> None:
    """Apply the application icon to the tkinter window when available."""

    icon_path = resource_path(APP_ICON_NAME)
    if not icon_path.exists():
        LOGGER.warning("Application icon not found: %s", icon_path)
        return
    try:
        root.iconbitmap(default=str(icon_path))
    except Exception:
        LOGGER.exception("Unable to apply application icon: %s", icon_path)


def configure_tk_scaling(root: Tk) -> None:
    """Synchronize Tk scaling with the current display DPI."""

    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except Exception:
        LOGGER.exception("Unable to configure Tk DPI scaling")


def default_output_directory() -> Path:
    """Return the default output directory for generated reports."""

    desktop = Path.home() / "Desktop"
    return desktop if desktop.exists() else Path.home()


class CounterAnalysisApp:
    """Main tkinter user interface."""

    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Analisi aperture e chiusure contatore")
        self.root.geometry("860x690")
        self.root.minsize(780, 620)

        self.csv_path = StringVar()
        self.rtu_name = StringVar(value="CBG_0087")
        self.output_dir = StringVar(value=str(default_output_directory()))
        self.counter_column = StringVar()
        self.status_text = StringVar(value="Seleziona un file CSV.")
        self.include_original_pdf = BooleanVar(value=False)
        self.advanced_visible = BooleanVar(value=False)
        self.excel_path: Path | None = None
        self.pdf_path: Path | None = None
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.advanced_vars: dict[str, StringVar] = {}

        self._build_ui()
        self.root.after(150, self._poll_worker_queue)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(12, weight=1)

        title = ttk.Label(main, text="Analisi aperture e chiusure contatore", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 18))

        ttk.Label(main, text="File CSV").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(main, textvariable=self.csv_path).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(main, text="Seleziona CSV", command=self._select_csv).grid(row=1, column=2, sticky="ew")

        ttk.Label(main, text="Nome GDC/RTU").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(main, textvariable=self.rtu_name).grid(row=2, column=1, sticky="ew", padx=8)

        ttk.Label(main, text="Colonna del contatore").grid(row=3, column=0, sticky="w", pady=6)
        self.counter_combo = ttk.Combobox(main, textvariable=self.counter_column, state="readonly")
        self.counter_combo.grid(row=3, column=1, sticky="ew", padx=8)

        ttk.Label(main, text="Cartella di uscita").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Entry(main, textvariable=self.output_dir).grid(row=4, column=1, sticky="ew", padx=8)
        ttk.Button(main, text="Seleziona cartella", command=self._select_output_dir).grid(row=4, column=2, sticky="ew")

        ttk.Checkbutton(
            main,
            text="Includi i dati originali nel PDF",
            variable=self.include_original_pdf,
        ).grid(row=5, column=1, sticky="w", padx=8, pady=8)

        self.advanced_button = ttk.Button(main, text="Parametri avanzati", command=self._toggle_advanced)
        self.advanced_button.grid(row=6, column=0, sticky="w", pady=(10, 4))
        self.advanced_frame = ttk.LabelFrame(main, text="Parametri avanzati", padding=12)
        self._build_advanced_fields()

        self.run_button = ttk.Button(main, text="ELABORA", command=self._start_processing)
        self.run_button.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(18, 8), ipady=10)

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.grid(row=9, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Label(main, textvariable=self.status_text).grid(row=10, column=0, columnspan=3, sticky="w", pady=6)

        self.result_frame = ttk.LabelFrame(main, text="Risultati", padding=12)
        self.result_frame.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.result_frame.columnconfigure(1, weight=1)
        self.excel_label = ttk.Label(self.result_frame, text="")
        self.pdf_label = ttk.Label(self.result_frame, text="")
        self.excel_label.grid(row=0, column=0, columnspan=4, sticky="w")
        self.pdf_label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 8))
        ttk.Button(self.result_frame, text="Apri Excel", command=lambda: self._open_path(self.excel_path)).grid(row=2, column=0, padx=(0, 8))
        ttk.Button(self.result_frame, text="Apri PDF", command=lambda: self._open_path(self.pdf_path)).grid(row=2, column=1, padx=(0, 8))
        ttk.Button(self.result_frame, text="Apri cartella", command=self._open_output_folder).grid(row=2, column=2)

        ttk.Label(
            main,
            text="by Manuel Rodriguez",
            font=("Segoe UI", 8),
            foreground="#6B7280",
        ).grid(row=12, column=0, columnspan=3, sticky="se", pady=(10, 0))

    def _build_advanced_fields(self) -> None:
        defaults = AnalysisConfig()
        fields = [
            ("max_oscillation", "Oscillazione massima (m3)", defaults.max_oscillation),
            ("normal_opening_volume", "Apertura normale - volume (m3)", defaults.normal_opening_volume),
            ("normal_opening_window_minutes", "Apertura normale - finestra (min)", defaults.normal_opening_window_minutes),
            ("slow_opening_volume", "Apertura lenta - volume (m3)", defaults.slow_opening_volume),
            ("slow_opening_window_minutes", "Apertura lenta - finestra (min)", defaults.slow_opening_window_minutes),
            ("slow_opening_min_increments", "Apertura lenta - incrementi minimi", defaults.slow_opening_min_increments),
            ("rapid_single_increment", "Apertura rapida - singolo incremento (m3)", defaults.rapid_single_increment),
            ("closure_confirmation_minutes", "Conferma chiusura (min)", defaults.closure_confirmation_minutes),
            ("closure_tolerance", "Tolleranza durante chiusura (m3)", defaults.closure_tolerance),
            ("high_reliability_max_interval_minutes", "Intervallo massimo per affidabilita alta (min)", defaults.high_reliability_max_interval_minutes),
        ]
        for row, (key, label, value) in enumerate(fields):
            ttk.Label(self.advanced_frame, text=label).grid(row=row, column=0, sticky="w", pady=3)
            var = StringVar(value=str(value))
            self.advanced_vars[key] = var
            ttk.Entry(self.advanced_frame, textvariable=var, width=14).grid(row=row, column=1, sticky="w", padx=8, pady=3)
        ttk.Button(self.advanced_frame, text="Ripristina valori predefiniti", command=self._reset_defaults).grid(
            row=len(fields), column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    def _toggle_advanced(self) -> None:
        if self.advanced_visible.get():
            self.advanced_frame.grid_remove()
            self.advanced_visible.set(False)
        else:
            self.advanced_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=4)
            self.advanced_visible.set(True)

    def _reset_defaults(self) -> None:
        defaults = AnalysisConfig()
        for key, var in self.advanced_vars.items():
            var.set(str(getattr(defaults, key)))

    def _select_csv(self) -> None:
        selected = filedialog.askopenfilename(title="Seleziona CSV", filetypes=[("CSV", "*.csv"), ("Tutti i file", "*.*")])
        if not selected:
            return
        path = Path(selected)
        self.csv_path.set(str(path))
        if not self.output_dir.get().strip():
            self.output_dir.set(str(default_output_directory()))
        try:
            preview = preview_csv(path)
            self._apply_preview(preview)
            self.status_text.set("CSV selezionato. Parametri pronti.")
        except Exception as exc:
            LOGGER.exception("CSV preview failed")
            messagebox.showwarning("Anteprima CSV", f"Impossibile leggere l'anteprima del CSV:\n{exc}")

    def _apply_preview(self, preview: CsvPreview) -> None:
        candidates = preview.counter_candidates
        self.counter_combo["values"] = candidates
        if candidates:
            self.counter_column.set(candidates[0])
        if preview.suggested_rtu:
            self.rtu_name.set(preview.suggested_rtu)

    def _select_output_dir(self) -> None:
        selected = filedialog.askdirectory(title="Seleziona cartella di uscita")
        if selected:
            self.output_dir.set(selected)

    def _config_from_ui(self) -> AnalysisConfig:
        values: dict[str, float | int] = {}
        for key, var in self.advanced_vars.items():
            text = var.get().strip().replace(",", ".")
            try:
                number = float(text)
            except ValueError as exc:
                raise ValueError(f"Parametro non numerico: {key}") from exc
            if number <= 0:
                raise ValueError(f"Parametro non positivo: {key}")
            values[key] = int(number) if key == "slow_opening_min_increments" else number
        return AnalysisConfig(**values)

    def _validate_inputs(self) -> tuple[Path, Path, str, str, AnalysisConfig]:
        if not self.csv_path.get().strip():
            raise ValueError("Seleziona un file CSV.")
        csv_path = Path(self.csv_path.get())
        if not csv_path.exists():
            raise ValueError("Il file CSV selezionato non esiste.")
        if not self.rtu_name.get().strip():
            raise ValueError("Il nome GDC/RTU non puo essere vuoto.")
        if not self.counter_column.get().strip():
            raise ValueError("Seleziona la colonna del contatore.")
        output_dir = Path(self.output_dir.get().strip() or default_output_directory())
        return csv_path, output_dir, self.rtu_name.get().strip(), self.counter_column.get().strip(), self._config_from_ui()

    def _start_processing(self) -> None:
        try:
            csv_path, output_dir, rtu_name, counter_column, config = self._validate_inputs()
        except ValueError as exc:
            messagebox.showerror("Dati mancanti", str(exc))
            return
        self.run_button.configure(state="disabled")
        self.progress.start(12)
        self.status_text.set("Lettura del file...")
        thread = threading.Thread(
            target=self._worker,
            args=(csv_path, output_dir, rtu_name, counter_column, config, self.include_original_pdf.get()),
            daemon=True,
        )
        thread.start()

    def _worker(
        self,
        csv_path: Path,
        output_dir: Path,
        rtu_name: str,
        counter_column: str,
        config: AnalysisConfig,
        include_original_pdf: bool,
    ) -> None:
        try:
            self.worker_queue.put(("status", "Lettura del file..."))
            load_result = load_counter_readings(csv_path, counter_column)
            self.worker_queue.put(("status", "Analisi delle aperture..."))
            result = analyze_readings(
                load_result.readings,
                config,
                csv_path,
                rtu_name,
                counter_column,
                load_result.discarded_rows,
                load_result.invalid_row_notes,
            )
            self.worker_queue.put(("status", "Creazione Excel..."))
            excel_path = create_excel_report(result, output_dir)
            self.worker_queue.put(("status", "Creazione PDF..."))
            pdf_path = create_pdf_report(result, output_dir, include_original_pdf)
            self.worker_queue.put(("done", (excel_path, pdf_path, len(result.events), len(result.isolated_increments))))
        except Exception as exc:
            LOGGER.error("Processing failed: %s\n%s", exc, traceback.format_exc())
            self.worker_queue.put(("error", exc))

    def _poll_worker_queue(self) -> None:
        try:
            while True:
                kind, payload = self.worker_queue.get_nowait()
                if kind == "status":
                    self.status_text.set(str(payload))
                elif kind == "done":
                    excel_path, pdf_path, events, isolated = payload
                    self._processing_done(Path(excel_path), Path(pdf_path), int(events), int(isolated))
                elif kind == "error":
                    self._processing_error(payload)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_worker_queue)

    def _processing_done(self, excel_path: Path, pdf_path: Path, events: int, isolated: int) -> None:
        self.progress.stop()
        self.run_button.configure(state="normal")
        self.excel_path = excel_path
        self.pdf_path = pdf_path
        self.status_text.set("Operazione completata.")
        self.excel_label.configure(text=f"Excel: {excel_path}")
        self.pdf_label.configure(text=f"PDF: {pdf_path}")
        messagebox.showinfo("Operazione completata", f"Creati Excel e PDF.\nAperture: {events}\nIncrementi isolati: {isolated}")

    def _processing_error(self, payload: object) -> None:
        self.progress.stop()
        self.run_button.configure(state="normal")
        self.status_text.set("Errore durante l'elaborazione.")
        messagebox.showerror("Errore", f"Impossibile completare l'elaborazione:\n{payload}")

    def _open_path(self, path: Path | None) -> None:
        if path is None:
            messagebox.showwarning("File non disponibile", "Nessun file ancora creato.")
            return
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("Apertura file", str(exc))

    def _open_output_folder(self) -> None:
        path = Path(self.output_dir.get()) if self.output_dir.get() else None
        self._open_path(path)


def main() -> None:
    """Start the desktop application."""

    setup_logging()
    set_windows_app_user_model_id()
    enable_high_dpi_awareness()
    root = Tk()
    configure_tk_scaling(root)
    apply_window_icon(root)
    CounterAnalysisApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
