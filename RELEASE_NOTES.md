# Release Notes

## 2026-07-21 - Correzione definitiva avviso Excel

- Sostituita l'intestazione separatrice composta da spazio con `SEPARATORE`.
- La colonna resta stretta e visivamente usata come separatore tra `CONSUMO` e `DURATA APERTURA`.
- Evitato l'avviso di ripristino contenuto di Microsoft Excel causato da intestazioni tabella non valide.

## 2026-07-21 - Icona barra applicazioni

- Aggiunto un Windows AppUserModelID stabile per forzare la barra applicazioni a usare l'icona dell'app.
- Generato un nuovo eseguibile `TecnidroAnalisiContatore.exe` per evitare la cache icone associata al vecchio nome `AnalisiContatore.exe`.
- Aggiornato `build_windows.bat` con il nuovo nome dell'eseguibile.

## 2026-07-21 - Interfaccia nitida su Windows

- Abilitata la modalita DPI-aware su Windows prima della creazione della finestra.
- Sincronizzato lo scaling di Tk con il DPI reale del monitor.
- Ridotto l'effetto sfocato dell'interfaccia quando Windows usa scaling 125%, 150% o superiore.

## 2026-07-21 - Icona piu nitida

- Usata `tecnidro_app_icon.png` come fonte ad alta qualita per rigenerare l'icona.
- Rigenerata `tecnidro_app_icon.ico` come icona multi-risoluzione.
- Aggiunti i formati interni `256`, `128`, `64`, `48`, `32`, `24` e `16` pixel per ridurre l'effetto sfocato in Windows.
- Aggiunto un test automatico per verificare i formati interni dell'icona.

## 2026-07-21 - Icona Tecnidro

- Aggiunta `tecnidro_app_icon.ico` come icona dell'eseguibile Windows.
- Applicata la stessa icona anche alla finestra principale dell'app.
- Aggiornato `build_windows.bat` per includere automaticamente icona e risorsa nel bundle PyInstaller.

## 2026-07-21 - Compatibilita Excel

- Corretto l'avviso di ripristino contenuto mostrato da Microsoft Excel.
- La colonna separatrice tra `CONSUMO` e `DURATA APERTURA` mantiene un'intestazione valida per Excel.
- Aggiunto un test automatico per verificare che la tabella Excel non contenga intestazioni vuote.

## 2026-07-21 - Cartella di uscita predefinita Desktop

- Impostata la `Cartella di uscita` predefinita sul Desktop dell'utente.
- La selezione del CSV non cambia piu automaticamente la cartella di uscita.
- Il fallback resta la home utente se la cartella Desktop non esiste.

## 2026-07-21 - Firma Manuel Rodriguez

- Aggiunta la firma `by Manuel Rodriguez` nell'angolo in basso a destra della finestra principale.
- Ricompilato `dist/AnalisiContatore.exe` con la correzione del layout PDF gia inclusa.
- Verificata la suite automatica: `15 passed`.
