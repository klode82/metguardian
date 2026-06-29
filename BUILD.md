# BUILD.md — Come compilare MetGuardian

## Spec disponibili

| File spec | Piattaforma | Output | Script |
|-----------|-------------|--------|--------|
| `metguardian-win.spec` | Windows | `dist\MetGuardian\` (cartella) | `build.bat` |
| `metguardian-win-onefile.spec` | Windows | `dist\MetGuardian.exe` (file singolo) | manuale |
| `metguardian-linux.spec` | Linux | `dist/MetGuardian/` → `MetGuardian-x86_64.AppImage` | `build-linux.sh` |

> PyInstaller **non supporta cross-compilation**: ogni spec va eseguito sul sistema operativo di destinazione.

---

## Windows — cartella (consigliato)

### Prerequisiti

| Requisito | Note |
|-----------|------|
| Windows 10 / 11 | |
| Python 3.10+ | [python.org](https://www.python.org/downloads/) — aggiungi al PATH |
| Microsoft Edge WebView2 Runtime | Incluso in Win10 20H2+ e Win11; se manca: [scaricalo](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) |

### Build

```bat
python -m venv .venv
.venv\Scripts\activate
build.bat
```

### Output

```
dist\MetGuardian\
    MetGuardian.exe
    _internal\
        ui\            ← HTML, CSS, JS, assets
        db\schema.sql
        *.dll / *.pyd  ← runtime Python
    data\              ← creata al primo avvio (DB SQLite)
    logs\              ← creata al primo avvio (log rotante)
```

### Distribuzione

Comprimi `dist\MetGuardian\` in uno zip. L'utente estrae e avvia `MetGuardian.exe`.

---

## Windows — file singolo

```bat
python -m venv .venv
.venv\Scripts\activate
build-onefile.bat
```

Output: `dist\MetGuardian.exe` — un solo file da copiare.

**Attenzione:**
- Il primo avvio estrae ~80-150 MB in `%TEMP%`: attesa di 3-5 secondi extra.
- Alcuni antivirus segnalano gli exe auto-estraenti come sospetti (falso positivo).
- `data\` e `logs\` vengono creati accanto all'exe, non nel temp.

---

## Linux — AppImage

### Prerequisiti

| Requisito | Note |
|-----------|------|
| Python 3.10+ | |
| `appimagetool` | Vedi sotto |

```bash
wget https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool
```

### Build

```bash
python -m venv .venv
source .venv/bin/activate
chmod +x build-linux.sh
./build-linux.sh
```

### Output

```
MetGuardian-x86_64.AppImage   ← file singolo eseguibile
```

L'AppImage include tutto il necessario (Qt, WebEngine, Python). L'utente scarica,
`chmod +x MetGuardian-x86_64.AppImage` e avvia — nessuna installazione richiesta.

---

## Note comuni

- **console=False** in tutti gli spec: nessuna finestra terminale nera. Per debug cambia a `True` e ricompila.
- **UPX** disabilitato di default per evitare falsi positivi antivirus.
- I file `data/` e `logs/` vengono scritti **accanto all'eseguibile**: installa MetGuardian in una posizione con permessi di scrittura (es. `C:\Users\nome\MetGuardian\`, mai `C:\Program Files\`).
