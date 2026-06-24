"""SQLite database access layer for MetGuardian.

This module owns the low-level database concerns: where the database file
lives, how connections are opened, and how the schema is initialized.

Design notes
------------
* I open a fresh connection per unit of work through the :meth:`Database.connect`
  context manager. This keeps things thread-safe: the scanner runs on a
  background thread while the UI bridge reads on the main thread, and a
  short-lived connection used within a single call never crosses threads.
* The database runs in WAL (Write-Ahead Logging) mode, which lets a reader and
  a writer work at the same time without blocking each other. WAL is a
  persistent property of the database file, so I set it once at init.
* All higher-level CRUD lives in ``repository.py``; this file deliberately
  contains no business logic.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

__version__ = "1.0.0"

# The schema lives next to this file.
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Default database location: <project_root>/data/metguardian.db
# (db/ is one level below the project root, hence parents[1]).
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "metguardian.db"


class Database:
    """Manages the SQLite database file and hands out connections.

    Args:
        db_path: optional path to the database file. If omitted, I use
            :data:`DEFAULT_DB_PATH`. The parent folder is created if needed.
    """

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        # Make sure the containing folder (e.g. data/) exists.
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Apply WAL and create the schema on first use.
        self._initialize()

    @contextmanager
    def connect(self):
        """Yield a configured connection inside a transaction.

        On a clean exit I commit; on any exception I roll back and re-raise.
        The connection is always closed afterwards.

        Yields:
            sqlite3.Connection: a connection whose rows behave like dicts
            (``row["column"]``) and with foreign keys enabled.
        """
        # timeout lets a writer wait instead of failing immediately if the
        # database is briefly locked by another connection.
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self):
        """Enable WAL and create the schema if it is not there yet.

        I run the PRAGMA and the schema script on a plain connection (outside
        the commit/rollback wrapper) because ``PRAGMA journal_mode`` must run
        on its own and is auto-persisted to the database file.
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            conn.executescript(schema_sql)
            conn.commit()
        finally:
            conn.close()
