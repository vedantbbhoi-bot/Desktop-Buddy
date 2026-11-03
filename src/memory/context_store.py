"""src/memory/context_store.py — per-directory SQLite context (F-08).

Each working directory gets a namespace keyed by SHA-256 of its absolute path.
History is isolated across directories and survives restarts.
"""
from __future__ import annotations

import hashlib
import logging
import pathlib
import sqlite3
import uuid
from typing import Optional

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / "data" / "context.db"
SCHEMA_PATH = pathlib.Path(__file__).resolve().parent / "schema.sql"

# Max messages returned in get_history to keep LLM context short
DEFAULT_HISTORY_LIMIT = 20


def _dir_hash(directory: pathlib.Path) -> str:
    """Return a stable SHA-256 hex string for a normalised directory path."""
    norm = str(directory.resolve()).lower()  # case-insensitive on Windows
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class ContextStore:
    """Thread-safe per-directory conversation store backed by SQLite."""

    def __init__(self, db_path: pathlib.Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._apply_schema()
        log.info("ContextStore ready: %s", self.db_path)

    def _apply_schema(self) -> None:
        if SCHEMA_PATH.exists():
            sql = SCHEMA_PATH.read_text(encoding="utf-8")
            self._conn.executescript(sql)
            self._conn.commit()
        else:
            log.warning("schema.sql not found at %s", SCHEMA_PATH)

    def _get_or_create_dir(self, directory: pathlib.Path) -> int:
        """Return the directories.id for the given directory, creating if needed."""
        h = _dir_hash(directory)
        row = self._conn.execute(
            "SELECT id FROM directories WHERE dir_hash = ?", (h,)
        ).fetchone()
        if row:
            return row[0]
        cur = self._conn.execute(
            "INSERT INTO directories (dir_hash, dir_path) VALUES (?, ?)",
            (h, str(directory.resolve())),
        )
        self._conn.commit()
        log.debug("Registered directory: %s (hash=%s)", directory, h[:8])
        return cur.lastrowid  # type: ignore[return-value]

    # ── Messages ──────────────────────────────────────────────────────────────

    def add_message(
        self,
        directory: pathlib.Path,
        role: str,
        content: str,
        task_id: Optional[str] = None,
    ) -> int:
        """Insert a message row. Returns the new row id."""
        dir_id = self._get_or_create_dir(directory)
        cur = self._conn.execute(
            "INSERT INTO messages (dir_id, role, content, task_id) VALUES (?, ?, ?, ?)",
            (dir_id, role, content, task_id),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_history(
        self,
        directory: pathlib.Path,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[dict]:
        """Return the most recent `limit` messages as dicts (oldest first)."""
        h = _dir_hash(directory)
        rows = self._conn.execute(
            """
            SELECT m.role, m.content, m.created_at, m.task_id
            FROM messages m
            JOIN directories d ON d.id = m.dir_id
            WHERE d.dir_hash = ?
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (h, limit),
        ).fetchall()
        return [
            {"role": r[0], "content": r[1], "created_at": r[2], "task_id": r[3]}
            for r in reversed(rows)
        ]

    def clear_history(self, directory: pathlib.Path) -> None:
        """Delete all messages for a directory (for testing / reset)."""
        h = _dir_hash(directory)
        self._conn.execute(
            "DELETE FROM messages WHERE dir_id = (SELECT id FROM directories WHERE dir_hash=?)",
            (h,),
        )
        self._conn.commit()

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def create_task(
        self, directory: pathlib.Path, task_type: str, summary: Optional[str] = None
    ) -> str:
        """Create a task record, return its UUID."""
        dir_id = self._get_or_create_dir(directory)
        task_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO tasks (id, dir_id, task_type, summary) VALUES (?, ?, ?, ?)",
            (task_id, dir_id, task_type, summary),
        )
        self._conn.commit()
        return task_id

    def finish_task(self, task_id: str, status: str = "done") -> None:
        self._conn.execute(
            "UPDATE tasks SET status=?, finished_at=strftime('%Y-%m-%dT%H:%M:%S','now') WHERE id=?",
            (status, task_id),
        )
        self._conn.commit()

    def get_last_task(self, directory: pathlib.Path) -> Optional[dict]:
        """Return the most recent task for a directory, or None."""
        h = _dir_hash(directory)
        row = self._conn.execute(
            """
            SELECT t.id, t.task_type, t.summary, t.status, t.created_at
            FROM tasks t
            JOIN directories d ON d.id = t.dir_id
            WHERE d.dir_hash = ?
            ORDER BY t.created_at DESC
            LIMIT 1
            """,
            (h,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0], "task_type": row[1], "summary": row[2],
            "status": row[3], "created_at": row[4],
        }

    def close(self) -> None:
        self._conn.close()


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = ContextStore(pathlib.Path(tmp) / "test.db")
        d = pathlib.Path(tmp)

        store.add_message(d, "user", "Hello pet!")
        store.add_message(d, "assistant", "Hi there! Working in a temp dir.")
        hist = store.get_history(d)
        assert len(hist) == 2
        assert hist[0]["role"] == "user"
        print("History:", hist)

        # Directory isolation
        d2 = pathlib.Path(tmp) / "subdir"
        d2.mkdir()
        store.add_message(d2, "user", "Different directory message")
        assert len(store.get_history(d2)) == 1
        assert len(store.get_history(d)) == 2  # unchanged

        # Task tracking
        tid = store.create_task(d, "open_file", "Opened README.md")
        store.finish_task(tid, "done")
        last = store.get_last_task(d)
        assert last is not None
        assert last["status"] == "done"

        store.close()
        print("ContextStore smoke test PASSED")

