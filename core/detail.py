"""Detail builder for .part.met files.

Sits above PartMetParser: takes a raw PartMet result and turns it into a
presentation-ready dictionary for the UI's Detail modal.

The caller (bridge) picks the best available source (live temp file or last
valid backup) and passes it here. This module only knows how to interpret the
parsed data, not where the file lives.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from core.parser import PartMetParser

__version__ = "1.0.0"

logger = logging.getLogger("metguardian.detail")

# Tags that are exposed as top-level fields and should not appear again in the
# "extra tags" section of the detail dict.
_SUPPRESS_FROM_EXTRA = frozenset({
    "filename", "partfilename", "filesize", "filesize_hi",
    "gap_start", "gap_end",
})


def _fmt_bytes(n: int) -> str:
    if n is None or n < 0:
        return "—"
    for unit, divisor in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= divisor:
            return f"{n / divisor:.2f} {unit}"
    return f"{n} B"


def _fmt_ts(ts) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (OSError, OverflowError, ValueError, TypeError):
        return str(ts)


class DetailReader:
    """Parses a .part.met file and returns a presentation-ready dict."""

    def get_detail(
        self,
        number: str,
        temp_folder: str,
        active_record: dict | None,
        backup_path: str | None = None,
    ) -> dict | None:
        """Build the detail dict for a given slot.

        Tries sources in order:
        1. ``temp_folder / number.part.met`` (live file)
        2. ``active_record["backup_path"]`` or the explicit ``backup_path``

        Args:
            number:        slot number string (e.g. ``"001"``).
            temp_folder:   path to the eMule temp folder.
            active_record: active file record from the DB, or ``None``.
            backup_path:   explicit backup path override (used for archive rows).

        Returns:
            dict if parsing succeeded, ``None`` otherwise.
        """
        parser = PartMetParser()

        effective_backup = backup_path
        if not effective_backup and active_record:
            effective_backup = active_record.get("backup_path")

        result = None
        source = None
        source_path = None

        # 1. Live temp file.
        if temp_folder and number:
            temp_path = Path(temp_folder) / f"{number}.part.met"
            if temp_path.is_file():
                result = parser.parsePartMet(str(temp_path))
                if result is not None:
                    source = "temp"
                    source_path = str(temp_path)

        # 2. Backup fallback.
        if result is None and effective_backup:
            bp = Path(effective_backup)
            if bp.is_file():
                result = parser.parsePartMet(str(bp))
                if result is not None:
                    source = "backup"
                    source_path = str(bp)

        if result is None:
            return None

        return self._build(result, source, source_path)

    # ---------------------------------------------------------------------- #

    def _build(self, pm, source: str, source_path: str) -> dict:
        # File size: low 32 bits from "filesize", high 32 bits from "filesize_hi".
        try:
            lo = int(pm.tags.get("filesize") or 0)
            hi = int(pm.tags.get("filesize_hi") or 0)
        except (TypeError, ValueError):
            lo = hi = 0
        filesize = (hi << 32) | lo

        # Gaps and progress.
        gaps = []
        missing = 0
        for start, end in pm.gaps:
            try:
                s, e = int(start), int(end)
            except (TypeError, ValueError):
                continue
            size = e - s
            gaps.append({"start": s, "end": e, "size": size})
            missing += size

        downloaded = max(0, filesize - missing) if filesize > 0 else 0
        percent = round(downloaded / filesize * 100, 1) if filesize > 0 else 0.0

        # Part hashes as hex strings.
        parts_hash = [
            h.hex() if isinstance(h, bytes) else str(h)
            for h in (pm.parts_hash or [])
        ]

        # Extra tags: everything not already promoted to a top-level field.
        extra_tags = {}
        for k, v in pm.tags.items():
            if k in _SUPPRESS_FROM_EXTRA:
                continue
            if isinstance(v, bytes):
                extra_tags[k] = v.hex()
            elif isinstance(v, float):
                extra_tags[k] = round(v, 4)
            else:
                extra_tags[k] = v

        file_hash = pm.file_hash.hex() if isinstance(pm.file_hash, bytes) else (pm.file_hash or "")

        return {
            "source":         source,
            "source_path":    source_path,
            "version":        f"0x{pm.version:02X}",
            "file_hash":      file_hash,
            "filename":       pm.tags.get("filename") or "",
            "partfilename":   pm.tags.get("partfilename") or "",
            "filesize":       filesize,
            "filesize_str":   _fmt_bytes(filesize) if filesize > 0 else "—",
            "date":           _fmt_ts(pm.date),
            "num_parts":      len(pm.parts_hash) if pm.parts_hash else 0,
            "parts_hash":     parts_hash,
            "gaps":           gaps,
            "gap_count":      len(gaps),
            "downloaded":     downloaded,
            "downloaded_str": _fmt_bytes(downloaded) if filesize > 0 else "—",
            "missing":        missing,
            "missing_str":    _fmt_bytes(missing) if missing > 0 else "—",
            "percent_done":   percent,
            "tags":           extra_tags,
        }
