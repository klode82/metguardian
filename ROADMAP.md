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

## Avanzamento

| # | Step | Stato |
|---|------|-------|
| 0 | Setup ambiente e scaffolding | ✅ |
| 1 | Database layer | ✅ |
| 2 | Lettura e classificazione stato | ✅ |
| 3 | Scansione cartella Temp | ✅ |
| 4 | Backup manager | ✅ |
| 5 | Macchina a stati + logging transizioni | ✅ |
| 6 | Scheduler | ✅ |
| 7 | Bridge pywebview | ✅ |
| 8 | UI: lista file e log | ✅ |
| 9 | UI: impostazioni | ✅ |
| 10 | Notifiche desktop cross-platform | ✅ |
| 11 | System tray (Qt + pystray) | ✅ |
| 12 | Ripristino file part.met | ✅ |
| 13 | Dettaglio singolo part.met (modal) | ✅ |
| 14 | Icona e branding | ✅ |
| 15 | Rifiniture e robustezza | ✅ |
| 16 | Packaging PyInstaller | ✅ |
| 17 | Test end-to-end | ⏳ |

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

### Step 12 — Ripristino del file part.met
Recupero di un download quando il suo `.part.met` in cartella Temp si è
danneggiato (es. dopo un'interruzione di corrente). Il ripristino si basa sul
**numero del file** (001, 032, …), NON sull'MD4: il `.met` danneggiato non è
leggibile, quindi l'hash non è disponibile. La sorgente è il backup dell'ultima
versione valida, che la macchina a stati conserva nel record attivo
(`backup_path` resta valorizzato anche quando lo stato passa a DAMAGED).

Requisiti funzionali:
- Solo i file **DAMAGED che hanno un backup** (`backup_path` valorizzato) sono
  ripristinabili. Un file mai stato valido (hash/backup nulli) non lo è.
- **Selezione multipla** in lista: comparsa di un pulsante **"Restore selected"**
  quando almeno un file ripristinabile è selezionato.
- Pulsante **"Restore all"** quando esiste **almeno un** file danneggiato
  ripristinabile.
- **Modal di avvertimento** prima di procedere: l'utente DEVE chiudere eMule.
  MetGuardian è a servizio di una *cartella*, non del processo eMule (la cartella
  Temp può stare su un'altra macchina/VM), quindi non può verificare da sé se
  eMule è in esecuzione: è responsabilità dell'utente.
- Per ogni file confermato:
  1. eliminare `<temp>/<num>.part.met` e `<temp>/<num>.part.met.bak` (se esistono);
  2. **copiare** (non spostare) il backup `<num>` da `backup_path` a
     `<temp>/<num>.part.met`;
  3. avvisare dell'esito (successo / errore per ciascun file).
- Dopo il ripristino, lanciare una scansione: al giro successivo il file torna
  `OK` (transizione DAMAGED → OK loggata).
- Backend dedicato `core/restore.py` (`RestoreManager`) + metodo bridge
  `restore_files(numbers)` che ritorna l'esito per-file. Robusto: backup
  mancante, cartella temp non valida, errori di I/O → messaggio chiaro, nessun
  crash.
- **DoD:** selezionando uno o più file danneggiati e confermando la modal, i
  `.met` vengono ripristinati nella Temp e al giro dopo tornano OK; gli errori
  per-file sono riportati senza interrompere gli altri.

### Step 13 — Dettaglio del singolo part.met
Una scheda (modal) che mostra **tutti** i dati di un `.part.met`.
- Pulsante **"Detail"** per riga (Monitored e Archive).
- Dati mostrati: versione, MD4 (hex), nome file, dimensione totale (con
  `filesize` + `filesize_hi`), data, numero di parti, **gap** con calcolo di
  scaricato/mancante e percentuale, e l'elenco completo dei tag.
- Sorgente: si ri-parsa il `.met` su richiesta — il file in Temp se leggibile,
  altrimenti il **backup** (utile per i danneggiati: mostra com'era l'ultima
  versione valida).
- Backend: helper che usa `PartMetParser` per costruire un dizionario ricco;
  metodo bridge `get_detail(number)`.
- **DoD:** premendo Detail si apre una modal con i dati completi del file
  (o del suo backup se il file in Temp non è leggibile).

### Step 14 — Icona e branding
- Icona definitiva: mulo (mascotte eMule) con cappuccio grigio da "stregone",
  muso in evidenza, testa leggermente china come in cammino. Logo testuale
  "MetGuardian" in stile medievale.
- Sostituire `make_tray_image()` per caricare l'icona da `ui/assets/`
  (PNG ad alta risoluzione) con fallback allo scudo generato.
- Generare `.ico` multi-risoluzione per la finestra e l'eseguibile Windows.
- **DoD:** l'app mostra l'icona definitiva su finestra e tray; `.ico` pronto per
  il packaging.

### Step 15 — Rifiniture e robustezza
- **Config guard all'avvio:** se `temp_folder` o `backup_folder` non sono configurate, la UI mostra un avviso e disabilita "Scan now" fino a quando non vengono impostate.
- **Cartelle inesistenti o non leggibili:** scanner e backup_manager loggano e restituiscono risultato vuoto senza propagare eccezioni verso la UI.
- **DB inaccessibile:** `OperationalError` SQLite catturata nel repository → log + risposta vuota, mai crash.
- **Log rotation:** `RotatingFileHandler` su `data/metguardian.log` — max 2 MB × 3 backup per evitare crescita illimitata.
- **Scan now disabilitato durante scansione in corso:** pulsante reso inattivo dal lancio del ciclo fino al suo completamento, per evitare cicli sovrapposti.
- **Settings warnings:** al salvataggio, se le cartelle configurate non esistono su disco viene mostrato un avviso non bloccante in UI.
- **DoD:** l'app non crasha negli scenari di errore comuni (cartella mancante, permessi negati, DB lockato); il file di log non cresce all'infinito; "Scan now" non è mai doppiabile.

### Step 16 — Packaging
- Eseguibile Windows con **PyInstaller** (un singolo `.exe` o cartella)
- Icona definitiva, test su macchina pulita
- **DoD:** l'app parte con doppio clic su un Windows senza Python installato.

### Step 17 — Test end-to-end
- Prova con file `.part.met` reali, inclusi casi limite (corrotto, in scrittura, sostituito, cancellato, ripristinato)
- **DoD:** tutti gli scenari della macchina a stati e del ripristino verificati su file veri.

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
