"""Crash-recoverable local batch journal.

Only public, canonical video URLs and validated transcription settings are stored.
The journal lives in the same SQLite database as the transcript library, making
backup/restore cover both. No original media is persisted here.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
import time
from typing import Any, Iterator

import library


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


def mark_item(job_id: str, status: str, title: str = "", error: str = "", library_id: str = "") -> None:
    assert status in {"queued", "working", "done", "error"}
    with _db() as conn:
        cursor = conn.execute("""UPDATE batch_queue_items
            SET status=?,title=CASE WHEN ?!='' THEN ? ELSE title END,
                error=?,library_id=?,updated_at=? WHERE job_id=?""",
                (status, title, title, error, library_id, time.time(), job_id))
        if cursor.rowcount != 1:
            raise KeyError(f"Missing batch job: {job_id}")


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
