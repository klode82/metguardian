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

### Bugfix

- **Bug critico nel parser (version 0xE0)**: il formato `.part.met` versione `0xE0`
  (eMule vecchio / aMule) ha il layout `date(4) → hash(16)`, mentre le versioni
  `0xE1`/`0xE2` usano `hash(16) → date(4)`. Il parser leggeva sempre hash prima
  di date: per i file `0xE0` i 4 byte del timestamp eMule finivano nei primi 4 byte
  dell'"hash", che cambiava ad ogni scrittura eMule → archivio `REPLACED` a ogni
  ciclo di scansione. Analisi confermata su 488 file reali: tutti `0xE0`, tutti
  affetti. Fix: `parser.py` ora biforca la lettura in base a `version`. Dopo il fix
  il DB va resettato perché i record esistenti hanno l'hash errato.

### In corso / pianificato
- **Step 13 — Dettaglio del singolo part.met**: modal con tutti i dati del
  `.met` (versione, MD4, nome, dimensione, data, n. parti, gap con
  scaricato/mancante e %, tag). Ri-parsing on-demand del file in Temp o del
  backup (per i danneggiati). Bridge `get_detail(number)`.
- **Step 14 — Icona e branding**: icona definitiva (mulo eMule con cappuccio
  grigio da "stregone", muso in evidenza, testa china; logo "MetGuardian" stile
  medievale). `make_tray_image()` caricherà l'icona da `ui/assets/` con fallback;
  `.ico` multi-risoluzione per finestra ed eseguibile.
- **Step 15 — Rifiniture e robustezza**, **Step 16 — Packaging (.exe Windows)**,
  **Step 17 — Test end-to-end** (numerazione aggiornata dopo l'inserimento dei
  due nuovi step prima della building finale).

### Anticipato
- **`app.py` (bootstrap minimale, v1.0.0)**: entry point che collega logging,
  DB, state machine, scheduler, bridge e finestra pywebview. Permette di lanciare
  e vedere la dashboard dal vivo. NON ancora incluso: tray (Step 11) — per ora la
  chiusura della finestra termina l'app — e notifiche (Step 10).

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
- **Step 8 — UI: lista file e log** (`ui/index.html`, `ui/css/app.css`,
  `ui/js/app.js`): dashboard con header+stato, banner danneggiati, tab
  Monitored/Archive/Activity log, badge di stato (OK / Pending / Damaged),
  refresh automatico sull'evento `metguardian:scan-complete`, pulsante
  "Scan now". UI in inglese. Tema **Teal** (light) di default.
  Asset Franken UI: solo `core.min.css` + `core.iife.js` + `icon.iife.js`.
