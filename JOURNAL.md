# MetGuardian — Journal di sviluppo

Diario tecnico della sessione di build completa (24–25 giugno 2026).
Contiene tutte le decisioni, i problemi incontrati, le soluzioni adottate e
lo stato corrente. Scritto per consentire la continuazione del lavoro in una
nuova sessione (es. Claude Code in VSCode) senza perdere contesto.

---

## Contesto generale

| Voce              | Dettaglio |
|-------------------|-----------|
| Sviluppatore      | Stefano (steveholmes) |
| Ambiente di dev   | Linux Mint 22.3 XFCE |
| Target principale | Windows 10/11 |
| Repo locale       | `/aurigalab/python/metguardian/` |
| Venv              | `.venv` (Python 3.12, isolato) |
| Lingua del codice | Inglese (docstring PEP 257, commenti in prima persona) |
| Lingua di lavoro  | Italiano |
| Metodo            | Analisi → condivisione → OK → codice a blocchi |

---

## Scopo dell'app

MetGuardian è un'app desktop Python che monitora una cartella Temp di
eMule/aMule ogni 5 minuti, leggendo **solo** i file `*.part.met` (ignorando
`.part` e `.part.met.bak`). Per ogni file valido:
- Estrae: numero slot (es. `001`), nome file (da tag), hash globale (MD4 hex)
- Salva un backup nominato per hash in una cartella dedicata
- Storicizza tutto in SQLite
- Notifica se un file diventa **danneggiato**

**Scenario chiave di Stefano**: la cartella Temp è su Linux, ma eMule gira su
una VM Windows 10. MetGuardian monitora la *cartella*, non il processo. Non può
sapere se eMule è in esecuzione.

---

## Stack tecnologico (decisioni definitive)

| Componente       | Scelta              | Motivazione |
|------------------|---------------------|-------------|
| GUI              | pywebview           | Finestra nativa, bridge JS↔Python, no HTTP server |
| Backend GUI Linux| PyQt6 + PyQt6-WebEngine | Installabile via pip (wheel), no PyGObject/sistema |
| Backend GUI Win  | WebView2/Edge       | Built-in su Win10/11, nessuna dipendenza |
| Tray Linux       | QSystemTrayIcon (Qt)| Menu+clic completi via pip, niente GObject |
| Tray Win/Mac     | pystray             | Nativo, funziona bene |
| CSS Framework    | Franken UI 2.1.2    | Moderno, shadcn-style, offline, no build step |
| Tema colore      | **Teal fisso**      | Decisione di prodotto, non esposta all'utente |
| Dark mode        | Solo toggle on/off  | Unica opzione estetica esposta |
| Database         | SQLite stdlib (WAL) | Zero dipendenze, concorrenza sicura |
| Scheduling       | threading + sleep   | Zero dipendenze |
| Notifiche Win    | win11toast          | Toast nativi Windows |
| Notifiche Linux  | plyer               | Notifiche desktop cross-platform |
| Icona tray       | Pillow (generata)   | Scudo teal, nessun file esterno per ora |

### Nota importante su GTK vs Qt
GTK richiederebbe PyGObject, che NON si installa via pip (va compilato,
richiede librerie di sistema). Su Linux, per un'app distribuita a utenti
finali, è inaccettabile chiedere di installare pacchetti di sistema.
**Qt invece si installa interamente via pip con wheel pre-compilate.**
Questa decisione impatta packaging, distribuzione e UX: corretta.

---

## Struttura del progetto (STRUCTURE.md)

