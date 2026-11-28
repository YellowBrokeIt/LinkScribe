# Bounded-memory library backup creation — 2026-11-28

Parent: `f17507b15eea180fc0ef9f93dda5fba0a380a5c1`. Its PR test run [46134310959](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46134310959) reports completed/success. This does not verify the new backup implementation.

## Change

Previously browser backup decoded every saved row into a single Python list, then serialized the whole library into another large object before applying the 100 MiB JSON ceiling. The new writer emits one decoded row at a time into the compressed ZIP member, updates SHA-256 incrementally, and enforces the existing JSON byte ceiling during emission. The same SQLite read transaction keeps a consistent snapshot. It also applies the restore-side 200,000-record ceiling to backup generation, preventing production of a backup the app would refuse to restore. The compressed archive is still held in memory and subject to the unchanged 50 MiB limit. A single very large row still requires its own decoding/encoding allocations.

Version 2, both member names, exact JSON encoding, deterministic record order, checksum, optional content and restore semantics are unchanged. The ZIP member order becomes transcripts then manifest; the reader validates their names, not their order. No schema changes or changes to the acceptance criteria.

## Actual local probe

Direct local git access failed DNS resolution. The candidate function was transferred from the local tested block and checked by FNV-1a fingerprint `4d0bfd7e`. The scoped Python probe exercised the previous and new writer with actual SQLite WAL databases, equivalent row decoding for records with null highlights, actual compression and hashing. It checked identical member bytes for empty, single, multiple and larger libraries, exact JSON-byte boundary acceptance and rejection, record-count boundary, and a second connection editing a later record during the first row read (the backup retained the original consistent snapshot). The probe does not exercise the full app, actual highlight validator or restore implementation. Added maintained tests use the production library and restore, with bilingual speaker metadata, warnings, summaries, empty/nonempty backups and concurrent edits; hosted verification is required.

Synthetic 600-record bilingual library: 31,703,153 uncompressed JSON bytes, 216,839 compressed archive bytes (highly repetitive text). Three uninstrumented elapsed samples per mode, separate tracemalloc peak sample.

| Writer | Median elapsed | Peak traced Python allocations |
| --- | ---: | ---: |
| Previous | 0.295 s | 160.85 MiB |
| Candidate | 0.294 s | 0.78 MiB |

Both ZIP members were byte-identical. These are scoped allocation measurements, not process RSS, native SQLite/compression allocations, real inference or worst-case archive size. Restore memory is unchanged. All language, source, long-recording and other open release gates remain open. Version remains 0.3.0.
