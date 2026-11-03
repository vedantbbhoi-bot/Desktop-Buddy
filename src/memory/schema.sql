-- src/memory/schema.sql — SQLite schema for per-directory conversation context (F-08)

CREATE TABLE IF NOT EXISTS directories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dir_hash    TEXT    NOT NULL UNIQUE,   -- SHA256 hex of the absolute normalised path
    dir_path    TEXT    NOT NULL,          -- human-readable path (informational)
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dir_id      INTEGER NOT NULL REFERENCES directories(id) ON DELETE CASCADE,
    role        TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT    NOT NULL,
    task_id     TEXT,                      -- optional: links message to a tool task
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_dir_id ON messages(dir_id);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT    PRIMARY KEY,       -- uuid4
    dir_id      INTEGER NOT NULL REFERENCES directories(id) ON DELETE CASCADE,
    task_type   TEXT    NOT NULL,          -- e.g. "open_file", "code_check", "small_talk"
    summary     TEXT,
    status      TEXT    NOT NULL DEFAULT 'pending',  -- pending | done | failed
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    finished_at TEXT
);

