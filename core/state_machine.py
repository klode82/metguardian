"""The state machine: the heart of MetGuardian.

This module ties the other pieces together and runs a single *scan cycle*:

1. read the configured folders and the mtime guard;
2. scan the temp folder for ``.part.met`` files (``TempScanner``);
3. read and classify each one (``MetReader``);
4. compare the detected state with what the database already knows and apply
   the right action (store/refresh backup, archive, flag as damaged, ...);
5. archive any slot that the database knew about but that is no longer present;
6. return a :class:`ScanReport` summarizing what changed.

Golden rule: I write a log entry ONLY when a slot changes state, never on
repeated confirmations of the same state.

The confirmed state machine
---------------------------
For a slot identified by its number (e.g. ``493``):

* **OK, same hash, was already OK** -> overwrite the backup (more parts
  downloaded), refresh the timestamp, NO log.
* **OK, same hash, was not OK before** -> back to OK: refresh backup, log it.
* **OK, different hash than before** -> a new download took the slot: archive the
  previous one (``REPLACED``), store the new backup, log it.
* **OK, brand new slot** -> first time seen valid: store backup, log it.
* **INACCESSIBLE** -> do NOT touch the hash/backup; only change the state. Shown
  in the list, never notified to Windows.
* **DAMAGED** -> do NOT storicize, do NOT touch the backup; log it and flag it
  for a Windows notification (only on the transition into DAMAGED).
* **Gone** (in the DB but no longer in the temp folder) -> archive it
  (``REMOVED_OR_COMPLETED``); the physical backup is kept on disk.

When a slot becomes INACCESSIBLE or DAMAGED I must NOT overwrite its stored
hash/backup, so I use ``set_active_state`` (state only) rather than
``upsert_active`` (which would also rewrite hash/backup).
"""

import logging
from dataclasses import dataclass, field

from db.repository import (
    Repository,
    STATE_OK,
    STATE_INACCESSIBLE,
    STATE_DAMAGED,
    REASON_REPLACED,
    REASON_REMOVED_OR_COMPLETED,
)
from .reader import MetReader
from .scanner import TempScanner
from .backup_manager import BackupManager

__version__ = "1.0.0"

# Logger for transitions and anomalies. The file handler is configured later,
# during application start-up; here I just emit records.
logger = logging.getLogger("metguardian.state_machine")

# Marker used in event_log.new_state when a slot leaves the active set.
LOG_STATE_ARCHIVED = "ARCHIVED"

# Config keys (kept here so I don't sprinkle string literals around).
CFG_TEMP_FOLDER = "temp_folder"
CFG_BACKUP_FOLDER = "backup_folder"
CFG_MTIME_GUARD = "mtime_guard_seconds"


@dataclass
class ScanReport:
    """Summary of a single scan cycle.

    Attributes:
        ran (bool): ``True`` if the cycle actually scanned; ``False`` if it
            could not run (e.g. folders not configured).
        error (str | None): a human-readable reason when ``ran`` is ``False``.
        scanned (int): number of ``.part.met`` files found.
        transitions (list[dict]): one dict per state change, each with
            ``number``, ``previous_state``, ``new_state`` and ``message``.
        newly_damaged (list[str]): slot numbers that just became DAMAGED this
            cycle (what the notifier should warn about).
        ok (int): count of slots seen OK this cycle.
        inaccessible (int): count of slots seen INACCESSIBLE this cycle.
        damaged (int): count of slots seen DAMAGED this cycle.
        archived (int): count of slots archived this cycle (replaced or gone).
    """

    ran: bool = True
    error: str = None
    scanned: int = 0
    transitions: list = field(default_factory=list)
    newly_damaged: list = field(default_factory=list)
    ok: int = 0
    inaccessible: int = 0
    damaged: int = 0
    archived: int = 0


