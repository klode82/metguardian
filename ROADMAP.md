# ROADMAP.md

Piano di sviluppo di **eMule Backup Manager** — app desktop Windows che fa backup intelligenti e storicizzati dei file `*.part.met` di eMule.

---

## Decisioni consolidate (dall'analisi)

| Tema | Scelta |
|---|---|
| Linguaggio | Python |
| Finestra desktop + UI | **pywebview** (usa WebView2/Edge già presente su Win10/11, nessun web server) |
| Scheduler | Thread con loop ogni 5 minuti (stdlib, nessuna dipendenza extra) |
| Database | **SQLite** (`sqlite3` stdlib, modalità WAL) |
| Framework UI/CSS | **Franken UI** + UIkit 3, caricati in locale (gratis, MIT, offline) |
| System tray | Icona vicino all'orologio, menu **Open** / **Exit** |
| Notifiche | Toast Windows **solo** per file danneggiati |
| Cartelle | Cartella temp e cartella backup **configurabili** dall'utente |
| Parser | La tua `PartMetParser` integrata senza modifiche |

## Le 3 informazioni storicizzate

1. **Nome del file** → dal tag `filename` del `.met`
2. **Numero del file** `part.met` → dal nome del file su disco (es. `493.part.met` → `493`)
3. **MD4 globale** → da `file_hash` del `.met`, convertito in esadecimale (usato anche come nome del backup)

## Macchina a stati — ⚠️ DA CONFERMARE

Stati di uno slot (identificato dal **numero**, es. `493`): `OK`, `INACCESSIBILE`, `DANNEGGIATO`, più l'uscita verso `ARCHIVIO`.

- **OK, MD4 invariato** → aggiorno il backup, aggiorno il timestamp. *Nessun log* (nessun cambio di stato).
- **OK, MD4 nuovo sullo stesso numero** → il precedente MD4 va in **archivio** (motivo: `SOSTITUITO`); creo nuovo record + nuovo backup. *Log della transizione.*
- **Inaccessibile** (file lockato da eMule / permessi) → **non tocco l'MD4**, cambio solo lo stato, backup invariato. *Log.* Visibile solo in lista, **nessuna notifica Windows.**
- **Danneggiato** (si apre ma il parser fallisce, e non è una scrittura in corso) → **non storicizzo**, backup invariato. *Log* + **notifica Windows.**
- **Sparito** (completato o cancellato, indistinguibili) → record spostato in **archivio** (motivo: `RIMOSSO_O_COMPLETATO`); il backup fisico **resta**. *Log.*

**Guardia anti-falso-positivo:** se il parse fallisce **ma** il file è stato modificato da meno di N secondi (es. 10), lo tratto come `INACCESSIBILE`, non `DANNEGGIATO` — eMule probabilmente sta scrivendo. Nessun contatore, solo lettura del `mtime`.

**Logging:** si scrive una riga **solo al cambio di stato**, mai sulle conferme ripetute. Esempi: `493 → inaccessibile`, `493 → danneggiato`, `493 → OK`.

## Punti aperti — ⚠️ DA CONFERMARE

1. **Dove salvare il log.** Proposta: **tabella nel DB** (visibile e filtrabile nella UI). Da decidere se aggiungere anche un file `.txt` su disco. *Nei documenti assumo solo tabella DB.*
2. **Conferma della macchina a stati** sopra (in particolare lo scenario inaccessibile → ritorno → MD4 diverso → archivio).

---

## Step di sviluppo

Ogni step ha un obiettivo e una *Definition of Done* (DoD): quando è "fatto".

### Step 0 — Setup ambiente e scaffolding
- Creazione struttura cartelle (vedi `STRUCTURE.md`)
- `requirements.txt`, ambiente virtuale, `README.md` iniziale
- Download in locale degli asset Franken UI + UIkit 3 in `ui/css` e `ui/js`
- **DoD:** la struttura esiste e `python app.py` apre una finestra pywebview vuota.

### Step 1 — Database layer
- `db/schema.sql`: tabelle `file_attivi`, `file_archivio`, `log_eventi`, `config`
- `db/database.py`: connessione, attivazione **WAL**, init schema al primo avvio, gestione path in `data/`
- `db/repository.py`: funzioni CRUD (nessun SQL fuori da qui)
- **DoD:** all'avvio il DB viene creato con le 4 tabelle; CRUD testati da script.

### Step 2 — Lettura e classificazione dello stato
- `core/parser.py`: integrazione della tua `PartMetParser`
- `core/reader.py`: distingue **OK / INACCESSIBILE / DANNEGGIATO** (apertura file → parse → guardia `mtime`)
- Estrazione delle 3 informazioni (nome, numero, MD4 hex)
- **DoD:** dato un percorso `.met`, la funzione ritorna stato + le 3 info (o lo stato di errore corretto).

