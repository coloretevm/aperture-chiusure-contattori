# Analisi aperture e chiusure contatore

Applicazione desktop locale per Windows che analizza letture CSV di un contatore acqua e genera report Excel e PDF.

## Architettura

- `app.py`: interfaccia grafica `tkinter`/`ttk` con elaborazione in thread.
- `csv_reader.py`: rilevamento separatore/codifica, parsing date inglesi, valori con virgola o punto decimale.
- `analyzer.py`: preprocessing del contatore e macchina di stati per aperture, chiusure e incrementi isolati.
- `excel_report.py`: report Excel professionale con fogli richiesti, filtri e formati data reali.
- `pdf_report.py`: report PDF A4 orizzontale con riepilogo, tabelle, logica e anomalie.
- `models.py`: dataclass condivise.
- `tests/`: test automatici del parser e della logica.

## Installazione

1. Installa Python 3.11 o superiore.
2. Crea un ambiente virtuale:

```bat
python -m venv .venv
.venv\Scripts\activate
```

3. Installa le dipendenze:

```bat
pip install -r requirements.txt
```

4. Avvia l'applicazione:

```bat
python app.py
```

## Creare l'eseguibile Windows

Con l'ambiente virtuale attivo:

```bat
build_windows.bat
```

L'eseguibile viene creato da PyInstaller con il nome `AnalisiContatore`.

## Test

```bat
pytest
```

I report tecnici e gli errori dell'applicazione vengono salvati in `logs/app.log`.