class StateMachine:
    """Runs scan cycles and keeps the database in sync with the temp folder.

    Args:
        repository (Repository): the data-access layer.
        reader (MetReader | None): the file reader/classifier. If omitted I
            create one.
    """

    def __init__(self, repository: Repository, reader: MetReader = None):
        self.repo = repository
        self.reader = reader or MetReader()

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    def run_cycle(self) -> ScanReport:
        """Run one full scan cycle and return what happened.

        Returns:
            ScanReport: the summary of this cycle.
        """
        report = ScanReport()

        temp_folder = (self.repo.get_config(CFG_TEMP_FOLDER) or "").strip()
        backup_folder = (self.repo.get_config(CFG_BACKUP_FOLDER) or "").strip()
        mtime_guard = self._read_int_config(CFG_MTIME_GUARD, default=10)

        # Configuration must be complete before I touch anything.
        if not temp_folder or not backup_folder:
            report.ran = False
            report.error = "Temp folder and/or backup folder are not configured."
            return report

        scanner = TempScanner(temp_folder)
        backup = BackupManager(backup_folder)

        # Scan the temp folder.
        try:
            entries = scanner.scan()
        except (FileNotFoundError, NotADirectoryError) as exc:
            report.ran = False
            report.error = str(exc)
            logger.warning("Scan aborted: %s", exc)
            return report

        report.scanned = len(entries)
        present_numbers = set()

        # Process each present file. One bad file must not kill the cycle.
        for entry in entries:
            present_numbers.add(entry.number)
            try:
                self._process_present(entry, backup, mtime_guard, report)
            except Exception:
                # Unexpected error on this file: record it and move on.
                logger.exception("Error while processing %s", entry.path)
                report.transitions.append(
                    {
                        "number": entry.number,
                        "previous_state": None,
                        "new_state": "ERROR",
                        "message": f"{entry.number}: unexpected error while processing",
                    }
                )

        # Anything the DB still lists as active but that is no longer present
        # has disappeared (completed or deleted) -> archive it.
        try:
            self._archive_disappeared(present_numbers, report)
        except Exception:
            logger.exception("Error while archiving disappeared slots")

        return report

    # ------------------------------------------------------------------ #
    # Per-file processing
    # ------------------------------------------------------------------ #

    def _process_present(self, entry, backup, mtime_guard, report):
        """Apply the state machine to a single present file.

        Args:
            entry (ScanEntry): the scanned file (number + path).
            backup (BackupManager): the backup store.
            mtime_guard (int): the mtime-guard window in seconds.
            report (ScanReport): the report to update.
        """
        result = self.reader.read(entry.path, mtime_guard_seconds=mtime_guard)
        prev = self.repo.get_active_by_number(entry.number)
        prev_state = prev["state"] if prev else None
        prev_hash = prev["file_hash"] if prev else None

        if result.state == STATE_OK:
            report.ok += 1
            self._handle_ok(entry, result, prev_state, prev_hash, backup, report)
        elif result.state == STATE_INACCESSIBLE:
            report.inaccessible += 1
            self._handle_inaccessible(entry, prev, prev_state, report)
        elif result.state == STATE_DAMAGED:
            report.damaged += 1
            self._handle_damaged(entry, prev, prev_state, prev_hash, report)

    def _handle_ok(self, entry, result, prev_state, prev_hash, backup, report):
        """Handle a slot that is currently readable and valid."""
        new_hash = result.file_hash

        # A new download replaced a previous, different one on the same slot.
        if prev_hash is not None and prev_hash != new_hash:
            self.repo.archive_active(entry.number, REASON_REPLACED)
            report.archived += 1
            backup_path = backup.store(entry.path, new_hash)
            self.repo.upsert_active(
                entry.number, new_hash, result.file_name, STATE_OK, backup_path
            )
            self._log(
                report, entry.number, new_hash, prev_state, STATE_OK,
                f"{entry.number}: new download replaced the previous one (archived)",
            )
            return

        # Same hash and already OK: just refresh the backup and timestamp.
        if prev_state == STATE_OK and prev_hash == new_hash:
            backup_path = backup.store(entry.path, new_hash)
            self.repo.upsert_active(
                entry.number, new_hash, result.file_name, STATE_OK, backup_path
            )
            # No state change -> no log entry.
            return

        # Otherwise this is a transition into OK (first time, or recovering from
        # inaccessible/damaged with the same/no previous hash).
        backup_path = backup.store(entry.path, new_hash)
        self.repo.upsert_active(
            entry.number, new_hash, result.file_name, STATE_OK, backup_path
        )
        message = (
            f"{entry.number}: first seen, OK"
            if prev_state is None
            else f"{entry.number}: back to OK"
        )
        self._log(report, entry.number, new_hash, prev_state, STATE_OK, message)

    def _handle_inaccessible(self, entry, prev, prev_state, report):
        """Handle a slot that is present but cannot be read right now."""
        if prev is None:
            # First time seen, and not readable: create a tracking row with no
            # hash/backup yet.
            self.repo.upsert_active(entry.number, None, None, STATE_INACCESSIBLE, None)
            self._log(
                report, entry.number, None, None, STATE_INACCESSIBLE,
                f"{entry.number}: inaccessible",
            )
            return

        if prev_state == STATE_INACCESSIBLE:
            return  # no change -> no log

        # Was OK or DAMAGED: change state only, preserving hash/backup.
        self.repo.set_active_state(entry.number, STATE_INACCESSIBLE)
        self._log(
            report, entry.number, prev["file_hash"], prev_state, STATE_INACCESSIBLE,
            f"{entry.number}: inaccessible",
        )

    def _handle_damaged(self, entry, prev, prev_state, prev_hash, report):
        """Handle a slot that opens but cannot be parsed (genuinely corrupted)."""
        if prev is None:
            self.repo.upsert_active(entry.number, None, None, STATE_DAMAGED, None)
            self._log(
                report, entry.number, None, None, STATE_DAMAGED,
                f"{entry.number}: damaged",
            )
            report.newly_damaged.append(entry.number)
            return

        if prev_state == STATE_DAMAGED:
            return  # already known as damaged -> no log, no new notification

        # Was OK or INACCESSIBLE: change state only, preserving hash/backup.
        self.repo.set_active_state(entry.number, STATE_DAMAGED)
        self._log(
            report, entry.number, prev_hash, prev_state, STATE_DAMAGED,
            f"{entry.number}: damaged",
        )
        report.newly_damaged.append(entry.number)

    def _archive_disappeared(self, present_numbers, report):
        """Archive every active slot that is no longer in the temp folder."""
        for row in self.repo.list_active():
            number = row["number"]
            if number in present_numbers:
                continue
            prev_state = row["state"]
            file_hash = row["file_hash"]
            self.repo.archive_active(number, REASON_REMOVED_OR_COMPLETED)
            report.archived += 1
            self._log(
                report, number, file_hash, prev_state, LOG_STATE_ARCHIVED,
                f"{number}: removed or completed (archived, backup kept)",
            )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _log(self, report, number, file_hash, previous_state, new_state, message):
        """Record a transition in the DB log and in the report.

        I only ever call this on an actual state change.
        """
        self.repo.add_log(number, file_hash, previous_state, new_state, message)
        logger.info("%s (%s -> %s)", message, previous_state, new_state)
        report.transitions.append(
            {
                "number": number,
                "previous_state": previous_state,
                "new_state": new_state,
                "message": message,
            }
        )

    def _read_int_config(self, key, default):
        """Read an integer config value, falling back to ``default`` on error."""
        raw = self.repo.get_config(key)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
