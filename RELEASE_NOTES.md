# Release Notes

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
