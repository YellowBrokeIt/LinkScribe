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
import zlib
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


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _text(value: Any, limit: int) -> bool:
    if not isinstance(value, str) or len(value) > limit:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _load_json(payload: bytes) -> Any:
    def reject_constant(_value: str) -> Any:
        raise BackupError("Backup JSON contains a non-finite number.")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            reject_constant(value)
        return number

    try:
        # JSON's NaN/Infinity extensions and overflowing exponents can poison
        # later exports even when they occur in otherwise unused metadata.
        return json.loads(payload, parse_constant=reject_constant, parse_float=finite_float)
    except BackupError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise BackupError("Backup contains invalid JSON.") from exc


def _json_text(value: Any) -> str:
    try:
        return _encode(value).decode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise BackupError("Backup contains invalid JSON values.") from exc


def _validate_segments(segments: Any) -> None:
    if not isinstance(segments, list) or not 1 <= len(segments) <= 30000:
        raise BackupError("Backup contains invalid transcript segments.")
    for segment in segments:
        if not isinstance(segment, dict):
            raise BackupError("Backup contains an invalid segment.")
        start, end, text = segment.get("start"), segment.get("end"), segment.get("text")
        if (not _finite_number(start) or not _finite_number(end) or
                start < 0 or end < start or end > 7 * 24 * 3600 or not _text(text, 25000)):
            raise BackupError("Backup contains invalid segment timestamps or text.")
        if "speaker" in segment and not _text(segment["speaker"], 120):
            raise BackupError("Backup contains an invalid speaker label.")


def _validate_summary(summary: Any) -> None:
    if summary is None or summary == {}:
        return
    if (not isinstance(summary, dict) or not _text(summary.get("summary"), 12000) or
            not isinstance(summary.get("key_points"), list) or len(summary["key_points"]) > 30 or
            any(not _text(point, 900) for point in summary["key_points"]) or
            not isinstance(summary.get("chapters"), list) or len(summary["chapters"]) > 100):
        raise BackupError("Backup contains an invalid summary.")
    for chapter in summary["chapters"]:
        if (not isinstance(chapter, dict) or not _finite_number(chapter.get("start")) or
                not 0 <= chapter["start"] <= 7 * 24 * 3600 or not _text(chapter.get("title"), 120)):
            raise BackupError("Backup contains an invalid summary chapter.")


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
    archive_bytes = buff.getvalue()
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise BackupError("Library backup exceeds the 50 MB restore limit; use the local SQLite backup procedure.")
    return archive_bytes, len(records)


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
    if (not _text(source, 4096) or not _text(title, 500) or not title or
            not _text(language, 32) or not _text(method, 100)):
        raise BackupError("Backup record metadata is invalid.")
    segments = record.get("segments")
    _validate_segments(segments)
    translations = record.get("translations", {})
    summary = record.get("summary")
    if not isinstance(translations, dict):
        raise BackupError("Backup contains invalid enhancements.")
    for lang, items in translations.items():
        if lang not in {"en", "el"}:
            raise BackupError("Backup contains invalid translations.")
        _validate_segments(items)
    _validate_summary(summary)
    created_at = record.get("created_at")
    updated_at = record.get("updated_at")
    if any(not _finite_number(v) or v < 0 for v in (created_at, updated_at)):
        raise BackupError("Backup contains an invalid timestamp.")
    return (identifier, source, title, language, method,
            _json_text(segments), library._plain(segments),
            _json_text(translations),
            _json_text(summary) if summary is not None else None,
            float(created_at), float(updated_at))


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
            manifest = _load_json(archive.read("manifest.json"))
            payload = archive.read("transcripts.json")
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError, NotImplementedError, zlib.error) as exc:
        raise BackupError("Invalid or damaged LinkScribe backup ZIP.") from exc
    if (not isinstance(manifest, dict) or manifest.get("format") != FORMAT or
            type(manifest.get("version")) is not int or manifest["version"] != VERSION or
            type(manifest.get("records")) is not int or
            hashlib.sha256(payload).hexdigest() != manifest.get("sha256")):
        raise BackupError("Backup format or checksum is invalid.")
    data = _load_json(payload)
    if (not isinstance(data, dict) or data.get("format") != FORMAT or
            type(data.get("version")) is not int or data["version"] != VERSION or
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
