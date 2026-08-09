## 🎉 First public release

MetGuardian watches your eMule / aMule temp folder and keeps a reliable,
independent backup of every `.part.met` file — the index that tells eMule
which chunks of a download have already been transferred.

When eMule crashes and corrupts that index, MetGuardian restores it in one
click, without losing a single downloaded byte.

---

### What's in v1.0.1

- **Automatic rolling backups** — scans the temp folder every N minutes and
  saves a backup keyed by MD4 hash whenever a file is healthy
- **One-click restore** — detects damaged files automatically and restores
  them from the last valid backup; triggers a re-scan immediately after
- **Download detail modal** — visual progress bar, gap list with byte offsets,
  all binary tags from the `.part.met`
- **State machine + event log** — tracks `OK / Pending / Damaged / Replaced /
  Removed` and logs only real state changes, never repeated confirmations
- **Desktop notifications** — single alert the moment a file is damaged
  (Windows: native toast; Linux: plyer)
- **System tray** — hides on window close and keeps scanning in the background
- **Dark mode** — persisted across sessions

---

### Download

| Platform | File |
|----------|------|
| Windows 10 / 11 (x64) — folder | `MetGuardian-1.0.1-win.zip` |
| Windows 10 / 11 (x64) — single exe | `MetGuardian-1.0.1.exe` |
| Linux x86_64 | `MetGuardian-1.0.1-x86_64.AppImage` |

> **Windows**: requires the
> [Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)
> — already included in Windows 10 20H2+ and all Windows 11 installations.

> **Linux AppImage**: `chmod +x MetGuardian-1.0.1-x86_64.AppImage` then run it.
> `data/` and `logs/` are created in the same folder as the AppImage.

---

*Tested on Windows 11 and Linux (x86_64).
Issues and feedback welcome — open a GitHub issue.*
