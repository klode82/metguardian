"""MetGuardian - application entry point (minimal bootstrap).

This wires the pieces together and opens the desktop window:

    logging -> database -> state machine -> scheduler -> bridge -> window

What this minimal version does NOT do yet (coming in later steps):
* system tray with Open / Exit (Step 11) - for now, closing the window quits;
* Windows toast notifications for damaged files (Step 10);
* a Settings screen (Step 9) - until then, folders are set via config.

Run it from the project root:

    python app.py
"""

import logging
import os
import sys
from pathlib import Path

import webview  # pywebview

# PyInstaller layout (onedir, v6+):
#   dist\MetGuardian\MetGuardian.exe          ← sys.executable
#   dist\MetGuardian\_internal\ui\            ← sys._MEIPASS  (read-only bundle)
#   dist\MetGuardian\_internal\db\schema.sql
#   dist\MetGuardian\data\                    ← writable at runtime (DB, logs)
#
# _BUNDLE  = where bundled read-only assets live (ui/, db/schema.sql)
# _HERE    = writable root next to the exe (data/, logs/)
if getattr(sys, "frozen", False):
    _BUNDLE = Path(sys._MEIPASS)
    _HERE   = Path(sys.executable).resolve().parent
else:
    _BUNDLE = Path(__file__).resolve().parent
    _HERE   = _BUNDLE

from core.logging_setup import setup_logging
from db.database import Database
from db.repository import Repository
from core.state_machine import StateMachine
from scheduler.worker import ScanScheduler
from api.bridge import Bridge
from core.notifier import Notifier
from tray.tray_icon import TrayIcon

__version__ = "1.0.0"

# Read-only resources come from the bundle; writable data lives next to the exe.
PROJECT_ROOT = _HERE
INDEX_HTML = _BUNDLE / "ui" / "index.html"
APP_ICON   = _BUNDLE / "ui" / "assets" / "icon.png"

# Initial window size.
WINDOW_TITLE = "MetGuardian"
WINDOW_WIDTH = 1140
WINDOW_HEIGHT = 760
WINDOW_MIN_SIZE = (820, 560)


def _configure_linux_webengine():
    """Work around QtWebEngine rendering issues on some Linux compositors.

    On certain Wayland setups QtWebEngine cannot share GPU textures and the
    window renders black ("dma_buf acquisition failure / Compositor returned
    null texture"). Disabling GPU acceleration fixes it. I set this before Qt
    starts, and only on Linux; Windows (WebView2) and macOS are unaffected.
    setdefault means a value the user exported by hand still wins.
    """
    if sys.platform.startswith("linux"):
        os.environ.setdefault(
            "QTWEBENGINE_CHROMIUM_FLAGS",
            "--disable-gpu --disable-gpu-compositing",
        )


def main():
    """Start the application and block until the window is closed."""
    _configure_linux_webengine()

    logger = setup_logging()
    logger.info("MetGuardian starting (v%s).", __version__)

    if not INDEX_HTML.is_file():
        raise FileNotFoundError(f"UI entry file not found: {INDEX_HTML}")

    # Core wiring. The database is created (with its schema) on first use.
    database = Database()
    repository = Repository(database)
    state_machine = StateMachine(repository)

    # The bridge needs the scheduler, and the scheduler needs a post-cycle
    # callback. I build the bridge and the notifier first, then a small
    # combined callback that (1) refreshes the UI and (2) notifies about any
    # files that just became damaged. This keeps the notifier decoupled from
    # both the bridge and the scheduler.
    bridge = Bridge(repository)
    notifier = Notifier()

    def on_cycle_complete(report):
        bridge.on_scan_complete(report)
        if report is not None:
            notifier.notify_damaged(report.newly_damaged)

    scheduler = ScanScheduler(
        state_machine,
        repository,
        on_cycle_complete=on_cycle_complete,
    )
    bridge.scheduler = scheduler

    # Create the desktop window. The bridge is exposed to JavaScript as
    # window.pywebview.api.*; the page is our local UI.
    window = webview.create_window(
        WINDOW_TITLE,
        url=str(INDEX_HTML),
        js_api=bridge,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
        text_select=False,
    )
    # Let the bridge push refresh events and open native folder dialogs.
    bridge.set_window(window)

    def _set_window_icon():
        """Set the Qt application icon from ui/assets/icon.png (Linux only)."""
        if not sys.platform.startswith("linux") or not APP_ICON.is_file():
            return
        try:
            import io
            from PIL import Image
            from qtpy.QtWidgets import QApplication
            from qtpy.QtGui import QIcon, QPixmap
            from qtpy.QtCore import QByteArray
            buf = io.BytesIO()
            Image.open(APP_ICON).save(buf, format="PNG")
            pix = QPixmap()
            pix.loadFromData(QByteArray(buf.getvalue()))
            QApplication.instance().setWindowIcon(QIcon(pix))
        except Exception:
            logger.exception("Could not set window icon.")

    # Shared flags between the GUI thread and the tray thread.
    state = {"quitting": False, "tray_ok": False}

    def show_window():
        """Tray 'Open': bring the window back."""
        try:
            window.show()
        except Exception:
            logger.exception("Failed to show window")

    def do_exit():
        """Tray 'Exit': really quit (stop scheduler + tray + destroy window)."""
        logger.info("Exit requested from tray.")
        state["quitting"] = True
        scheduler.stop()
        tray.stop()
        try:
            window.destroy()
        except Exception:
            logger.exception("Failed to destroy window")

    tray = TrayIcon(app_name=WINDOW_TITLE, on_open=show_window, on_exit=do_exit)

    def on_closing():
        """Window close: hide to tray instead of quitting (when tray is up).

        If the tray is not available, allow the real close so the user is never
        stuck with an unreachable background process.
        """
        if state["quitting"] or not state["tray_ok"]:
            return True  # allow the window to close / app to quit
        window.hide()
        return False     # cancel the close; keep running in the tray

    window.events.closing += on_closing

    def on_started():
        """Runs once the GUI loop is up: start scanning and the tray."""
        logger.info("GUI started; launching scheduler.")
        _set_window_icon()
        scheduler.start()
        state["tray_ok"] = tray.start()
        if not state["tray_ok"]:
            logger.warning(
                "No system tray available; closing the window will quit the app."
            )

    try:
        # Force the Qt backend on Linux: we install Qt via pip and do not want
        # pywebview to probe GTK first (which both prints a scary traceback and
        # could pick a broken backend). Windows/macOS use their default.
        gui = "qt" if sys.platform.startswith("linux") else None
        # Blocks here until the window is destroyed.
        webview.start(on_started, gui=gui)
    finally:
        # Window closed (or an error occurred): stop background work.
        logger.info("Shutting down; stopping scheduler and tray.")
        scheduler.stop()
        tray.stop()
        logger.info("MetGuardian stopped.")


if __name__ == "__main__":
    main()
