"""Temp-folder scanner for MetGuardian.

This module answers one question: *which ``.part.met`` files are currently in
the eMule / aMule temp folder, and what is each one's slot number?*

It deliberately looks only at ``*.part.met`` and ignores everything else:

* ``493.part``          -> the actual data file, not my concern;
* ``493.part.met``      -> YES, this is what I track;
* ``493.part.met.bak``  -> eMule's own backup, explicitly ignored (it is exactly
                           the unreliable safety net this whole app exists to
                           replace).

The scanner does not read or parse the files; it only finds them and pairs each
with its number. Reading and classification happen later, in ``core/reader.py``.
"""

from pathlib import Path
from dataclasses import dataclass

__version__ = "1.0.0"

# Files I care about end with this; eMule's own backup adds ".bak" on top.
PART_MET_SUFFIX = ".part.met"
BAK_SUFFIX = ".bak"


@dataclass
class ScanEntry:
    """A single ``.part.met`` file found in the temp folder.

    Attributes:
        number (str): slot number taken from the file name (e.g. ``"493"``).
        path (str): absolute path to the ``.part.met`` file.
    """

    number: str
    path: str


class TempScanner:
    """Lists the ``.part.met`` files in a configured temp folder.

    Args:
        temp_folder: path of the eMule / aMule temp folder to scan.
    """

    def __init__(self, temp_folder):
        self.temp_folder = Path(temp_folder)

    def folder_is_valid(self) -> bool:
        """Return ``True`` if the configured temp folder is an existing directory.

        Returns:
            bool: whether the folder exists and is a directory.
        """
        return self.temp_folder.is_dir()

    def scan(self) -> list:
        """Find all ``.part.met`` files in the temp folder.

        Returns:
            list[ScanEntry]: one entry per ``.part.met`` file, sorted by slot
            number (numerically when the numbers are digits, otherwise
            alphabetically).

        Raises:
            FileNotFoundError: if the temp folder does not exist.
            NotADirectoryError: if the configured path is not a directory.
        """
        if not self.temp_folder.exists():
            raise FileNotFoundError(f"Temp folder does not exist: {self.temp_folder}")
        if not self.temp_folder.is_dir():
            raise NotADirectoryError(f"Temp path is not a directory: {self.temp_folder}")

        entries = []
        for child in self.temp_folder.iterdir():
            if not child.is_file():
                continue  # skip subfolders and anything that is not a real file
            name = child.name
            # Keep only "*.part.met"; this naturally excludes "*.part" and
            # "*.part.met.bak" (the latter ends with ".bak", not ".part.met").
            if not name.endswith(PART_MET_SUFFIX):
                continue
            # Belt-and-braces guard against eMule's own backup file.
            if name.endswith(PART_MET_SUFFIX + BAK_SUFFIX):
                continue
            number = name[: -len(PART_MET_SUFFIX)]
            entries.append(ScanEntry(number=number, path=str(child.resolve())))

        entries.sort(key=self._sort_key)
        return entries

    @staticmethod
    def _sort_key(entry):
        """Sort numeric slot numbers by value, others alphabetically.

        Args:
            entry (ScanEntry): the entry to derive a sort key for.

        Returns:
            tuple: a key that puts digit-only numbers (sorted by int value)
            before non-numeric ones (sorted as text).
        """
        n = entry.number
        if n.isdigit():
            return (0, int(n), "")
        return (1, 0, n)