```
metguardian/
├── app.py                  # Entry point
├── requirements.txt
├── ROADMAP.md
├── STRUCTURE.md
├── CHANGELOG.md
├── JOURNAL.md              # Questo file
├── core/
│   ├── __init__.py
│   ├── parser.py           # PartMetParser (classe di Stefano, documentata)
│   ├── reader.py           # MetReader: legge un .met → ReadResult
│   ├── scanner.py          # TempScanner: scansiona la cartella Temp
│   ├── backup_manager.py   # BackupManager: backup atomici per hash
│   ├── state_machine.py    # StateMachine: orchestrazione per ciclo
│   ├── notifier.py         # Notifier: notifiche desktop cross-platform
│   └── logging_setup.py    # setup_logging(): file rotante + console
├── db/
│   ├── __init__.py
│   ├── schema.sql          # Schema SQLite (CREATE TABLE IF NOT EXISTS)
│   ├── database.py         # Database: connessione WAL, context manager
│   └── repository.py       # Repository: tutte le query + costanti STATE_*
├── scheduler/
│   ├── __init__.py
│   └── worker.py           # ScanScheduler: thread daemon, scan ogni N sec
├── api/
│   ├── __init__.py
│   └── bridge.py           # Bridge: js_api pywebview (get_*, save_config, ecc.)
├── tray/
│   ├── __init__.py
│   └── tray_icon.py        # TrayIcon: Qt su Linux, pystray su Win/Mac
├── ui/
│   ├── index.html          # Dashboard principale (Franken UI)
│   ├── css/
│   │   ├── core.min.css    # Franken UI (locale, da scaricare)
│   │   └── app.css         # Stili custom MetGuardian
│   ├── js/
│   │   ├── core.iife.js    # Franken UI (locale)
│   │   ├── icon.iife.js    # Franken UI icons (locale)
│   │   └── app.js          # Logica UI (bridge calls, rendering, tab)
│   └── assets/             # Icona definitiva (quando pronta)
├── data/
│   └── metguardian.db      # SQLite (generato automaticamente)
└── logs/
    └── metguardian.log     # Log rotante
```

**Asset Franken UI 2.1.2** — file da scaricare manualmente (non su PyPI):
- `ui/css/core.min.css` — contiene TUTTI i 16 temi come classi CSS
- `ui/js/core.iife.js` — UIkit bundled
- `ui/js/icon.iife.js` — icone

---

## Sistema di temi Franken UI (nota importante)

I 16 temi colore NON sono file separati. Stanno **tutti** in `core.min.css`
e si attivano con **una classe sull'elemento `<html>`**:

```html
<html class="uk-theme-teal">          <!-- chiaro -->
<html class="uk-theme-teal dark">     <!-- scuro -->
```

Classi disponibili confermate da analisi binaria di `core.min.css`:
- Temi: `uk-theme-zinc/slate/stone/gray/neutral/red/rose/orange/green/blue/yellow/violet/amber/purple/teal`
- Dark: `.dark`
- Raggi: `uk-radii-none/sm/lg`
- Ombre: `uk-shadows-none/md/lg`
- Font: `uk-font-sm`

**Per MetGuardian**: tema fisso `uk-theme-teal` (hardcoded in `<html>`),
solo `dark_mode` (0/1) esposto all'utente nelle Impostazioni.

---

## Macchina a stati (il cuore del progetto)

Ogni file è identificato dal **numero slot** (es. `001`). Lo stato è per slot.

### Stati attivi
- `OK` — file leggibile e valido
- `INACCESSIBLE` — file non leggibile (mostrato in UI come "Pending")
- `DAMAGED` — file corrotto (hash non leggibile, mtime > guard)

### Motivi di archiviazione
- `REPLACED` — stesso slot, hash diverso (nuovo download)
- `REMOVED_OR_COMPLETED` — file sparito dalla Temp

### Transizioni chiave
```
File valido, hash noto → OK: aggiorna backup, NO log
File valido, hash noto, era non-OK → OK: log transizione
File valido, hash diverso → archivia vecchio (REPLACED), nuovo record, log
File nuovo → inserisci, backup, log
File mtime recente + non parsabile → INACCESSIBLE (guard: 10 sec default)
File non parsabile + mtime vecchio → DAMAGED, notifica
File scomparso → archivia (REMOVED_OR_COMPLETED), backup resta su disco
```

