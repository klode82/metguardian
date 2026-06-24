# Changelog — MetGuardian

Tutte le modifiche rilevanti del progetto sono annotate qui.

Il formato segue la convenzione [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto adotta il [Versionamento Semantico](https://semver.org/lang/it/).

> **Nota per le sessioni di lavoro future**
> Questo file e' la memoria del progetto. All'inizio di ogni nuova sessione
> allego sempre `CHANGELOG.md`, `ROADMAP.md` e `STRUCTURE.md`, cosi' si
> riprende esattamente dal punto in cui eravamo. Ogni step completato va
> annotato qui, spostandolo da `[Non rilasciato]` a una versione datata.

---

## [Non rilasciato]

### In corso
- **Step 0 — Scaffolding**: struttura cartelle, ambiente virtuale, dipendenze.

### Added
- Documenti di progetto: `ROADMAP.md`, `STRUCTURE.md`, `README.md`.
- `requirements.txt` con dipendenze e marker per-OS (build Portable-ready).
- `.gitignore` (esclude `data/`, ambiente virtuale, cache, log, build).
- Struttura cartelle: `core/`, `db/`, `scheduler/`, `api/`, `tray/`, `ui/`.

### Decisioni prese
- **Nome dell'applicazione**: MetGuardian.
- **Scopo**: backup intelligenti e storicizzati dei file `*.part.met` di eMule.
- **Stack**: Python + pywebview (finestra desktop, nessun web server) +
  SQLite (modulo standard, modalita' WAL) + Franken UI / UIkit 3 (UI in locale).
- **Cross-platform**: scelta build "Portable-ready" (codice neutro per
  Windows / macOS / Linux fin da subito; collaudo e packaging Windows per ora).
  Fuori da Windows l'app monitora i file `.part.met` di **aMule**.
- **Macchina a stati** confermata: stati `OK`, `INACCESSIBILE`, `DANNEGGIATO`,
  piu' uscita verso `ARCHIVIO`.
  - MD4 invariato -> aggiorna backup, nessun log.
  - MD4 nuovo sullo stesso numero -> il precedente va in archivio (`SOSTITUITO`),
    si crea nuovo record + backup.
  - Inaccessibile -> non si tocca l'MD4, cambia solo lo stato (solo in lista,
    nessuna notifica Windows).
  - Danneggiato -> non si storicizza, notifica Windows. Guardia `mtime`: se il
    parse fallisce ma il file e' stato modificato da pochi secondi, si tratta
    come `INACCESSIBILE` (eMule sta scrivendo).
  - Sparito -> record in archivio (`RIMOSSO_O_COMPLETATO`), il backup fisico resta.
- **Le 3 informazioni storicizzate**: nome file (tag `filename`), numero del
  file (dal nome su disco, es. `493`), MD4 globale (da `file_hash`, in esadecimale,
  usato anche come nome del backup).
- **Logging doppio**: tabella nel DB (visibile in UI) + file di testo (per
  tracciare anche le anomalie del software, con `try/except` mirati). Si scrive
  **solo** al cambio di stato, mai sulle conferme ripetute.
- **Cartelle configurabili**: cartella temp e cartella backup impostabili
  dall'utente.
- **System tray**: alla chiusura della finestra l'app resta nel tray (menu
  Open / Exit) e continua a scansionare.
- **Il file `.part.met.bak` viene ignorato**: non e' affidabile, ed e' proprio
  il motivo per cui questo software esiste.
- **La classe `PartMetParser` resta intatta**: la distinzione
  inaccessibile/danneggiato vive in un livello superiore (`core/reader.py`).
- **Convenzioni di codice**: docstring in stile PEP 257 + commenti inline,
  scritti in prima persona; `pathlib` per tutti i percorsi.

---

## Legenda dei tipi di modifica
- **Added** — funzionalita' nuove.
- **Changed** — modifiche a funzionalita' esistenti.
- **Deprecated** — funzionalita' che verranno rimosse.
- **Removed** — funzionalita' rimosse.
- **Fixed** — correzioni di bug.
- **Security** — correzioni di sicurezza.
