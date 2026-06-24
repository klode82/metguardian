# STRUCTURE.md

Struttura fisica del progetto **eMule Backup Manager**.

Legenda:
- `(*)` = file/cartella **generati a runtime** (non versionati, creati al primo avvio)
- `(tuo)` = file che **fornisci tu** o che derivano da codice già esistente
- `(lib)` = asset di terze parti scaricati in locale (offline, nessuna CDN)

```
emule-backup-manager/
│
├── app.py                          # Entry point. Avvia DB, scheduler, bridge, finestra pywebview e tray.
├── requirements.txt                # Dipendenze Python (pywebview, pystray, win11toast, Pillow)
├── README.md                       # Istruzioni d'uso e avvio
├── ROADMAP.md                      # Piano di sviluppo a step
├── STRUCTURE.md                    # Questo file
│
├── core/                           # Logica di dominio (nessuna dipendenza dalla UI)
│   ├── __init__.py
│   ├── parser.py                   # (tuo) La tua classe PartMetParser, integrata senza modifiche
│   ├── scanner.py                  # Scansione cartella temp: trova solo *.part.met, ignora .part e .bak
│   ├── reader.py                   # Wrapper sopra il parser: distingue OK / INACCESSIBILE / DANNEGGIATO
│   │                               #   - prova apertura file  -> OSError/PermissionError = INACCESSIBILE
│   │                               #   - parser ritorna None  -> DANNEGGIATO (con guardia mtime)
│   │                               #   - guardia mtime: parse fallito + file modificato < N sec = INACCESSIBILE
│   ├── state_machine.py            # Confronta stato rilevato vs stato salvato; decide transizioni e azioni
│   ├── backup_manager.py           # Copia il .met valido in data/backups/ nominandolo per MD4 (hex)
│   └── notifier.py                 # Toast Windows per i file danneggiati
│
├── db/                             # Persistenza
│   ├── __init__.py
│   ├── schema.sql                  # DDL: file_attivi, file_archivio, log_eventi, config
│   ├── database.py                 # Connessione SQLite (modalità WAL), init schema, gestione path
│   └── repository.py               # Query CRUD su attivi/archivio/log/config (nessun SQL sparso altrove)
│
├── scheduler/                      # Esecuzione periodica
│   ├── __init__.py
│   └── worker.py                   # Thread con loop ogni 5 min; richiama scanner + state_machine
│
├── api/                            # Ponte tra Python e UI web
│   ├── __init__.py
│   └── bridge.py                   # Classe js_api esposta a pywebview: metodi chiamabili da app.js
│                                   #   es. get_file_list(), get_log(), get_config(), save_config(),
│                                   #       scan_now(), set_theme()
│
├── tray/                           # Icona vicino all'orologio
│   ├── __init__.py
│   └── tray_icon.py                # Menu "Open" (riapre finestra) e "Exit" (chiude tutto)
│
├── ui/                             # Front-end (Franken UI + UIkit 3, tutto in locale)
│   ├── index.html                  # Pagina unica: sezione Lista file + sezione Log + sezione Impostazioni
│   ├── css/
│   │   ├── franken-ui.min.css      # (lib) tema/estetica shadcn
│   │   └── app.css                 # Stili custom dell'app
│   ├── js/
│   │   ├── uikit.min.js            # (lib) JS di UIkit 3 (modali, toast, ecc.)
│   │   ├── uikit-icons.min.js      # (lib) set di icone UIkit
│   │   ├── franken-ui.iife.js      # (lib) web component Franken UI
│   │   └── app.js                  # Logica UI: chiama window.pywebview.api.*, rende tabella e badge
│   └── assets/
│       └── icon.ico                # Icona finestra + tray
│
└── data/                       (*) # Dati locali, creati al primo avvio
    ├── emule_backup.db         (*) # Database SQLite
    └── backups/                (*) # I file .part.met salvati, nominati per MD4
        ├── <MD4-A>.met         (*) #   es. 7f3a...e9.met
        └── <MD4-B>.met         (*)
```

## Note di progettazione sulla struttura

**Separazione netta in tre livelli.** `core/` non sa nulla di pywebview né di SQLite specifico: contiene solo la logica (cosa fare con un file). `db/` parla solo con SQLite. `api/` e `ui/` sono la presentazione. Questo rende ogni pezzo testabile da solo e facile da modificare senza toccare il resto.

**La tua classe resta intatta.** `core/parser.py` ospita `PartMetParser` così com'è. La distinzione tra "inaccessibile" e "danneggiato" — che la classe da sola non fa, perché ritorna sempre `None` in caso di errore — vive in `core/reader.py`, sopra al parser. Se un domani cambi la classe, tocchi solo quel file.

**Niente web server.** Non c'è una cartella `server/` perché pywebview comunica con la UI tramite il bridge `js_api` (`api/bridge.py`), non via HTTP. La UI chiama direttamente i metodi Python.

**Tutto offline.** Gli asset in `ui/css` e `ui/js` sono scaricati in locale: l'app funziona senza connessione e senza CDN.
