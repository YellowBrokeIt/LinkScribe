"""Crash-recoverable local batch journal.

Only public, canonical video URLs and validated transcription settings are stored.
The journal lives in the same SQLite database as the transcript library.
Browser backups export transcripts only, not batch work. No media is stored here.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
import time
from typing import Any, Iterator

import library

REMOVED_ERROR = "Transcript was removed from the library after processing."


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    conn = library._connect()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""CREATE TABLE IF NOT EXISTS batch_queue (
            id TEXT PRIMARY KEY,
            options TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS batch_queue_items (
            batch_id TEXT NOT NULL REFERENCES batch_queue(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            job_id TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            error TEXT NOT NULL DEFAULT '',
            library_id TEXT NOT NULL DEFAULT '',
            updated_at REAL NOT NULL,
            PRIMARY KEY(batch_id, position)
        )""")
        with conn:
            yield conn
    finally:
        conn.close()


def create(batch_id: str, items: list[dict[str, str]], options: dict[str, Any]) -> None:
    """Commit all job metadata atomically, before putting work in the thread pool."""
    now = time.time()
    with _db() as conn:
        conn.execute("INSERT INTO batch_queue(id,options,status,created_at,updated_at) VALUES (?,?,?,?,?)",
                     (batch_id, json.dumps(options, separators=(",", ":")), "queued", now, now))
        conn.executemany("""INSERT INTO batch_queue_items
            (batch_id,position,job_id,source,title,status,error,library_id,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", [
            (batch_id, index, item["id"], item["source"], item["title"], "queued", "", "", now)
            for index, item in enumerate(items)
        ])


def mark_batch(batch_id: str, status: str) -> None:
    assert status in {"queued", "working", "done", "error"}
    with _db() as conn:
        cursor = conn.execute("UPDATE batch_queue SET status=?,updated_at=? WHERE id=?",
                              (status, time.time(), batch_id))
        if cursor.rowcount != 1:
            raise KeyError(f"Missing batch: {batch_id}")


def claim_item(job_id: str) -> dict[str, Any] | None:
    """Start a pending item, or return its terminal journal state unchanged."""
    with _db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT status,error FROM batch_queue_items WHERE job_id=?",
                           (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"Missing batch job: {job_id}")
        if row["status"] in {"done", "error"}:
            return dict(row)
        conn.execute("UPDATE batch_queue_items SET status='working',error='',library_id='',updated_at=? WHERE job_id=?",
                     (time.time(), job_id))
        return None


def mark_item(job_id: str, status: str, title: str = "", error: str = "", library_id: str = "") -> str:
    assert status in {"queued", "working", "done", "error"}
    with _db() as conn:
        # Serialize the saved-record check with edits and deletion. A late
        # worker must not acknowledge a transcript that no longer exists.
        conn.execute("BEGIN IMMEDIATE")
        if status == "done":
            saved = conn.execute("SELECT title FROM transcripts WHERE id=?", (library_id,)).fetchone()
            if saved is not None:
                title = saved["title"]  # Preserve an edit made just after transcript commit.
            else:
                status, error, library_id = "error", REMOVED_ERROR, ""
                title = ""  # Preserve the latest journal title.
        if status == "error":
            previous = conn.execute("SELECT error FROM batch_queue_items WHERE job_id=?", (job_id,)).fetchone()
            if previous is not None and previous["error"] == REMOVED_ERROR:
                error, library_id, title = REMOVED_ERROR, "", ""
        cursor = conn.execute("""UPDATE batch_queue_items
            SET status=?,title=CASE WHEN ?!='' THEN ? ELSE title END,
                error=?,library_id=?,updated_at=? WHERE job_id=?""",
                (status, title, title, error, library_id, time.time(), job_id))
        if cursor.rowcount != 1:
            raise KeyError(f"Missing batch job: {job_id}")
        return status


def delete_library_record(identifier: str) -> bool:
    """Delete a transcript and record its removal in the same transaction.

    The journal may still say 'working' if deletion happens just after the
    transcript is saved. A durable terminal status closes that recovery gap.
    """
    with _db() as conn:
        deleted = conn.execute("DELETE FROM transcripts WHERE id=?", (identifier,))
        if not deleted.rowcount:
            return False
        conn.execute("""UPDATE batch_queue_items SET status='error', error=?,
                     library_id='', updated_at=? WHERE job_id=?""",
                     (REMOVED_ERROR,
                      time.time(), identifier))
        return True


def get(batch_id: str) -> dict[str, Any] | None:
    with _db() as conn:
        batch = conn.execute("SELECT * FROM batch_queue WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            return None
        children = conn.execute("""SELECT job_id id, position, source, title, status,
                         error, library_id FROM batch_queue_items
                         WHERE batch_id=? ORDER BY position""", (batch_id,)).fetchall()
    return {**dict(batch), "options": json.loads(batch["options"]),
            "jobs": [dict(row) for row in children]}


def unfinished() -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.execute("""SELECT id FROM batch_queue WHERE status IN ('queued','working')
                                 ORDER BY created_at""").fetchall()
    return [stored for row in rows if (stored := get(row["id"])) is not None]


def recent(limit: int = 50) -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.execute("""SELECT id FROM batch_queue ORDER BY created_at DESC
                               LIMIT ?""", (min(max(limit, 1), 100),)).fetchall()
    return [stored for row in rows if (stored := get(row["id"])) is not None]
