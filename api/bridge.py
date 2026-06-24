"""Python <-> UI bridge for MetGuardian.

This class is handed to pywebview as ``js_api``. Every public method here is
callable from the front-end as ``window.pywebview.api.<method>(...)`` and its
return value comes back to JavaScript as JSON.

The bridge is deliberately thin: it validates/normalizes inputs, delegates to
the repository and scheduler, and shapes results for the UI. No business logic
lives here.

Pushing updates to the UI
-------------------------
After a background scan finishes, the UI needs to refresh. I expose
:meth:`on_scan_complete`, which the scheduler calls as its
``on_cycle_complete`` callback; from there I push a lightweight browser event
(``metguardian:scan-complete``) into the page via the window. The UI listens
for that event and re-fetches the lists. (Windows notifications for damaged
files are wired in a later step.)
"""

import json
import logging
from pathlib import Path

__version__ = "1.0.0"

logger = logging.getLogger("metguardian.bridge")

# Config keys the settings screen is allowed to write.
ALLOWED_CONFIG_KEYS = {
    "temp_folder",
    "backup_folder",
    "scan_interval_seconds",
    "mtime_guard_seconds",
    "theme",
}

# Browser event name the UI listens for to refresh after a scan.
SCAN_EVENT = "metguardian:scan-complete"


def report_to_dict(report) -> dict:
    """Convert a :class:`ScanReport` into a JSON-serializable dict.

    Args:
        report: the report returned by the state machine, or ``None``.

    Returns:
        dict: a compact, serializable summary.
    """
    if report is None:
        return {"ran": False, "error": "Scan did not run."}
    return {
        "ran": report.ran,
        "error": report.error,
        "scanned": report.scanned,
        "ok": report.ok,
        "inaccessible": report.inaccessible,
        "damaged": report.damaged,
        "archived": report.archived,
        "newly_damaged": list(report.newly_damaged),
        "transitions": report.transitions,
    }