### Regola cruciale per il ripristino
Quando un file passa a DAMAGED, `set_active_state` cambia **solo lo stato**.
`file_hash` e `backup_path` **restano nel record attivo**. Questo è ciò che
permette il ripristino per numero slot senza leggere il file corrotto.

---

## Schema database

### Tabella `active_files`
```sql
number TEXT PRIMARY KEY,   -- "001", "032", ecc.
file_name TEXT,
file_hash TEXT,            -- 32 char hex (MD4/ed2k)
backup_path TEXT,          -- percorso del backup su disco
state TEXT,                -- OK | INACCESSIBLE | DAMAGED
first_seen TEXT,
last_updated TEXT
```

### Tabella `archived_files`
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
number TEXT, file_name TEXT, file_hash TEXT, backup_path TEXT,
reason TEXT,               -- REPLACED | REMOVED_OR_COMPLETED
archived_at TEXT
```

### Tabella `event_log`
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
timestamp TEXT, number TEXT,
previous_state TEXT, new_state TEXT, message TEXT
```

### Tabella `config`
```sql
key TEXT PRIMARY KEY, value TEXT
```
Chiavi default: `temp_folder`, `backup_folder`, `scan_interval_seconds` (300),
`mtime_guard_seconds` (10), `dark_mode` (0).

**NOTA MIGRAZIONI**: non ci sono migrazioni automatiche. Se cambia lo schema,
cancellare manualmente `data/metguardian.db*` e rilanciare. Da migliorare
in futuro.

---

## Problemi incontrati e soluzioni

### 1. `no such column: file_hash`
**Causa**: il DB era stato creato con lo schema vecchio (colonna `md4`).
`CREATE TABLE IF NOT EXISTS` non aggiorna tabelle esistenti.
**Soluzione**: cancellare il DB e rigenerarlo.
```bash
rm -f data/metguardian.db data/metguardian.db-wal data/metguardian.db-shm
```

### 2. `[pywebview] GTK cannot be loaded` + crash
**Causa**: pywebview prova GTK prima di Qt. GTK richiede `gi` (PyGObject),
non installabile via pip nel venv isolato.
**Soluzione**: forzare il backend Qt in `app.py`:
```python
gui = "qt" if sys.platform.startswith("linux") else None
webview.start(on_started, gui=gui)
```

### 3. Finestra nera su Linux (`dma_buf acquisition failure`)
**Causa**: QtWebEngine (Chromium) su Wayland non riesce a condividere texture
GPU. Messaggio: `Failed to get native pixmap due to dma_buf acquisition failure`.
**Soluzione**: disabilitare GPU per Chromium prima che Qt parta:
```python
if sys.platform.startswith("linux"):
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --disable-gpu-compositing",
    )
```
Implementato in `_configure_linux_webengine()` in `app.py`.

### 4. Colonna "File" invisibile in UI
**Causa**: `.mg-filename` aveva `max-width: 0` che in QtWebEngine collassava
la larghezza a zero. I dati erano corretti nel DB e nel parser.
**Soluzione**: `table-layout: fixed` su `.mg-table` e `max-width: 100%` su
`.mg-filename` in `app.css`.

### 5. Tray non interattiva su Linux (pystray xorg)
**Causa**: senza PyGObject, pystray usa il backend `xorg` che mostra l'icona
ma non supporta menu né clic. L'icona restava anche dopo la chiusura dell'app
("icona fantasma").
**Soluzione**: usare `QSystemTrayIcon` di Qt su Linux (già installato con
PyQt6, nessuna dipendenza aggiuntiva). Implementato con un **QObject ponte**
che marshala la creazione dell'icona sul thread GUI tramite segnale+
`QueuedConnection`.

### 6. `QTimer.singleShot(msec, context, slot)` non esiste in PyQt6
**Causa**: la firma a 3 argomenti con context object non esiste in PyQt6
(esiste in PySide o versioni più recenti).
**Errore**: `TypeError: arguments did not match any overloaded call`
**Soluzione**: QObject ponte con Signal connesso in QueuedConnection:
```python
class _Bridge(QObject):
    run = Signal(object)
    def __init__(self):
        super().__init__()
        self.moveToThread(app.thread())
        self.run.connect(self._invoke, Qt.QueuedConnection)
    def _invoke(self, func):
        func()
```
Emettere `bridge.run.emit(fn)` da qualsiasi thread esegue `fn` sul thread GUI.

