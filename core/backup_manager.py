"""Backup storage for MetGuardian.

When a ``.part.met`` is read successfully, I copy it into the backup folder and
name it after its global hash, e.g. ``a1b2c3...0f.met``. The hash is the stable
identity of the download for its whole lifetime, so naming the backup by hash
means:

* the same download keeps overwriting the same backup file as it progresses;
* a different download (different hash) lands in a different file and never
  clobbers a previous one.

Backups are intentionally never deleted by the normal flow: even when a slot is
archived (completed, removed or replaced), the physical ``.met`` stays on disk.
That persistence is the whole point of the app.

Atomic writes
-------------
I copy to a temporary file in the same folder and then ``os.replace`` it onto
the final name. ``os.replace`` is atomic on a given filesystem, so a crash mid
copy can never leave a half-written backup in place of a good one.
"""

import os
import re
import shutil
from pathlib import Path

__version__ = "1.0.0"

# The global hash is 16 bytes -> 32 lowercase hex characters. Validating this
# also guarantees the value is a safe file name (no path separators, etc.).
HASH_RE = re.compile(r"^[0-9a-f]{32}$")

# Extension used for the stored backup files.
BACKUP_EXTENSION = ".met"


class BackupManager:
    """Stores ``.part.met`` backups named by their file hash.

    Args:
        backup_folder: destination folder for the backups (set by the user).
    """

    def __init__(self, backup_folder):
        self.backup_folder = Path(backup_folder)

    def folder_is_configured(self) -> bool:
        """Return ``True`` if a non-empty backup folder has been configured.

        Returns:
            bool: whether the backup folder path is set to something usable.
        """
        return str(self.backup_folder).strip() not in ("", ".")

    def backup_path_for(self, file_hash) -> Path:
        """Return the backup path for a given file hash (without creating it).

        Args:
            file_hash (str): the 32-char hex hash.

        Returns:
            Path: ``<backup_folder>/<file_hash>.met``.

        Raises:
            ValueError: if the hash is not a valid 32-char hex string.
        """
        normalized = self._validate_hash(file_hash)
        return self.backup_folder / f"{normalized}{BACKUP_EXTENSION}"

    def store(self, source_path, file_hash) -> str:
        """Copy a ``.part.met`` into the backup folder, named by its hash.

        If a backup with the same hash already exists it is overwritten (same
        download, more parts downloaded). The write is atomic.

        Args:
            source_path: path of the source ``.part.met`` to back up.
            file_hash (str): the 32-char hex hash to name the backup with.

        Returns:
            str: the path of the stored backup file.

        Raises:
            ValueError: if the hash is invalid or the backup folder is unset.
            FileNotFoundError: if the source file does not exist.
        """
        if not self.folder_is_configured():
            raise ValueError("Backup folder is not configured.")

        src = Path(source_path)
        if not src.is_file():
            raise FileNotFoundError(f"Source .met not found: {src}")

        dest = self.backup_path_for(file_hash)
        # Make sure the destination folder exists.
        self.backup_folder.mkdir(parents=True, exist_ok=True)

        # Atomic store: write to a temporary file in the same folder, then
        # replace the final name in one step. copy2 also preserves metadata.
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            shutil.copy2(src, tmp)
            os.replace(tmp, dest)
        finally:
            # If something failed before the replace, clean up the temp file.
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

        return str(dest)

    def exists(self, file_hash) -> bool:
        """Return ``True`` if a backup for the given hash is already stored.

        Args:
            file_hash (str): the 32-char hex hash.

        Returns:
            bool: whether the backup file exists.
        """
        try:
            return self.backup_path_for(file_hash).is_file()
        except ValueError:
            return False

    def remove(self, file_hash) -> bool:
        """Delete a stored backup. Not used by the normal flow.

        Provided for completeness (e.g. a future manual cleanup feature); the
        regular state machine never calls this, because backups are kept.

        Args:
            file_hash (str): the 32-char hex hash.

        Returns:
            bool: ``True`` if a file was deleted, ``False`` if none existed.
        """
        path = self.backup_path_for(file_hash)
        if path.is_file():
            path.unlink()
            return True
        return False

    def list_backups(self) -> list:
        """Return the hashes of all stored backups.

        Returns:
            list[str]: the hash part of every ``*.met`` file in the backup
            folder. Empty if the folder is missing.
        """
        if not self.backup_folder.is_dir():
            return []
        hashes = []
        for child in self.backup_folder.iterdir():
            if child.is_file() and child.suffix == BACKUP_EXTENSION:
                hashes.append(child.stem)
        return sorted(hashes)

    @staticmethod
    def _validate_hash(file_hash) -> str:
        """Validate and normalize a file hash to lowercase hex.

        Args:
            file_hash (str): the candidate hash.

        Returns:
            str: the normalized lowercase hash.

        Raises:
            ValueError: if the value is not a 32-char hex string.
        """
        if not isinstance(file_hash, str):
            raise ValueError(f"Hash must be a string, got {type(file_hash).__name__}")
        normalized = file_hash.strip().lower()
        if not HASH_RE.match(normalized):
            raise ValueError(f"Invalid file hash: {file_hash!r}")
        return normalized
