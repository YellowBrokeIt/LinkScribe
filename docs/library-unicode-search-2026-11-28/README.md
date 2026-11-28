# Greek/Unicode library search correction — 2026-11-28

Parent: 11e336577c7980f8da9dd817f265472596347a48. The production library previously used SQLite LIKE,
which does not perform Greek caseless matching. A Greek title or transcript
could appear missing when the user typed uppercase/lowercase or a canonically
equivalent accent representation. The correction uses a connection-local
deterministic Unicode search key and bound literal substring queries. It does
not strip accents, modify stored text, migrate search data, add dependencies,
change result ordering, or change the limit. Greek final sigma is casefolded.

## Local regression verification

Direct container GitHub clone failed with DNS resolution error, so the local
test module contained the exact fetched _connect and list_items functions
plus standard imports and a temporary DB_FILE; no ASR or source_highlights
module was needed. The candidate replaced only the search function and added
the unicodedata import. Existing additive schema migrations ran on the
legacy SQLite fixture. Function and test transfer fingerprints (FNV-1a over
Unicode code units) matched: _connect c3adb1ad, original search 83c2ba82,
candidate search 71ae044f, test file 705357d3, with two trailing newlines in
the source function blocks. The candidate test file SHA-256 locally was
066adf3b68972a94869ae52f7d2a41a767cd3eabd9191adc6c7cd3ab33883dbb.

Command: python -m pytest -q
- Original: 5 failed, 7 passed in 0.21s (Greek case, final sigma, composed
  versus decomposed accents, limited result).
- Candidate: 12 passed in 0.20s. Includes literal percent, underscore,
  backslash, SQL-looking input, English case, ordering, limits, empty search,
  missing result and exact retained original title/preview.
- This was an isolated actual SQLite function test, NOT a full checkout or
  browser/model rerun. New maintained tests exercise the full module in CI.

## Prior exact-head hosted status

At parent 11e3365, GitHub reports success for the corrected original two-reader
speaker pipeline (run 46126494171), including preflight, model preparation,
bounded worker and evidence upload. The previous f2 run remains a historical
failure. This is a limited fixture pass; no wider Greek/noisy speaker accuracy
claim is made, and raw new acoustic numbers are not inferred from job status.
The parent also completed candidate ZIP installation (46126494141), real
browser (46126494146), independent integration (46126494148) and platform
tests (46126498562 and 46126494119). These are parent results, not verification
of the search patch.

## Next work / open gates

The new search implementation scans matching rows like the previous LIKE
query; Unicode conversion can add overhead for long collections, and
accent-omitting searches are still accent-sensitive. No benchmark on a large
real library is claimed. No full-source hosted run was manually requested
again. Continue with exact new-head CI results, raw speaker artifact review,
the retained five-header grammar continuation, meaningful bilingual outputs,
provider access and whole-machine resource gates. Keep version 0.3.0 and
draft PR #2; no release gate is relaxed.
