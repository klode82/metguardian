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
from pathlib import Path

import webview  # pywebview

from core.logging_setup import setup_logging
from db.database import Database
from db.repository import Repository
from core.state_machine import StateMachine
from scheduler.worker import ScanScheduler
from api.bridge import Bridge

__version__ = "1.0.0"

# Project root and the UI entry file.
PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_HTML = PROJECT_ROOT / "ui" / "index.html"

# Initial window size.
WINDOW_TITLE = "MetGuardian"
WINDOW_WIDTH = 1140
WINDOW_HEIGHT = 760
WINDOW_MIN_SIZE = (820, 560)


def main():
    """Start the application and block until the window is closed."""
    logger = setup_logging()
    logger.info("MetGuardian starting (v%s).", __version__)

    if not INDEX_HTML.is_file():
        raise FileNotFoundError(f"UI entry file not found: {INDEX_HTML}")

    # Core wiring. The database is created (with its schema) on first use.
    database = Database()
    repository = Repository(database)
    state_machine = StateMachine(repository)

    # The bridge needs the scheduler, and the scheduler needs the bridge as its
    # post-cycle callback, so I build the bridge first and inject the scheduler.
    bridge = Bridge(repository)
    scheduler = ScanScheduler(
        state_machine,
        repository,
        on_cycle_complete=bridge.on_scan_complete,
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

    def on_started():
        """Runs once the GUI loop is up: start scanning in the background."""
        logger.info("GUI started; launching scheduler.")
        scheduler.start()

    try:
        # Blocks here until the window is closed.
        webview.start(on_started)
    finally:
        # Window closed (or an error occurred): stop the background thread.
        logger.info("Window closed; stopping scheduler.")
        scheduler.stop()
        logger.info("MetGuardian stopped.")


if __name__ == "__main__":
    main()
