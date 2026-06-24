"""Data-access layer (CRUD) for MetGuardian.

All SQL lives here, behind a small set of intention-revealing methods. The rest
of the application (scanner, state machine, UI bridge) talks to the database
only through :class:`Repository`, never with raw SQL of its own.

The state machine (built in a later step) orchestrates these methods; here I
only provide the building blocks.
"""

from .database import Database

__version__ = "1.0.0"

# --- File states -----------------------------------------------------------
# A slot (a part.met number) is always in exactly one of these states.
STATE_OK = "OK"                     # readable and valid; backed up and storicized
STATE_INACCESSIBLE = "INACCESSIBLE" # present but not readable right now (locked / being written)
STATE_DAMAGED = "DAMAGED"           # opens but cannot be parsed; NOT storicized, user is notified

# --- Archive reasons -------------------------------------------------------
REASON_REPLACED = "REPLACED"                       # same slot now holds a different MD4
REASON_REMOVED_OR_COMPLETED = "REMOVED_OR_COMPLETED"  # file gone from temp (deleted or finished)


class Repository:
    """High-level CRUD over the MetGuardian tables.

    Args:
        db (Database): the database access layer to run queries against.
    """

    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------ #
    # active_files
    # ------------------------------------------------------------------ #

    def get_active_by_number(self, number):
        """Return the active row for a slot number, or ``None`` if absent.

        Args:
            number (str): the slot number (e.g. ``"493"``).

        Returns:
            dict | None: the row as a dict, or ``None``.
        """
        with self.db.connect() as c:
            row = c.execute(
                "SELECT * FROM active_files WHERE number = ?", (number,)
            ).fetchone()
            return dict(row) if row else None

    def list_active(self):
        """Return all active files, ordered by slot number.

        Returns:
            list[dict]: one dict per active file.
        """
        with self.db.connect() as c:
            rows = c.execute(
                "SELECT * FROM active_files ORDER BY number"
            ).fetchall()
            return [dict(r) for r in rows]

    def upsert_active(self, number, md4, file_name, state, backup_path):
        """Insert a new active slot or update the existing one.

        Keyed on ``number``. On update I refresh md4, file name, state and
        backup path, and bump ``last_updated``. ``first_seen`` is preserved.

        Args:
            number (str): slot number.
            md4 (str | None): hex MD4 global hash, or ``None`` if unknown.
            file_name (str | None): the "filename" tag value, or ``None``.
            state (str): one of the ``STATE_*`` constants.
            backup_path (str | None): path of the stored .met, or ``None``.
        """
        with self.db.connect() as c:
            c.execute(
                """
                INSERT INTO active_files
                    (number, md4, file_name, state, backup_path, first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(number) DO UPDATE SET
                    md4          = excluded.md4,
                    file_name    = excluded.file_name,
                    state        = excluded.state,
                    backup_path  = excluded.backup_path,
                    last_updated = datetime('now')
                """,
                (number, md4, file_name, state, backup_path),
            )

    def set_active_state(self, number, state):
        """Update only the state of a slot (and its ``last_updated``).

        I use this when a file becomes inaccessible or damaged but I must NOT
        touch its md4 or backup (e.g. it was OK before and is now locked).

        Args:
            number (str): slot number.
            state (str): one of the ``STATE_*`` constants.
        """
        with self.db.connect() as c:
            c.execute(
                "UPDATE active_files SET state = ?, last_updated = datetime('now') WHERE number = ?",
                (state, number),
            )

    def delete_active(self, number):
        """Remove an active slot without archiving it.

        Args:
            number (str): slot number.
        """
        with self.db.connect() as c:
            c.execute("DELETE FROM active_files WHERE number = ?", (number,))

    # ------------------------------------------------------------------ #
    # archived_files
    # ------------------------------------------------------------------ #

    def archive_active(self, number, reason):
        """Move an active slot into the archive, then remove it from active.

        Both operations run in a single transaction so the row can never be
        lost or duplicated. The physical backup file is left untouched on disk.

        Args:
            number (str): slot number to archive.
            reason (str): ``REASON_REPLACED`` or ``REASON_REMOVED_OR_COMPLETED``.

        Returns:
            bool: ``True`` if a row was archived, ``False`` if the slot was
            not found among the active files.
        """
        with self.db.connect() as c:
            row = c.execute(
                "SELECT * FROM active_files WHERE number = ?", (number,)
            ).fetchone()
            if row is None:
                return False
            c.execute(
                """
                INSERT INTO archived_files
                    (number, md4, file_name, backup_path, reason, first_seen, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    row["number"],
                    row["md4"],
                    row["file_name"],
                    row["backup_path"],
                    reason,
                    row["first_seen"],
                ),
            )
            c.execute("DELETE FROM active_files WHERE number = ?", (number,))
            return True

    def list_archive(self):
        """Return all archived files, newest first.

        Returns:
            list[dict]: one dict per archived file.
        """
        with self.db.connect() as c:
            rows = c.execute(
                "SELECT * FROM archived_files ORDER BY archived_at DESC, id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # event_log
    # ------------------------------------------------------------------ #

    def add_log(self, number, md4, previous_state, new_state, message):
        """Append a state-transition entry to the log.

        I call this only when a slot actually changes state.

        Args:
            number (str): slot number.
            md4 (str | None): hex MD4, if known.
            previous_state (str | None): the prior state, or ``None`` if first seen.
            new_state (str): the new state.
            message (str): human-readable description of the transition.
        """
        with self.db.connect() as c:
            c.execute(
                """
                INSERT INTO event_log (number, md4, previous_state, new_state, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (number, md4, previous_state, new_state, message),
            )

    def list_log(self, limit=200):
        """Return the most recent log entries, newest first.

        Args:
            limit (int): maximum number of rows to return.

        Returns:
            list[dict]: one dict per log entry.
        """
        with self.db.connect() as c:
            rows = c.execute(
                "SELECT * FROM event_log ORDER BY timestamp DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # config
    # ------------------------------------------------------------------ #

    def get_config(self, key, default=None):
        """Return a single config value, or ``default`` if the key is missing.

        Args:
            key (str): config key.
            default: value to return when the key does not exist.

        Returns:
            str | Any: the stored string value, or ``default``.
        """
        with self.db.connect() as c:
            row = c.execute(
                "SELECT value FROM config WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_config(self, key, value):
        """Insert or update a config value (stored as text).

        Args:
            key (str): config key.
            value: value to store; it is converted to ``str``.
        """
        with self.db.connect() as c:
            c.execute(
                """
                INSERT INTO config(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )

    def all_config(self):
        """Return the whole configuration as a dict.

        Returns:
            dict: ``{key: value}`` for every config row.
        """
        with self.db.connect() as c:
            rows = c.execute("SELECT key, value FROM config").fetchall()
            return {r["key"]: r["value"] for r in rows}