### Step 3 — Scansione cartella temp
- `core/scanner.py`: elenca **solo** `*.part.met` (esclude `.part` e `.part.met.bak`)
- Estrae il **numero** dal nome file
- **DoD:** data la cartella temp, ritorna la lista dei `.met` con numero associato.

### Step 4 — Backup manager
- `core/backup_manager.py`: copia il `.met` valido in `data/backups/` nominato `<MD4>.met`
- Sovrascrittura quando l'MD4 è invariato
- **DoD:** un `.met` valido viene copiato/sovrascritto correttamente per MD4.

### Step 5 — Macchina a stati + logging transizioni
- `core/state_machine.py`: confronto stato rilevato vs salvato, decisione azione, scrittura log **solo su cambio**
- Gestione archivio (`SOSTITUITO`, `RIMOSSO_O_COMPLETATO`)
- Gestione scenario inaccessibile → ritorno → MD4 diverso
- **DoD:** simulando una sequenza di scansioni, gli stati e l'archivio evolvono come da specifica e il log contiene solo le transizioni.

### Step 6 — Scheduler
- `scheduler/worker.py`: thread con loop ogni 5 minuti che orchestra scanner → state_machine
- Avvio/arresto pulito insieme all'app; possibilità di "scansiona ora"
- **DoD:** il ciclo gira ogni 5 min in background senza bloccare la UI.

### Step 7 — Bridge pywebview
- `api/bridge.py`: classe `js_api` con metodi `get_file_list()`, `get_log()`, `get_config()`, `save_config()`, `scan_now()`, `set_theme()`
- **DoD:** dalla console della UI si possono invocare i metodi e ricevere dati reali dal DB.

### Step 8 — UI: lista file e log
- `ui/index.html` + `ui/js/app.js`: tabella dei file con **badge di stato** (OK / Pending / Danneggiato), sezione log
- Banner di avviso per i danneggiati
- Aggiornamento automatico dopo ogni scansione
- **DoD:** la dashboard mostra dati reali, gli stati sono leggibili a colpo d'occhio.

### Step 9 — UI: impostazioni
- Sezione impostazioni: selezione **cartella temp** e **cartella backup**, salvataggio in `config`
- Selettore di tema chiaro/scuro **con persistenza** (salvato nel DB, risolve il limite noto di Franken UI)
- **DoD:** cambiando le cartelle e riavviando, le impostazioni persistono.

### Step 10 — Notifiche Windows
- `core/notifier.py`: toast tipo *"Ci sono file danneggiati su eMule, è possibile il ripristino"*
- Scatta **solo** alla transizione verso `DANNEGGIATO`, non a ogni scansione
- **DoD:** un `.met` corrotto genera una (e una sola) notifica al cambio di stato.

### Step 11 — System tray e comportamento finestra
- `tray/tray_icon.py`: icona vicino all'orologio, menu **Open** / **Exit**
- Chiusura della finestra → l'app resta nel tray e continua a scansionare; **Exit** chiude davvero
- **DoD:** chiudendo la finestra l'app vive nel tray; **Open** la riapre; **Exit** termina tutto.

### Step 12 — Rifiniture e robustezza
- Gestione errori (cartella temp inesistente, permessi, DB lockato)
- Log applicativo minimo per il debug
- **DoD:** l'app non crasha negli scenari di errore comuni.

### Step 13 — Packaging
- Eseguibile Windows con **PyInstaller** (un singolo `.exe` o cartella)
- Icona, test su macchina pulita
- **DoD:** l'app parte con doppio clic su un Windows senza Python installato.

### Step 14 — Test end-to-end
- Prova con file `.part.met` reali, inclusi casi limite (corrotto, in scrittura, sostituito, cancellato)
- **DoD:** tutti gli scenari della macchina a stati verificati su file veri.

---

## Schema database (bozza)

**file_attivi** — i download attualmente monitorati
`id, numero, md4, nome_file, stato, percorso_backup, data_primo_rilevamento, data_ultimo_aggiornamento`

**file_archivio** — storico dei download non più presenti o sostituiti
`id, numero, md4, nome_file, percorso_backup, motivo, data_archiviazione`

**log_eventi** — solo le transizioni di stato
`id, numero, md4, stato_precedente, stato_nuovo, messaggio, timestamp`

**config** — impostazioni chiave/valore
`chiave, valore` (es. `cartella_temp`, `cartella_backup`, `intervallo_scansione`, `tema`)

---

## Ordine di lavoro proposto

Backend prima, UI dopo: **Step 0 → 6** costruiscono e validano tutta la logica senza interfaccia (testabile da script). **Step 7 → 11** aggiungono la parte visibile. **Step 12 → 14** consolidano e impacchettano. Procederemo uno step alla volta, con il tuo OK a ciascuno.