### 7. `GPUInfo not initialized on GpuInfoUpdate`
**Causa**: effetto collaterale innocuo del `--disable-gpu`. Chromium segnala
l'assenza dell'accelerazione. Non è un errore.
**Soluzione**: nessuna. Il messaggio è inoffensivo.

---

## Stato degli step

| Step | Descrizione | Stato |
|------|-------------|-------|
| 0 | Scaffolding, `requirements.txt`, `.gitignore` | ✅ Completo |
| 1 | DB layer (schema, database.py, repository.py) | ✅ Completo |
| 2 | `core/reader.py` — lettura e classificazione | ✅ Completo |
| 3 | `core/scanner.py` — scansione cartella Temp | ✅ Completo |
| 4 | `core/backup_manager.py` — backup atomici | ✅ Completo |
| 5 | `core/state_machine.py` — macchina a stati | ✅ Completo |
| 6 | `scheduler/worker.py` + `core/logging_setup.py` | ✅ Completo |
| 7 | `api/bridge.py` — js_api pywebview | ✅ Completo |
| 8 | UI: dashboard, lista file, log (`index.html`, `app.css`, `app.js`) | ✅ Completo |
| 9 | UI: impostazioni (cartelle, intervallo, dark mode) | ✅ Completo |
| 10 | `core/notifier.py` — notifiche desktop cross-platform | ✅ Completo |
| 11 | `tray/tray_icon.py` — system tray Qt+pystray | ✅ Completo, verificato XFCE |
| 12 | **Ripristino file part.met** (`core/restore.py`) | ✅ Completo |
| 13 | **Dettaglio singolo part.met** (`core/detail.py`, modal) | ✅ Completo |
| 14 | **Icona e branding** (`ui/assets/icon.png`, tray, window) | ✅ Completo |
| 15 | Rifiniture e robustezza | ✅ Completo |
| 16 | Packaging PyInstaller (.exe Windows) | ✅ Completo |
| 17 | Test end-to-end | ⏳ Pianificato |

---

## Step 12 — Ripristino: specifiche complete e approvate

**Logica**: solo file `DAMAGED` con `backup_path` **fisicamente presente su
disco** sono ripristinabili. Il backup_path resta nel record attivo anche dopo
il passaggio a DAMAGED (design della state machine).

**Flusso UI**:
1. In tab Monitored, solo i file ripristinabili mostrano la checkbox
2. Selezionandone ≥1 appare il pulsante **"Restore selected"**
3. Con ≥1 file ripristinabile esiste anche **"Restore all"**
4. Clic → **modal obbligatoria**: "Attenzione: accertarsi che eMule sia chiuso"
   (MetGuardian non può verificarlo: monitora una cartella, non il processo;
   la cartella può essere su una macchina diversa dalla VM con eMule)
5. Utente conferma → per ogni file:
   - Elimina `<temp>/<num>.part.met` e `<temp>/<num>.part.met.bak` (se esistono)
   - **Copia** (non sposta) il backup come `<temp>/<num>.part.met`
   - Riporta esito per-file
6. Dopo il ripristino → lancia scansione immediata → file torna OK

**Comportamento su errori**:
- Backup mancante su disco → non mostrare checkbox (non ripristinabile)
- Errore I/O durante il ripristino → segnala errore per quel file, continua gli altri
- Mai crash dello scheduler

**Nuovi file**:
- `core/restore.py` — `RestoreManager`
- Metodo bridge: `restore_files(numbers)` → `{number: {ok, error}}`

---

## Step 13 — Dettaglio: specifiche

Modal "Detail" per ogni riga in Monitored e Archive. Dati:
- Versione, MD4 hex, nome file, dimensione (`filesize` + `filesize_hi`)
- Data, numero parti, gap (scaricato/mancante in byte e %)
- Tutti i tag