- **Step 9 — UI: impostazioni**: tab Settings con cartelle temp/backup
  (selettore nativo via `pick_folder`), intervallo di scansione (in minuti),
  e interruttore **Dark mode**, con persistenza (`dark_mode` salvato in config e
  applicato all'avvio). Il **tema colore è fisso a Teal** (decisione di prodotto,
  non esposta all'utente): rimosso il selettore dei 16 colori. Bridge:
  `ALLOWED_CONFIG_KEYS` include `dark_mode` (rimossi `theme` e `theme_color`).
- **Step 10 — Notifiche** (`core/notifier.py`, v1.0.0): classe `Notifier`
  cross-platform (win11toast su Windows, plyer su Linux/Mac) con `notify_damaged`
  agganciato a `report.newly_damaged` (avviso solo alla transizione verso
  danneggiato, mai ripetuto). Invio su thread breve (non blocca lo scheduler) e
  a prova di errore. Agganciato in `app.py` con callback combinato
  refresh-UI + notifica. Testato.
- **Step 12 — Ripristino del file part.met** (`core/restore.py`, v1.0.0):
  classe `RestoreManager.restore_files()` che ripristina i `.met` DAMAGED dalla
  copia di backup. Per ogni slot: elimina `<num>.part.met` e `<num>.part.met.bak`
  dalla cartella Temp, **copia** il backup come `<num>.part.met`, poi il bridge
  lancia una scansione immediata → DAMAGED→OK. Errori per-file isolati, mai crash.
  Bridge `restore_files(numbers)` (`api/bridge.py`): espone il metodo alla UI,
  aggiunge il campo `restorable` a `get_active_files()` (DAMAGED + backup fisico
  su disco). UI: colonna checkbox nella tab Monitored (solo per file ripristinabili),
  toolbar con "Restore selected" / "Restore all damaged", dialog di avvertimento
  ("chiudi eMule") con **componente generico** `showDialog()` riutilizzabile (icona
  configurabile, titolo, body HTML, pulsanti configurabili). Stili Franken UI
  (`uk-modal` + overlay). Risultati per-file mostrati sotto la toolbar.
- **Step 11 — System tray** (`tray/tray_icon.py`, v1.0.0): classe `TrayIcon`
  (pystray) con icona teal generata da Pillow e menu Open / Exit. In `app.py`:
  chiusura finestra → nascondi in tray (continua a scansionare), Open → mostra,
  Exit → ferma scheduler+tray e chiude davvero. Avvio difensivo: se il tray non
  è disponibile, l'app degrada (la chiusura finestra termina) senza crashare.
  `requirements.txt`: aggiunto `python-xlib` (Linux) per il backend xorg di
  pystray quando manca PyGObject (es. XFCE). Testato (icona, fallback, sintassi).

### Note sui temi (Franken UI 2.1.2)
- I 16 temi colore (zinc, slate, teal, ...) NON sono file separati: stanno tutti
  in `core.min.css` e si attivano con una classe su `<html>` (`uk-theme-<colore>`),
  più `.dark` per il dark mode, `uk-radii-*`, `uk-shadows-*`, `uk-font-*`.
  La persistenza del tema (Step 9) sarà quindi solo salvare/applicare la classe.

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

### Fixed
- **Tray pienamente funzionante su Linux senza pacchetti di sistema**
  (`tray/tray_icon.py` v2.1.0): doppio backend dietro un'unica `TrayIcon` —
  **Qt `QSystemTrayIcon`** su Linux (menu + clic completi, tutto via pip, sfrutta
  l'app Qt già usata da pywebview) e **pystray** su Windows/macOS. Il marshaling
  sul thread GUI usa un QObject ponte con `Signal` in `QueuedConnection` (la
  firma `QTimer.singleShot(msec, context, slot)` non esiste in PyQt6). Niente più
  richiesta di installare PyGObject/AppIndicator all'utente.
  **Verificato dal vivo su Linux Mint XFCE**: icona cliccabile, menu Open/Exit,
  nascondi-in-tray e riapertura funzionanti.
- **Tray non interattiva su Linux/XFCE (e icona fantasma)**: risolto dal punto
  sopra (prima ripiegava sul backend pystray `xorg`, privo di menu).
- **Colonna File vuota nella UI**: il troncamento usava `max-width: 0` sul
  `<div>` interno, che in QtWebEngine collassava la larghezza a zero nascondendo
  il nome. Corretto con `table-layout: fixed` sulla tabella ed ellissi su
  `.mg-filename` (`max-width: 100%`). Il dato era corretto in DB e parser.

### Note tecniche
- **QtWebEngine su Linux/Wayland**: su alcuni compositor la finestra rende nera
  (`dma_buf acquisition failure / Compositor returned null texture`). `app.py`
  imposta `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu --disable-gpu-compositing`
  solo su Linux (via `setdefault`, così una variabile esportata a mano vince).
- **Backend grafico pywebview** (deciso): Windows usa **WebView2/Edge**
  (built-in, nessuna dipendenza nel pacchetto); Linux usa **Qt/QtWebEngine**
  (installato via pip: `qtpy`, `PyQt6`, `PyQt6-WebEngine` — niente pacchetti di
  sistema, autosufficiente in fase di packaging); macOS usa WebKit via pyobjc.
  Scelta orientata alla minor frizione per l'UTENTE FINALE (pacchetto che gira
  sempre) più che alla leggerezza per lo sviluppatore. GTK resta alternativa
  leggera ma fragile da distribuire, scartata come default.
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
