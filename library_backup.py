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
from typing import Any, BinaryIO

import library
from source_highlights import validate_highlights

FORMAT = "linkscr-transcript-library"
VERSION = 2
SUPPORTED_VERSIONS = {1, 2}
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_JSON_BYTES = 100 * 1024 * 1024
MAX_RECORDS = 200000
HEX_ID = re.compile(r"[a-f0-9]{32}\Z")


class BackupError(ValueError):
    """Validation error suitable for an HTTP 400 response."""


class BackupTooLarge(BackupError):
    """Compressed archive exceeds the supported upload size."""


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


def write_backup(stream: BinaryIO) -> int:
    """Write a snapshot to an empty seekable stream owned by the caller."""
    digest = hashlib.sha256()
    size = count = 0
    conn = library._connect()
    try:
        conn.execute("BEGIN")
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipout:
            with zipout.open("transcripts.json", "w") as member:
                def write(chunk: bytes) -> None:
                    nonlocal size
                    size += len(chunk)
                    if size > MAX_JSON_BYTES:
                        raise BackupError("Library is too large for a browser backup; use the local SQLite backup procedure.")
                    digest.update(chunk)
                    member.write(chunk)

                write(_encode({"format": FORMAT, "version": VERSION, "records": []})[:-2])
                for row in conn.execute("SELECT * FROM transcripts ORDER BY id"):
                    if count >= MAX_RECORDS:
                        raise BackupError("Library has too many records for a browser backup; use the local SQLite backup procedure.")
                    if count:
                        write(b",")
                    write(_encode(library._row(row)))
                    count += 1
                write(b"]}")
            meta = {"format": FORMAT, "version": VERSION, "records": count,
                    "sha256": digest.hexdigest()}
            zipout.writestr("manifest.json", _encode(meta))
        conn.rollback()
    finally:
        conn.close()
    if stream.tell() > MAX_ARCHIVE_BYTES:
        raise BackupError("Library backup exceeds the 50 MB restore limit; use the local SQLite backup procedure.")
    return count


def make_backup() -> tuple[bytes, int]:
    """Compatibility helper for callers explicitly requiring archive bytes."""
    with io.BytesIO() as stream:
        count = write_backup(stream)
        return stream.getvalue(), count


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
    highlights = record.get("highlights")
    if highlights is not None:
        try:
            validate_highlights(highlights, segments)
        except ValueError as exc:
            raise BackupError("Backup source highlights do not match their transcript.") from exc
    try:
        processing_metadata = library._processing_metadata_json(record.get("processing_metadata", {}))
    except ValueError as exc:
        raise BackupError(str(exc)) from exc
    created_at = record.get("created_at")
    updated_at = record.get("updated_at")
    if any(not _finite_number(v) or v < 0 for v in (created_at, updated_at)):
        raise BackupError("Backup contains an invalid timestamp.")
    return (identifier, source, title, language, method,
            _json_text(segments), library._plain(segments),
            _json_text(translations),
            _json_text(summary) if summary is not None else None,
            processing_metadata,
            _json_text(highlights) if highlights is not None else None,
            float(created_at), float(updated_at))


def restore_backup(archive_bytes: bytes) -> dict[str, int]:
    """Validate *all* rows before inserting. Skip existing IDs; never overwrite."""
    if not archive_bytes or len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise BackupError("Backup ZIP must be 50 MB or smaller.")
    return restore_backup_file(io.BytesIO(archive_bytes))


def restore_backup_file(archive_file: BinaryIO) -> dict[str, int]:
    """Restore a seekable binary archive without copying or closing the input."""
    try:
        size = archive_file.seek(0, io.SEEK_END)
        if size > MAX_ARCHIVE_BYTES:
            raise BackupTooLarge("Backup ZIP must be 50 MB or smaller.")
        if not size:
            raise BackupError("Backup ZIP must be 50 MB or smaller.")
        archive_file.seek(0)
        with zipfile.ZipFile(archive_file) as archive:
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
            type(manifest.get("version")) is not int or manifest["version"] not in SUPPORTED_VERSIONS or
            type(manifest.get("records")) is not int or
            hashlib.sha256(payload).hexdigest() != manifest.get("sha256")):
        raise BackupError("Backup format or checksum is invalid.")
    data = _load_json(payload)
    del payload
    if (not isinstance(data, dict) or data.get("format") != FORMAT or
            type(data.get("version")) is not int or data["version"] != manifest["version"] or
            not isinstance(data.get("records"), list) or
            len(data["records"]) != manifest.get("records")):
        raise BackupError("Backup manifest does not match its records.")
    if len(data["records"]) > MAX_RECORDS:
        raise BackupError("Backup contains too many records.")
    if data["version"] == 1 and any(isinstance(record, dict) and record.get("highlights") is not None
                                     for record in data["records"]):
        raise BackupError("Source highlights require a version 2 backup.")
    # Reuse the decoded list, releasing each JSON record as it becomes SQL
    # parameters. Keep every validation before opening the write transaction.
    parsed = data.pop("records")
    del data
    for index in range(len(parsed)):
        parsed[index] = _validated_record(parsed[index])
    ids = [row[0] for row in parsed]
    if len(set(ids)) != len(ids):
        raise BackupError("Backup contains duplicate transcript IDs.")
    conn = library._connect()
    try:
        with conn:
            before = conn.total_changes
            conn.executemany("""INSERT OR IGNORE INTO transcripts
              (id,source,title,language,method,segments,plain_text,translations,summary,processing_metadata,highlights,created_at,updated_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", parsed)
            inserted = conn.total_changes - before
    finally:
        conn.close()
    return {"total": len(parsed), "imported": inserted, "already_present": len(parsed) - inserted}
