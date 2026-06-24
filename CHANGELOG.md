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
- **Step 8 — UI: lista file e log** (`ui/index.html`, `ui/js/app.js`).

### Completato
- **Step 0 — Scaffolding**: struttura cartelle creata, ambiente virtuale
  funzionante, dipendenze installate.
- **Documentazione di `PartMetParser`** (v1.0.0): docstring PEP 257 + commenti,
  logica invariata. Da collocare in `core/parser.py`.
- **Step 1 — Database**: `db/schema.sql`, `db/database.py`, `db/repository.py`.
  4 tabelle in WAL, CRUD testati end-to-end sugli scenari della macchina a stati.
  Colonna identificativa del contenuto: `file_hash`.
- **Step 2 — Lettura e classificazione** (`core/reader.py`, v1.0.0): classe
  `MetReader` che traduce l'esito del parser in `OK` / `INACCESSIBLE` / `DAMAGED`,
  con guardia `mtime` per non segnalare come danneggiato un file in scrittura.
  Estrae le 3 informazioni (numero dal nome, `file_hash` hex, `filename`).
  Testato su file valido, corrotto, fresco, mancante e troncato.
- **Step 3 — Scansione cartella temp** (`core/scanner.py`, v1.0.0): classe
  `TempScanner` che elenca i soli `*.part.met` (esclude `.part` e
  `.part.met.bak`), ne ricava il numero e li ordina. Gestisce cartella
  inesistente/non valida con eccezioni chiare. Testato.
- **Step 4 — Backup manager** (`core/backup_manager.py`, v1.0.0): classe
  `BackupManager` che salva il `.met` valido come `<file_hash>.met` con
  scrittura atomica (temp + replace), sovrascrive a parità di hash, valida
  l'hash (anti path-traversal). I backup non vengono mai cancellati dal flusso
  normale. Testato.
- **Step 5 — Macchina a stati** (`core/state_machine.py`, v1.0.0): classe
  `StateMachine.run_cycle()` che orchestra scanner + reader + backup +
  repository. Implementa l'intera "vera chiave" (OK / INACCESSIBLE / DAMAGED /
  sostituzione hash / archivio), preserva l'hash quando il file non è valido,
  logga solo le transizioni, segnala i nuovi danneggiati per la notifica, e
  isola gli errori per-file con `try/except` + logger. Restituisce uno
  `ScanReport`. Testato su sequenza multi-ciclo completa.
- **Step 6 — Scheduler** (`scheduler/worker.py`, v1.0.0): classe
  `ScanScheduler` con thread daemon che esegue `run_cycle()` a intervalli
  (letti dalla config a ogni giro), `scan_now()` sincrono, avvio/arresto puliti,
  callback `on_cycle_complete` per UI e notifiche. Cambio cartelle a caldo senza
  riavvio. Aggiunto `core/logging_setup.py` (v1.0.0): logger `metguardian` con
  file rotante (`logs/metguardian.log`) + console per transizioni e anomalie.
  Testato (avvio, ciclo periodico, scan_now, cambio cartella, stop, file log).
- **Step 7 — Bridge pywebview** (`api/bridge.py`, v1.0.0): classe `Bridge`
  (`js_api`) con i metodi chiamabili dalla UI: `get_active_files`, `get_archive`,
  `get_log`, `get_config`, `get_status`, `save_config` (valida cartelle con
  warning, ignora chiavi ignote, lancia scan), `scan_now`, `set_theme`,
  `pick_folder` (selettore nativo). `on_scan_complete` spinge l'evento
  `metguardian:scan-complete` alla UI per il refresh. Testato.

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
- **Lingua del codice**: tutto il codice (docstring, commenti, identificatori)
  e' scritto in **inglese**. Di conseguenza stati e motivi sono in inglese:
  - Stati: `OK`, `INACCESSIBLE`, `DAMAGED` (erano OK / INACCESSIBILE / DANNEGGIATO).
  - Motivi archivio: `REPLACED` (sostituito), `REMOVED_OR_COMPLETED` (rimosso/completato).
  - Tabelle: `active_files`, `archived_files`, `event_log`, `config`.
  - Identificativo del contenuto: colonna `file_hash` (stesso nome di
    `PartMet.file_hash`; neutra rispetto a MD4/MD5, lunga 32 caratteri hex).
  - Database file: `data/metguardian.db`.

### Note tecniche
- **Setup Linux**: `PyGObject` non si installa via pip (richiede compilazione).
  Si usa il pacchetto di sistema (`python3-gi`, `gir1.2-gtk-3.0`,
  `gir1.2-webkit2-4.1`) e si crea il venv con `--system-site-packages`.
  Per questo `requirements.txt` non contiene la riga `PyGObject`.
- **Asset UI rinviati**: il download di Franken UI / UIkit in locale e' stato
  spostato allo Step 8 (costruzione UI), perche' il backend (Step 1-6) non li
  usa. Versione di riferimento da "pinnare": `franken-ui@2.1.2` (il progetto e'
  in transizione verso un nuovo corso "0build", da rivalutare al momento).

---

## Legenda dei tipi di modifica
- **Added** — funzionalita' nuove.
- **Changed** — modifiche a funzionalita' esistenti.
- **Deprecated** — funzionalita' che verranno rimosse.
- **Removed** — funzionalita' rimosse.
- **Fixed** — correzioni di bug.
- **Security** — correzioni di sicurezza.
