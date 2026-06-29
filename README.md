<p align="center">
  <img src="docs/MetGuardian_Contest.webp" alt="MetGuardian — dashboard" width="860">
</p>

<h1 align="center">MetGuardian</h1>
<p align="center">
  <strong>Smart backups and recovery for eMule / aMule <code>.part.met</code> files</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.12.3-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/pywebview-6.2.1-4B8BBE?style=flat-square" alt="pywebview">
  <img src="https://img.shields.io/badge/Pillow-12.2.0-FF6B6B?style=flat-square" alt="Pillow">
  <img src="https://img.shields.io/badge/pystray-0.19.5-44CC11?style=flat-square" alt="pystray">
  <img src="https://img.shields.io/badge/PyQt6-6.11.0-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/PyQt6--WebEngine-6.11.0-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PyQt6-WebEngine">
  <img src="https://img.shields.io/badge/QtPy-2.4.3-41CD52?style=flat-square" alt="QtPy">
  <img src="https://img.shields.io/badge/SQLite-built--in-07405E?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Franken_UI-2.1.2-8B5CF6?style=flat-square" alt="Franken UI">
  <img src="https://img.shields.io/badge/win11toast-Windows_only-0078D4?style=flat-square&logo=windows&logoColor=white" alt="win11toast">
</p>

---

## Why MetGuardian?

Anyone who has used **eMule** or **aMule** for long downloads knows the frustration: a power outage, a forced shutdown, or an unexpected crash can corrupt a `.part.met` file — the small but critical index that records which chunks of a file have already been downloaded.

When this happens, eMule marks the download as **damaged or unreadable**, and the corresponding `.part` data file (which can be gigabytes in size and represent hours or days of transfer) becomes inaccessible. eMule does maintain its own `.part.met.bak` backup, but it is notoriously unreliable — often a copy of the already-corrupted file, written at exactly the wrong moment.

**MetGuardian was born to solve this.** It runs silently in the system tray and, every few minutes, reads every `.part.met` file in your eMule temp folder. When a file is valid and healthy, MetGuardian saves its own independent backup copy, identified by the file's unique MD4 hash. If the `.part.met` is later corrupted, MetGuardian can restore the last known-good version in seconds — bringing your download back to life without losing a single already-downloaded chunk.

---

## Features

### 🛡️ Automatic rolling backups
MetGuardian scans the eMule / aMule temp folder at a configurable interval (default: 5 minutes). Every time a `.part.met` file is healthy and readable, a backup copy is saved, named after its **MD4 hash** — the stable identity of the download. The backup is overwritten only when progress is made on the same download; a new download occupying the same slot creates a new backup without touching the previous one.

### 🔄 One-click restore
When a `.part.met` is damaged, the restore toolbar appears automatically. Select one or more files (or click **Restore all damaged**), confirm that eMule is closed, and MetGuardian replaces the broken `.met` with the last valid backup. A scan is triggered immediately afterward, and the file returns to **OK** status.

### 📊 Full download detail
Click the **ⓘ** icon on any row in the Monitored or Archive tab to open a full detail modal showing: file version, MD4 hash, filename, total size, download date, number of parts, **visual progress bar**, gap list (with start/end byte offsets and missing size per gap), and all raw binary tags from the `.part.met` file. For damaged or archived files, the detail is loaded from the last valid backup.

### 📋 State machine with event log
MetGuardian tracks every download across five states:

| State | Meaning |
|-------|---------|
| **OK** | File is readable and backed up |
| **Pending** | File is present but temporarily locked or being written |
| **Damaged** | File is unreadable — backup available for restore |
| **Replaced** | A new download took over the same slot number |
| **Removed / Completed** | File disappeared from the temp folder (download finished or deleted) |

A log entry is written **only on state changes**, never on repeated confirmations of the same state. The full activity log is visible in the app and stored in SQLite.

### 🔔 Desktop notifications
A system notification is sent the moment a file transitions to **Damaged** — once and only once per event, never repeated. On Windows: native toast via `win11toast`. On Linux / macOS: desktop notification via `plyer`.

