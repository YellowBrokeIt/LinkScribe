"""Versioned, validated, non-destructive transcript backup/restore.

Backups contain JSON only (no executable database, media or credentials). They
can be restored into an existing local library without overwriting edits.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zipfile
from typing import Any

import library

FORMAT = "linkscr-transcript-library"
VERSION = 1
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_JSON_BYTES = 100 * 1024 * 1024
HEX_ID = re.compile(r"[a-f0-9]{32}\Z")


class BackupError(ValueError):
    """Validation error suitable for an HTTP 400 response."""


def _encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def make_backup() -> tuple[bytes, int]:
    """Snapshot all transcript rows in one SQLite read transaction."""
    conn = library._connect()
    try:
        conn.execute("BEGIN")
        records = [library._row(row) for row in conn.execute("SELECT * FROM transcripts ORDER BY id")]
        conn.rollback()
    finally:
        conn.close()
    contents = _encode({"format": FORMAT, "version": VERSION, "records": records})
    if len(contents) > MAX_JSON_BYTES:
        raise BackupError("Library is too large for a browser backup; use the local SQLite backup procedure.")
    meta = {"format": FORMAT, "version": VERSION, "records": len(records),
            "sha256": hashlib.sha256(contents).hexdigest()}
    buff = io.BytesIO()
    with zipfile.ZipFile(buff, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipout:
        zipout.writestr("manifest.json", _encode(meta))
        zipout.writestr("transcripts.json", contents)
    return buff.getvalue(), len(records)


def _validated_record(record: Any) -> tuple:
    if not isinstance(record, dict):
        raise BackupError("Backup record is not an object.")
    identifier = record.get("id")
    if not isinstance(identifier, str) or not HEX_ID.fullmatch(identifier):
        raise BackupError("Backup contains an invalid transcript ID.")
    source = record.get("source")
    title = record.get("title")
    language = record.get("language")
    method = record.get("method")
    if (not isinstance(source, str) or len(source) > 4096 or
            not isinstance(title, str) or not 1 <= len(title) <= 500 or
            not isinstance(language, str) or len(language) > 32 or
            not isinstance(method, str) or len(method) > 100):
        raise BackupError("Backup record metadata is invalid.")
    segments = record.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= 30000:
        raise BackupError("Backup contains invalid transcript segments.")
    for segment in segments:
        if not isinstance(segment, dict):
            raise BackupError("Backup contains an invalid segment.")
        start, end, text = segment.get("start"), segment.get("end"), segment.get("text")
        if (isinstance(start, bool) or not isinstance(start, (int, float)) or
                isinstance(end, bool) or not isinstance(end, (int, float)) or
                not math.isfinite(start) or not math.isfinite(end) or
                start < 0 or end < start or end > 7 * 24 * 3600 or
                not isinstance(text, str) or len(text) > 25000):
            raise BackupError("Backup contains invalid segment timestamps or text.")
        if "speaker" in segment and (not isinstance(segment["speaker"], str) or len(segment["speaker"]) > 120):
            raise BackupError("Backup contains an invalid speaker label.")
    translations = record.get("translations", {})
    summary = record.get("summary")
    if not isinstance(translations, dict) or summary is not None and not isinstance(summary, dict):
        raise BackupError("Backup contains invalid enhancements.")
    for lang, items in translations.items():
        if not isinstance(lang, str) or len(lang) > 24 or not isinstance(items, list):
            raise BackupError("Backup contains invalid translations.")
    created_at = record.get("created_at")
    updated_at = record.get("updated_at")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
           for v in (created_at, updated_at)):
        raise BackupError("Backup contains an invalid timestamp.")
    return (identifier, source, title, language, method,
            json.dumps(segments, ensure_ascii=False), library._plain(segments),
            json.dumps(translations, ensure_ascii=False),
            json.dumps(summary, ensure_ascii=False) if summary is not None else None,
            created_at, updated_at)


def restore_backup(archive_bytes: bytes) -> dict[str, int]:
    """Validate *all* rows before inserting. Skip existing IDs; never overwrite."""
    if not archive_bytes or len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise BackupError("Backup ZIP must be 50 MB or smaller.")
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            files = archive.infolist()
            if (len(files) != 2 or {x.filename for x in files} != {"manifest.json", "transcripts.json"}
                    or any(x.is_dir() or x.flag_bits & 1 for x in files)):
                raise BackupError("Backup ZIP must contain only manifest.json and transcripts.json.")
            if next(x for x in files if x.filename == "manifest.json").file_size > 8192:
                raise BackupError("Backup manifest is too large.")
            if next(x for x in files if x.filename == "transcripts.json").file_size > MAX_JSON_BYTES:
                raise BackupError("Backup transcript data exceeds 100 MB.")
            manifest = json.loads(archive.read("manifest.json"))
            payload = archive.read("transcripts.json")
    except (zipfile.BadZipFile, EOFError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("Invalid or damaged LinkScribe backup ZIP.") from exc
    if (not isinstance(manifest, dict) or manifest.get("format") != FORMAT or
            manifest.get("version") != VERSION or
            hashlib.sha256(payload).hexdigest() != manifest.get("sha256")):
        raise BackupError("Backup format or checksum is invalid.")
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("Backup transcript JSON is invalid.") from exc
    if (not isinstance(data, dict) or data.get("format") != FORMAT or data.get("version") != VERSION or
            not isinstance(data.get("records"), list) or
            len(data["records"]) != manifest.get("records")):
        raise BackupError("Backup manifest does not match its records.")
    if len(data["records"]) > 200000:
        raise BackupError("Backup contains too many records.")
    parsed = [_validated_record(record) for record in data["records"]]
    ids = [row[0] for row in parsed]
    if len(set(ids)) != len(ids):
        raise BackupError("Backup contains duplicate transcript IDs.")
    conn = library._connect()
    try:
        with conn:
            before = conn.total_changes
            conn.executemany("""INSERT OR IGNORE INTO transcripts
              (id,source,title,language,method,segments,plain_text,translations,summary,created_at,updated_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?)""", parsed)
            inserted = conn.total_changes - before
    finally:
        conn.close()
    return {"total": len(parsed), "imported": inserted, "already_present": len(parsed) - inserted}
