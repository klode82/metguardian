# BUILD.md — Come compilare MetGuardian per Windows

## Prerequisiti

| Requisito | Note |
|-----------|------|
| Windows 10 / 11 | PyInstaller non supporta cross-compilation: il build deve girare su Windows |
| Python 3.10+ | [python.org](https://www.python.org/downloads/) — aggiungi Python al PATH durante l'installazione |
| Microsoft Edge WebView2 Runtime | Già incluso in Windows 10 20H2 e Windows 11; se manca: [scaricalo qui](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) |

## Build in tre passi

```bat
REM 1. Crea e attiva un virtual environment pulito
python -m venv .venv
.venv\Scripts\activate

REM 2. Esegui lo script di build (installa tutto e compila)
build.bat
```

Oppure manualmente:

```bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller metguardian.spec --clean --noconfirm
```

## Output

```
dist\
  MetGuardian\
    MetGuardian.exe      ← eseguibile principale
    ui\                  ← HTML, CSS, JS, icona
    db\
      schema.sql         ← schema SQLite (creato automaticamente al primo avvio)
    *.dll                ← runtime Python e dipendenze
    ...
```

Al primo avvio vengono create automaticamente accanto all'eseguibile:

```
dist\MetGuardian\
    data\
      metguardian.db     ← database SQLite
    logs\
      metguardian.log    ← log rotante (max 1 MB × 5 file)
```

## Distribuzione

Comprimi la cartella `dist\MetGuardian\` in uno zip. L'utente estrae lo zip
e avvia `MetGuardian.exe` — nessuna installazione richiesta.

## Note

- **WebView2** è incluso in Windows 10 20H2+ e in tutti i Windows 11. Se la
  macchina di destinazione è più vecchia, l'utente deve installare
  *Microsoft Edge WebView2 Runtime* (installer gratuito ~2 MB).
- **console=False** nello spec significa che non compare nessuna finestra
  terminale nera. Se devi fare debug, cambia `console=True` e ricompila.
- **UPX** (compressione DLL/exe) è disabilitato di default per evitare
  problemi con antivirus. Puoi abilitarlo nello spec se UPX è nel PATH e
  i test non danno falsi positivi.
- I file `data\` e `logs\` vengono scritti nella stessa cartella
  dell'eseguibile: installa MetGuardian in una posizione dove l'utente ha
  i permessi di scrittura (es. `C:\Users\nome\MetGuardian\`, non
  `C:\Program Files\`).
