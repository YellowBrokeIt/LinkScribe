# LinkScribe v0.3 recovery checkpoint — 2026-11-11

## Provenance

Work resumed from verified GitHub commit `cbda9ed173d88f3893604cd2ec63e3f5a1fae84e` on `feature/linkscribe-v03-reliability`, draft PR #2. The earlier chat-only reports of 189 and 253 tests were not recoverable as published code and are not evidence for this candidate. Stable `master` remains outside this work.

The candidate-artifacts workflow now publishes an exact tracked-source ZIP and a manifest containing its commit and SHA-256. These are unreleased source snapshots, not installers or release approvals. Download a snapshot from the Actions run for the desired commit; consult that same commit's test and Independent LinkScribe QA results.

## This checkpoint

- Translation batching measures the serialized JSON input in UTF-8 bytes, including escaping and entry IDs, rather than raw text character count.
- Oversized individual segments are divided into bounded internal fragments, preferring word boundaries. Translated fragments are reassembled into the original segment; segment count, timestamps, speakers and other metadata are preserved. No subtitle timing is invented.
- Original source dictionaries are not changed, including after a later request fails. Entire input validation happens before the first model call.
- Blank segments do not invoke the model or fabricate content.
- Invalid Unicode and oversized translated fragments fail explicitly. Model JSON rejects duplicate keys, non-standard numeric constants and non-object roots. Explicitly incomplete responses are not accepted as successful results.
- 76 new deterministic regression cases cover Greek, English, emoji, combining characters, JSON escaping, metadata preservation, malformed output and failure paths. Their model responses are synthetic; these are structural tests, not semantic translation-quality approval.

## Local verification

Python 3.13.5: `python -m pytest -q --ignore=tests/test_provider_runtime.py` passed **214 tests**. The four provider-runtime tests were deliberately excluded because this environment lacks yt-dlp; the normal hosted workflows run the full suite with installed dependencies. Compilation and Linux shell syntax checks also passed.

A baseline reproduction sent a 16,023-byte serialized input for one long Greek segment despite the old nominal 2,800-character batching limit. The new regression tests enforce the actual per-request payload bound.

## Limits retained

English–Greek semantic quality remains experimental. Smaller fragments can lose surrounding linguistic context; structural success is not proof that terminology, names or meaning were translated correctly. Existing real Ollama smoke tests check integration and preservation, not independent linguistic approval. This checkpoint does not alter the summarization chunking policy, gated pyannote setup, provider access restrictions, downloader runtime security floors, or localhost-only deployment scope.

Next release gates are current-head hosted validation and a reproducible semantic-quality evaluation before approving translation for release. Keep the PR draft until those results are reviewed.
