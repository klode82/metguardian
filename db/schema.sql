-- MetGuardian - Database schema
-- ---------------------------------------------------------------------------
-- This script is executed on every startup via executescript(). Every
-- statement is idempotent (IF NOT EXISTS / INSERT OR IGNORE), so running it
-- repeatedly is safe and never destroys existing data.
--
-- All timestamps are stored as TEXT in UTC, using datetime('now').
-- ---------------------------------------------------------------------------

-- Currently monitored downloads.
-- One row per "slot" (the part.met number, e.g. "493"). The number is unique:
-- at any given time only one active file can occupy a given slot.
-- file_hash / file_name / backup_path are NULL when the file has never been read
-- successfully (e.g. it appeared already damaged or inaccessible).
CREATE TABLE IF NOT EXISTS active_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    number        TEXT    NOT NULL UNIQUE,          -- slot number from the file name (e.g. "493")
    file_hash     TEXT,                              -- hex global file hash (from PartMet.file_hash); NULL if not yet read
    file_name     TEXT,                              -- value of the "filename" tag
    state         TEXT    NOT NULL,                  -- OK | INACCESSIBLE | DAMAGED
    backup_path   TEXT,                              -- path of the backed-up .met (named by MD4)
    first_seen    TEXT    NOT NULL DEFAULT (datetime('now')),
    last_updated  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- History of downloads that are no longer active in the temp folder.
-- A row lands here when a slot is replaced by a different MD4 (REPLACED) or
-- when the file disappears, i.e. completed or deleted (REMOVED_OR_COMPLETED).
-- The physical backup file is intentionally kept on disk regardless.
CREATE TABLE IF NOT EXISTS archived_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    number        TEXT,
    file_hash     TEXT,
    file_name     TEXT,
    backup_path   TEXT,
    reason        TEXT    NOT NULL,                  -- REPLACED | REMOVED_OR_COMPLETED
    first_seen    TEXT,                              -- carried over from active_files
    archived_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- State-transition log. I write a row ONLY when a slot changes state, never on
-- repeated confirmations of the same state. previous_state is NULL the first
-- time a slot is seen.
CREATE TABLE IF NOT EXISTS event_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    number          TEXT,
    file_hash       TEXT,
    previous_state  TEXT,                            -- NULL on first appearance
    new_state       TEXT    NOT NULL,
    message         TEXT,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Key/value application settings.
CREATE TABLE IF NOT EXISTS config (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

-- Indexes for the most common lookups.
CREATE INDEX IF NOT EXISTS idx_active_number   ON active_files(number);
CREATE INDEX IF NOT EXISTS idx_log_timestamp   ON event_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_archive_file_hash ON archived_files(file_hash);

-- Default configuration. Inserted only if the key is missing, so user changes
-- are never overwritten on restart.
INSERT OR IGNORE INTO config(key, value) VALUES
    ('temp_folder',            ''),     -- eMule/aMule temp folder to scan (set by the user)
    ('backup_folder',          ''),     -- destination folder for the backups (set by the user)
    ('scan_interval_seconds',  '300'),  -- scan every 5 minutes
    ('mtime_guard_seconds',    '10'),   -- if a parse fails but the file changed within this window, treat as INACCESSIBLE
    ('theme',                  'light'); -- UI theme (persisted here, since Franken UI does not persist it)
