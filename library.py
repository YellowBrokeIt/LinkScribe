"""Persistent, local-only SQLite transcript library.

The library stores transcript text and metadata, not original video/audio.
This is intentionally single-user: never expose the existing app publicly.
"""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_FILE = Path(__file__).resolve().parent / "data" / "library.sqlite3"


def _connect():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS transcripts (
      id TEXT PRIMARY KEY,
      source TEXT NOT NULL,
      title TEXT NOT NULL,
      language TEXT NOT NULL,
      method TEXT NOT NULL,
      segments TEXT NOT NULL,
      plain_text TEXT NOT NULL,
      translations TEXT NOT NULL DEFAULT '{}',
      summary TEXT,
      created_at REAL NOT NULL,
      updated_at REAL NOT NULL
    )""")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_created ON transcripts(created_at DESC)")
    return connection


def _row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["segments"] = json.loads(data["segments"])
    data["translations"] = json.loads(data["translations"])
    data["summary"] = json.loads(data["summary"]) if data["summary"] else None
    return data


def _plain(segments: list[dict[str, Any]]) -> str:
    return "\n".join(str(s.get("text", "")).strip().replace("\n", " ") for s in segments)


def save(identifier: str, source: str, title: str, language: str, method: str,
         segments: list[dict[str, Any]], translations: dict[str, Any] | None = None,
         summary: dict[str, Any] | None = None) -> None:
    now = time.time()
    with _connect() as connection:
        connection.execute("""INSERT INTO transcripts
          (id,source,title,language,method,segments,plain_text,translations,summary,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
          (identifier, source, title, language, method,
           json.dumps(segments, ensure_ascii=False), _plain(segments),
           json.dumps(translations or {}, ensure_ascii=False),
           json.dumps(summary, ensure_ascii=False) if summary else None, now, now))


def get(identifier: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM transcripts WHERE id=?", (identifier,)).fetchone()
    return _row(row) if row else None


def list_items(query: str = "", limit: int = 50) -> list[dict[str, Any]]:
    limit = min(max(int(limit), 1), 100)
    with _connect() as connection:
        if query:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            term = "%" + escaped + "%"
            rows = connection.execute("""SELECT id,source,title,language,method,substr(plain_text,1,180) preview,
                 created_at,updated_at FROM transcripts WHERE title LIKE ? ESCAPE '\\' OR
                 plain_text LIKE ? ESCAPE '\\' ORDER BY created_at DESC LIMIT ?""", (term,term,limit)).fetchall()
        else:
            rows = connection.execute("""SELECT id,source,title,language,method,substr(plain_text,1,180) preview,
                created_at,updated_at FROM transcripts ORDER BY created_at DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(row) for row in rows]


def update(identifier: str, title: str, segments: list[dict[str, Any]]) -> bool:
    # Caller validates IDs, segment count, timestamps, and text constraints.
    with _connect() as connection:
        cursor = connection.execute("""UPDATE transcripts SET title=?, segments=?, plain_text=?,
            translations='{}', summary=NULL, updated_at=? WHERE id=?""",
            (title, json.dumps(segments,ensure_ascii=False), _plain(segments), time.time(), identifier))
        return cursor.rowcount > 0


def delete(identifier: str) -> bool:
    with _connect() as connection:
        result = connection.execute("DELETE FROM transcripts WHERE id=?", (identifier,))
        return result.rowcount > 0
