"""State classification for ``.part.met`` files.

This module sits one level above :class:`~core.parser.PartMetParser`. The parser
can only say "parsed" or ``None``; it cannot tell *why* it failed. Here I turn
the outcome of a read into a precise state that the rest of the application
understands:

* ``OK``           - the file is readable and valid; I also extract the three
                     pieces of information I care about (number, file hash,
                     file name);
* ``INACCESSIBLE`` - the file is present but I cannot read it right now (locked
                     by eMule, permissions, or it is in the middle of being
                     written);
* ``DAMAGED``      - the file opens but cannot be parsed, and it was NOT written
                     recently, so it is genuinely corrupted.

The "mtime guard"
-----------------
eMule may be writing the ``.met`` exactly while I scan, which would make a valid
file look corrupted. To avoid crying wolf, if a parse fails *but* the file was
modified within the last ``mtime_guard_seconds`` I report ``INACCESSIBLE``
instead of ``DAMAGED`` (no Windows notification). This uses a single timestamp
read, no counters or accumulated state.

Note on the state strings
-------------------------
The string values below (``"OK"``, ``"INACCESSIBLE"``, ``"DAMAGED"``) are the
shared vocabulary stored in the database. They intentionally match the
``STATE_*`` constants in ``db/repository.py``.
"""

import os
import time
from pathlib import Path
from dataclasses import dataclass

from .parser import PartMetParser

__version__ = "1.0.0"

# Domain state vocabulary (kept in sync with db/repository.py).
STATE_OK = "OK"
STATE_INACCESSIBLE = "INACCESSIBLE"
STATE_DAMAGED = "DAMAGED"

# A part.met file is named like "493.part.met"; this is the trailing suffix.
PART_MET_SUFFIX = ".part.met"

# The eMule global file hash is 16 raw bytes (32 hex characters).
EXPECTED_HASH_LEN = 16


@dataclass
class ReadResult:
    """Outcome of reading a single ``.part.met`` file.

    Attributes:
        number (str): slot number taken from the file name (e.g. ``"493"``).
        state (str): one of ``STATE_OK`` / ``STATE_INACCESSIBLE`` / ``STATE_DAMAGED``.
        file_hash (str | None): hex global hash, populated only when ``OK``.
        file_name (str | None): the ``filename`` tag value, populated only when ``OK``.
        gaps (list | None): list of ``(start, end)`` gap tuples when ``OK``.
        path (str): the path that was read.
    """

    number: str
    state: str
    file_hash: str | None = None
    file_name: str | None = None
    gaps: list | None = None
    path: str | None = None


class MetReader:
    """Reads a ``.part.met`` file and classifies its state.

    Args:
        parser (PartMetParser | None): the low-level parser to use. If omitted,
            I create my own instance. Reusing one instance is safe because the
            parser resets its state at the start of every parse.
    """

    def __init__(self, parser=None):
        self.parser = parser or PartMetParser()

    @staticmethod
    def number_from_path(path) -> str:
        """Extract the slot number from a part.met file path.

        ``"/tmp/493.part.met"`` -> ``"493"``.

        Args:
            path: the file path (str or Path).

        Returns:
            str: the slot number.
        """
        name = Path(path).name
        if name.endswith(PART_MET_SUFFIX):
            return name[: -len(PART_MET_SUFFIX)]
        # Fallback for unexpected names: drop the last extension only.
        return Path(path).stem

    def read(self, path, mtime_guard_seconds: int = 10) -> ReadResult:
        """Read a ``.part.met`` file and return its classified state.

        Args:
            path: path of the ``.part.met`` file.
            mtime_guard_seconds (int): if a parse fails but the file was
                modified within this many seconds, I treat it as
                ``INACCESSIBLE`` rather than ``DAMAGED``.

        Returns:
            ReadResult: the state plus, when ``OK``, the extracted information.
        """
        p = Path(path)
        number = self.number_from_path(p)

        # 1) Can I open the file at all? A 1-byte read confirms access without
        #    reading the whole thing. Any OS-level error means INACCESSIBLE
        #    (locked, permissions, vanished mid-scan, or it is a directory).
        try:
            with open(p, "rb") as fh:
                fh.read(1)
        except OSError:
            return ReadResult(number=number, state=STATE_INACCESSIBLE, path=str(p))

        # 2) The file opens. Ask the parser to read it.
        result = self.parser.parsePartMet(str(p))

        parsed_ok = result is not None and len(result.file_hash) == EXPECTED_HASH_LEN
        if not parsed_ok:
            # Parsing failed (or the hash is implausible). Before calling it
            # DAMAGED, check the mtime guard: a file written moments ago is
            # probably mid-write, so I report INACCESSIBLE instead.
            if self._recently_modified(p, mtime_guard_seconds):
                return ReadResult(number=number, state=STATE_INACCESSIBLE, path=str(p))
            return ReadResult(number=number, state=STATE_DAMAGED, path=str(p))

        # 3) Parsed fine: extract the three pieces of information I need.
        return ReadResult(
            number=number,
            state=STATE_OK,
            file_hash=result.file_hash.hex(),
            file_name=result.tags.get("filename"),
            gaps=result.gaps,
            path=str(p),
        )

    @staticmethod
    def _recently_modified(path, window_seconds: int) -> bool:
        """Return ``True`` if the file was modified within ``window_seconds``.

        Args:
            path: the file path.
            window_seconds (int): the guard window in seconds.

        Returns:
            bool: whether the last modification is more recent than the window.
        """
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            # If I cannot even read the mtime, I do not extend the benefit of
            # the doubt; the caller will handle the resulting classification.
            return False
        return (time.time() - mtime) < window_seconds