Sorgente: ri-parsing on-demand. Se il file in Temp è leggibile, usa quello.
Se è DAMAGED/inaccessibile, usa il backup (mostra l'ultima versione valida).

**Nota**: Stefano fornirà un archivio ZIP con decine di `.part.met` reali per
verificare che il parser gestisca tutti i casi. Prima di implementare Step 13,
fare **analisi binaria** di quei file per mappare tutti i tipi di tag presenti.
Includere: verifica del dubbio su tipi `0x08`/`0x09` (UINT16/UINT8 potrebbero
essere invertiti rispetto alla spec eMule — lasciato con NOTE nel codice).

---

## Step 14 — Icona: specifiche

**Design desiderato** (da realizzare graficamente da Stefano):
- Mulo (mascotte eMule) con **cappuccio grigio da "stregone"**
- Testa leggermente china come in cammino su un sentiero
- Muso del mulo che sporge visibilmente dal cappuccio
- Wordmark "**MetGuardian**" in stile medievale, semplice e d'impatto

**Integrazione tecnica** (da fare quando arriva il PNG):
- PNG ad alta risoluzione (256×256, sfondo trasparente) in `ui/assets/`
- `make_tray_image()` in `tray/tray_icon.py` → caricare da file con fallback
  allo scudo generato se il file manca
- Generare `.ico` multi-risoluzione per finestra e packaging Windows
- Aggiungere come icona della finestra pywebview

---

## Note su cose da rivedere

### "Discorso archivio da rivedere"
Stefano ha segnalato che vuole spiegare come intende rivedere la logica
dell'archivio (`archived_files`). I dettagli saranno forniti nella prossima
sessione.

### Localizzazione UI
L'UI è attualmente in **inglese** (coerente con il codice). Da localizzare in
italiano se richiesto — è una mezz'ora di lavoro.

### Migrazioni DB
Attualmente non esistono. Cambiando lo schema, va cancellato il DB manualmente.
Per il futuro: aggiungere una versione dello schema in `config` e un sistema
minimale di migrazione.

---

## Come continuare in VSCode / Claude Code

### Setup ambiente (se il venv è già fatto)
```bash
cd /aurigalab/python/metguardian
source .venv/bin/activate
python app.py
```

### Lanciare l'app
```bash
python app.py
```
- L'app parte, mostra la finestra, l'icona compare in tray su XFCE
- Il log è in `logs/metguardian.log`
- In tempo reale: `tail -f logs/metguardian.log`

### Se il DB va rigenerato
```bash
rm -f data/metguardian.db data/metguardian.db-wal data/metguardian.db-shm
python -c "
from db.database import Database
from db.repository import Repository
r = Repository(Database())
r.set_config('temp_folder', '/home/steveholmes/eMule/Temp')
r.set_config('backup_folder', '/home/steveholmes/eMule/Backup')
print(r.all_config())
"
```

### Prossimo step da implementare: Step 12 — Ripristino
File da creare: `core/restore.py`
File da modificare: `api/bridge.py` (aggiungere `restore_files`),
`ui/index.html` (checkbox + pulsanti), `ui/js/app.js` (logica modal + chiamate)

### Documenti sempre da allegare all'inizio di una sessione
- `CHANGELOG.md`
- `ROADMAP.md`
- `STRUCTURE.md`
- (questo `JOURNAL.md`)

---

## Versioni dipendenze rilevanti (al momento del test)

| Pacchetto | Versione testata |
|-----------|-----------------|
| Python | 3.12 |
| pywebview | (latest da pip) |
| PyQt6 | (latest da pip) |
| PyQt6-WebEngine | (latest da pip) |
| qtpy | (latest da pip) |
| Pillow | 12.1.1 |
| pystray | (latest da pip) |
| plyer | (latest da pip) |
| Franken UI | 2.1.2 (locale) |

---

*Documento generato il 25 giugno 2026 — fine sessione di build Step 0–11.*