### 🗂️ Archive
Every download that leaves the active set (replaced, completed, or deleted) is moved to the Archive tab. Its physical backup file is never deleted — it stays on disk indefinitely and can be inspected at any time via the detail modal.

### 🌙 Dark mode
Full dark mode support via Franken UI / UIkit theming. The preference is persisted across sessions.

### 🖥️ System tray integration
Closing the window does not quit the app — it hides to the system tray and keeps scanning. The tray icon provides **Open** and **Exit** actions. On Linux the Qt `QSystemTrayIcon` backend is used (no extra system packages required); on Windows and macOS `pystray` handles the tray.

### ⚙️ Settings
Configure from the UI without restarting:
- **eMule / aMule temp folder** — the folder MetGuardian watches
- **Backup folder** — where backup `.met` files are stored
- **Scan interval** — in minutes (minimum: 1)
- **Dark mode** toggle

---

## Running from source

```bash
# Clone the repository
git clone https://github.com/your-username/metguardian.git
cd metguardian

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
```

### Requirements

| Platform | Minimum |
|----------|---------|
| Windows | Windows 10 / 11 + [Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (pre-installed on Win10 20H2+ and all Win11) |
| Linux | Python 3.10+ — Qt 6 and QtWebEngine installed automatically via pip |

---

## Building a distributable package

See [BUILD.md](BUILD.md) for full instructions. Quick reference:

| Target | Command |
|--------|---------|
| Windows (folder, recommended) | `build.bat` |
| Windows (single .exe) | `build-onefile.bat` |
| Linux (AppImage) | `./build-linux.sh` |

---

## Changelog highlights

### v1.0.0
- **Restore** — one-click recovery of damaged `.part.met` files from the last valid backup, with per-file results and automatic re-scan after restore.
- **Detail modal** — full inspection of any `.part.met`: version, MD4 hash, download progress bar, gap list with byte offsets, all binary tags. Falls back to the backup for damaged / archived files.
- **App icon and branding** — custom icon on window, title bar, and system tray on all platforms.
- **Robustness pass** — all bridge read methods protected against DB lock errors; config guard disables scanning and shows an in-app warning when folders are not configured; log rotation (1 MB × 5 files).
- **System tray** — Qt-based on Linux (no system packages needed), `pystray` on Windows / macOS. Hide-to-tray on window close.
- **State machine** — tracks `OK / PENDING / DAMAGED / REPLACED / REMOVED_OR_COMPLETED`; logs only state transitions, not repeated confirmations.
- **Parser fix (layout 0xE0)** — eMule `.part.met` version `0xE0` stores the download date before the hash (not after); identified and fixed after analysis on 488 real-world files.
- **Gap tag fix** — `gap_start` / `gap_end` tags use 2-byte names in the eMule wire format; now correctly parsed and shown in the detail modal.
- **SQLite WAL** — write-ahead logging for safe concurrent access between the background scanner and the UI thread.
- **Cross-platform build** — PyInstaller specs for Windows (onedir + onefile) and Linux (AppImage via `appimagetool`).

---

## Tech stack

| Component | Technology |
|-----------|-----------|
| Desktop window | [pywebview](https://pywebview.flowrl.com/) — native WebView (WebView2 on Windows, QtWebEngine on Linux) |
| UI framework | [Franken UI](https://www.franken-ui.dev/) 2.1.2 (UIkit 3 components) — loaded locally, no CDN |
| Database | SQLite 3 (Python stdlib) in WAL mode |
| System tray | `QSystemTrayIcon` (Linux) / [pystray](https://github.com/moses-palmer/pystray) (Windows, macOS) |
| Image processing | [Pillow](https://python-pillow.org/) 12.2.0 |
| Desktop notifications | [win11toast](https://github.com/GitHub-Pao/win11toast) (Windows) / [plyer](https://github.com/kivy/plyer) (Linux, macOS) |
| Packaging | [PyInstaller](https://pyinstaller.org/) |

---

## License

MIT — see [LICENSE](LICENSE) for details.