class Bridge:
    """The ``js_api`` object exposed to the pywebview front-end.

    Args:
        repository: the data-access layer.
        scheduler: the scan scheduler (optional, but needed for scans).
    """

    def __init__(self, repository, scheduler=None):
        self.repo = repository
        self.scheduler = scheduler
        self._window = None  # set by app.py once the window exists

    def set_window(self, window):
        """Attach the pywebview window, enabling UI push and folder dialogs.

        Args:
            window: the pywebview window object.
        """
        self._window = window

    # ------------------------------------------------------------------ #
    # Read methods (called by the UI to populate the screens)
    # ------------------------------------------------------------------ #

    def get_active_files(self) -> list:
        """Return the currently monitored files.

        Returns:
            list[dict]: active files, ordered by slot number.
        """
        return self.repo.list_active()

    def get_archive(self) -> list:
        """Return the archived files (newest first).

        Returns:
            list[dict]: archived files.
        """
        return self.repo.list_archive()

    def get_log(self, limit=200) -> list:
        """Return the most recent log entries (newest first).

        Args:
            limit (int): maximum number of entries.

        Returns:
            list[dict]: log entries.
        """
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 200
        return self.repo.list_log(limit=limit)

    def get_config(self) -> dict:
        """Return the whole configuration.

        Returns:
            dict: ``{key: value}`` for every setting.
        """
        return self.repo.all_config()

    def get_status(self) -> dict:
        """Return a small status snapshot for the header/dashboard.

        Returns:
            dict: scheduler state, counts and the scan interval.
        """
        return {
            "scheduler_running": bool(self.scheduler and self.scheduler.is_running()),
            "active_count": len(self.repo.list_active()),
            "archive_count": len(self.repo.list_archive()),
            "scan_interval_seconds": self.repo.get_config("scan_interval_seconds"),
            "temp_folder": self.repo.get_config("temp_folder"),
            "backup_folder": self.repo.get_config("backup_folder"),
        }

    # ------------------------------------------------------------------ #
    # Write / action methods
    # ------------------------------------------------------------------ #

    def save_config(self, settings) -> dict:
        """Persist settings, then run a scan so changes take effect at once.

        Only keys in :data:`ALLOWED_CONFIG_KEYS` are accepted; anything else is
        ignored. Folder paths are validated leniently: a missing folder does not
        block saving (the user may set it before the drive is available), but a
        warning is returned so the UI can show it.

        Args:
            settings (dict): the settings to save.

        Returns:
            dict: ``{"ok", "config", "warnings", "scan"}``.
        """
        try:
            if not isinstance(settings, dict):
                return {"ok": False, "error": "Invalid settings payload."}

            warnings = []
            for key, value in settings.items():
                if key not in ALLOWED_CONFIG_KEYS:
                    continue  # silently ignore unknown keys
                self.repo.set_config(key, value)

            # Lenient validation of the folders, for user feedback only.
            temp_folder = (self.repo.get_config("temp_folder") or "").strip()
            backup_folder = (self.repo.get_config("backup_folder") or "").strip()
            if temp_folder and not Path(temp_folder).is_dir():
                warnings.append("The temp folder does not exist or is not a directory.")
            if not backup_folder:
                warnings.append("No backup folder is set; backups cannot be stored.")

            # Apply immediately by running a scan now (if we have a scheduler).
            scan = report_to_dict(self.scheduler.scan_now()) if self.scheduler else None

            return {
                "ok": True,
                "config": self.repo.all_config(),
                "warnings": warnings,
                "scan": scan,
            }
        except Exception as exc:
            logger.exception("save_config failed")
            return {"ok": False, "error": str(exc)}

    def scan_now(self) -> dict:
        """Trigger an immediate scan and return its summary.

        Returns:
            dict: the serialized scan report, or an error structure.
        """
        try:
            if not self.scheduler:
                return {"ran": False, "error": "Scheduler is not available."}
            return report_to_dict(self.scheduler.scan_now())
        except Exception as exc:
            logger.exception("scan_now failed")
            return {"ran": False, "error": str(exc)}

    def set_theme(self, theme) -> dict:
        """Persist the UI theme (light/dark/...). 

        Args:
            theme (str): the theme identifier.

        Returns:
            dict: ``{"ok", "theme"}``.
        """
        try:
            theme = str(theme)
            self.repo.set_config("theme", theme)
            return {"ok": True, "theme": theme}
        except Exception as exc:
            logger.exception("set_theme failed")
            return {"ok": False, "error": str(exc)}

    def pick_folder(self, title="Select a folder") -> dict:
        """Open the native folder picker and return the chosen path.

        Requires the window to be attached. Used by the settings screen to set
        the temp and backup folders.

        Args:
            title (str): dialog title.

        Returns:
            dict: ``{"ok", "path"}`` where ``path`` is ``None`` if cancelled.
        """
        try:
            if self._window is None:
                return {"ok": False, "error": "Window not available."}
            # Import lazily so the module imports fine in non-GUI contexts/tests.
            import webview
            result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if not result:
                return {"ok": True, "path": None}  # user cancelled
            # create_file_dialog returns a tuple/list of paths.
            return {"ok": True, "path": str(result[0])}
        except Exception as exc:
            logger.exception("pick_folder failed")
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------ #
    # Scheduler callback -> push a refresh to the UI
    # ------------------------------------------------------------------ #

    def on_scan_complete(self, report):
        """Scheduler callback: push a refresh event to the UI after a scan.

        Args:
            report: the :class:`ScanReport` from the cycle.
        """
        payload = {
            "scanned": report.scanned if report else 0,
            "newly_damaged": list(report.newly_damaged) if report else [],
            "ran": bool(report and report.ran),
        }
        self._emit(SCAN_EVENT, payload)

    def _emit(self, event_name, payload):
        """Dispatch a CustomEvent into the page, if a window is attached.

        Args:
            event_name (str): the browser event name.
            payload (dict): JSON-serializable detail for the event.
        """
        if self._window is None:
            return
        try:
            js = (
                "window.dispatchEvent(new CustomEvent("
                f"{json.dumps(event_name)}, {{detail: {json.dumps(payload)}}}))"
            )
            self._window.evaluate_js(js)
        except Exception:
            logger.exception("Failed to emit UI event %s", event_name)
