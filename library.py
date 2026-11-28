"""Persistent, local-only SQLite transcript library.

The library stores transcript text and metadata, not original video/audio.
This is intentionally single-user: never expose the existing app publicly.
"""
from __future__ import annotations
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from source_highlights import validate_highlights

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
      highlights TEXT,
      processing_metadata TEXT NOT NULL DEFAULT '{}',
      created_at REAL NOT NULL,
      updated_at REAL NOT NULL
    )""")
    if "processing_metadata" not in {row[1] for row in connection.execute("PRAGMA table_info(transcripts)")}:
        try:
            connection.execute("ALTER TABLE transcripts ADD COLUMN processing_metadata TEXT NOT NULL DEFAULT '{}'")
        except sqlite3.OperationalError:
            # Another local connection may have completed this additive migration.
            if "processing_metadata" not in {row[1] for row in connection.execute("PRAGMA table_info(transcripts)")}:
                connection.close()
                raise
    if "highlights" not in {row[1] for row in connection.execute("PRAGMA table_info(transcripts)")}:
        try:
            connection.execute("ALTER TABLE transcripts ADD COLUMN highlights TEXT")
        except sqlite3.OperationalError:
            if "highlights" not in {row[1] for row in connection.execute("PRAGMA table_info(transcripts)")}:
                connection.close()
                raise
    connection.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_created ON transcripts(created_at DESC)")
    return connection


def _row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["segments"] = json.loads(data["segments"])
    data["translations"] = json.loads(data["translations"])
    data["summary"] = json.loads(data["summary"]) if data["summary"] else None
    data["processing_metadata"] = json.loads(data.get("processing_metadata") or "{}")
    try:
        data["highlights"] = json.loads(data["highlights"]) if data.get("highlights") else None
        if data["highlights"] is not None:
            validate_highlights(data["highlights"], data["segments"])
    except ValueError:
        data["highlights"] = None
        warning = "Saved source highlights were damaged or no longer matched the transcript. Create them again; the original transcript is retained."
        warnings = data["processing_metadata"].get("warnings", [])
        data["processing_metadata"]["warnings"] = (warnings if isinstance(warnings, list) else []) + [warning]
    return data


def _plain(segments: list[dict[str, Any]]) -> str:
    return "\n".join(str(s.get("text", "")).strip().replace("\n", " ") for s in segments)


def _processing_metadata_json(value: Any) -> str:
    """Bound configuration provenance; never accept audio, vectors or credentials."""
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("Processing metadata must be an object.")
    nodes = 0
    forbidden = {"audio", "embeddings", "embedding", "waveform", "voiceprint", "samples",
                 "token", "hf_token", "api_key", "authorization"}

    def visit(item, depth=0):
        nonlocal nodes
        nodes += 1
        if depth > 8 or nodes > 1024:
            raise ValueError("Processing metadata is too deeply nested or complex.")
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, (int, float)):
            try:
                if not math.isfinite(item):
                    raise ValueError("Processing metadata contains a non-finite number.")
            except OverflowError as exc:
                raise ValueError("Processing metadata contains an oversized number.") from exc
        elif isinstance(item, str):
            if len(item) > 4096:
                raise ValueError("Processing metadata contains an oversized string.")
            item.encode("utf-8")
        elif isinstance(item, dict):
            if len(item) > 64:
                raise ValueError("Processing metadata contains too many fields.")
            for key, entry in item.items():
                if not isinstance(key, str) or len(key) > 80 or key.lower() in forbidden:
                    raise ValueError("Processing metadata contains a prohibited field.")
                key.encode("utf-8")
                visit(entry, depth + 1)
        elif isinstance(item, list):
            if len(item) > 100:
                raise ValueError("Processing metadata contains an oversized list.")
            for entry in item:
                visit(entry, depth + 1)
        else:
            raise ValueError("Processing metadata contains an unsupported value.")

    try:
        visit(value)
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 32768:
            raise ValueError("Processing metadata exceeds 32 KiB.")
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Processing metadata is not valid bounded Unicode JSON.") from exc
    return encoded


def save(identifier: str, source: str, title: str, language: str, method: str,
         segments: list[dict[str, Any]], translations: dict[str, Any] | None = None,
         summary: dict[str, Any] | None = None, processing_metadata: dict[str, Any] | None = None,
         highlights: dict[str, Any] | None = None) -> None:
    now = time.time()
    metadata_json = _processing_metadata_json(processing_metadata)
    if highlights is not None:
        validate_highlights(highlights, segments)
    with _connect() as connection:
        connection.execute("""INSERT INTO transcripts
          (id,source,title,language,method,segments,plain_text,translations,summary,processing_metadata,highlights,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (identifier, source, title, language, method,
           json.dumps(segments, ensure_ascii=False), _plain(segments),
           json.dumps(translations or {}, ensure_ascii=False),
           json.dumps(summary, ensure_ascii=False) if summary else None, metadata_json,
           json.dumps(highlights, ensure_ascii=False, allow_nan=False) if highlights is not None else None, now, now))


def set_highlights(identifier: str, highlights: dict[str, Any]) -> bool:
    """Bind derived excerpts to the current source atomically, preserving edits."""
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT segments FROM transcripts WHERE id=?", (identifier,)).fetchone()
        if row is None:
            return False
        validate_highlights(highlights, json.loads(row["segments"]))
        connection.execute("UPDATE transcripts SET highlights=?, updated_at=? WHERE id=?",
                           (json.dumps(highlights, ensure_ascii=False, allow_nan=False), time.time(), identifier))
    return True


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
        existing = connection.execute("SELECT processing_metadata FROM transcripts WHERE id=?", (identifier,)).fetchone()
        if existing is None:
            return False
        metadata = json.loads(existing["processing_metadata"] or "{}")
        metadata.pop("translation", None)
        metadata.pop("summary", None)
        metadata["user_edited"] = True
        now = time.time()
        cursor = connection.execute("""UPDATE transcripts SET title=?, segments=?, plain_text=?,
            translations='{}', summary=NULL, highlights=NULL, processing_metadata=?, updated_at=? WHERE id=?""",
            (title, json.dumps(segments,ensure_ascii=False), _plain(segments),
             _processing_metadata_json(metadata), now, identifier))
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='batch_queue_items'").fetchone():
            connection.execute("UPDATE batch_queue_items SET title=?,updated_at=? WHERE library_id=? OR job_id=?",
                               (title, now, identifier, identifier))
        return cursor.rowcount > 0


def delete(identifier: str) -> bool:
    with _connect() as connection:
        result = connection.execute("DELETE FROM transcripts WHERE id=?", (identifier,))
        return result.rowcount > 0
