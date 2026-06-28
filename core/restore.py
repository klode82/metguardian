"""Restore manager for MetGuardian.

Handles copying backed-up part.met files back into the eMule temp folder so
that a damaged slot can recover on the next scan cycle.

The caller is responsible for ensuring eMule is closed before invoking this.
MetGuardian monitors a folder, not a process, and the temp folder may be on a
different machine or VM, so it cannot verify whether eMule is running.
"""

import logging
import shutil
from pathlib import Path

__version__ = "1.0.0"

logger = logging.getLogger("metguardian.restore")


class RestoreManager:
    """Restores one or more DAMAGED part.met files from their last valid backup.

    For each requested slot the manager:
    1. Validates that the slot is DAMAGED and has a backup on disk.
    2. Deletes ``<temp>/<num>.part.met`` and ``<temp>/<num>.part.met.bak``
       if they exist.
    3. Copies (never moves) the stored backup to ``<temp>/<num>.part.met``.

    Errors for individual files are captured in the result dict without
    stopping processing of the remaining files.
    """

    def restore_files(
        self,
        numbers: list,
        temp_folder: str,
        active_records: dict,
    ) -> dict:
        """Copy backups back into the temp folder for the given slot numbers.

        Args:
            numbers: slot numbers to restore (strings, e.g. ``["001", "032"]``).
            temp_folder: path to the eMule temp folder.
            active_records: ``{number: record_dict}`` for the requested slots,
                as returned by the repository (pre-fetched by the bridge).

        Returns:
            dict: ``{number: {"ok": bool, "error": str | None}}``.
        """
        temp = Path(temp_folder).expanduser() if temp_folder else None
        return {
            number: self._restore_one(number, temp, active_records)
            for number in numbers
        }

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _restore_one(self, number: str, temp, active_records: dict) -> dict:
        record = active_records.get(number)
        if not record:
            return {"ok": False, "error": "Slot not found in active files."}

        if record.get("state") != "DAMAGED":
            return {"ok": False, "error": "File is not in DAMAGED state."}

        backup_path = record.get("backup_path")
        if not backup_path:
            return {"ok": False, "error": "No backup path recorded for this slot."}

        src = Path(backup_path)
        if not src.is_file():
            return {"ok": False, "error": f"Backup not found on disk: {backup_path}"}

        if not temp or not temp.is_dir():
            return {"ok": False, "error": "Temp folder is not set or does not exist."}

        try:
            dest_met = temp / f"{number}.part.met"
            dest_bak = temp / f"{number}.part.met.bak"

            if dest_met.exists():
                dest_met.unlink()
            if dest_bak.exists():
                dest_bak.unlink()

            shutil.copy2(src, dest_met)
            logger.info("Restored slot %s from %s to %s", number, src, dest_met)
            return {"ok": True, "error": None}

        except OSError as exc:
            logger.error("Failed to restore slot %s: %s", number, exc)
            return {"ok": False, "error": str(exc)}
