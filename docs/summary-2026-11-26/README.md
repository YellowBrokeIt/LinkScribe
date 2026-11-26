# Actual local summary and chapter QA — 26 November 2026

This evaluation uses six internally authored fictional English and Greek transcripts. The complete source transcripts and review criteria were frozen before any summary-model output was inspected. They are development diagnostics, not an external benchmark or human quality certification.

## Frozen corpus

`tests/fixtures/summary_quality_cases.json`

SHA-256: `0b241fc12d8a86e4fab50ecb8a3371588c6e8bc67754c782fcc5ef996001c830`

| Case | Language | Source design |
| --- | --- | --- |
| Consent and roles | English | Twelve interviews, limited quotation permission, owner/operator distinctions, approved amount and pending booking. |
| Workshop counts | Greek | Six inspected bicycles, four ready and two awaiting parts, unaccepted estimate and conditional release. |
| Quoted command | English | Misleading training instruction, seven confirmed bookings and two pending requests. |
| Quotation and correction | Greek | Criticized cancellation instruction, two confirmed meetings and one pending, corrected room. |
| Board-game day | English | Twenty paragraphs; a late venue, date and capacity decision supersedes the opening proposal. |
| Photo archive | Greek | Twenty paragraphs; late consent counts and a replacement date supersede an initial publication proposal. |

The long English source contains 7,941 characters and the long Greek source 8,496. Under the baseline production 6,500-character grouping rule, both require two excerpt summaries followed by synthesis. The decisive final facts occur in the later excerpt. Chapters are attached to the actual starting timestamp of each excerpt; the current implementation groups by length rather than detecting every topic boundary.

## Review method

The evaluator must call the actual application summary workflow with the selected local model and preserve the exact requests, responses, delivered summary, key points and chapter titles. Expected facts and prohibited distortions are review metadata; they must never be added to the model input beyond facts already present in the source transcript.

Assistant review examines the delivered summary and key points together, then checks each chapter title against its excerpt. Ordinary compression is allowed. Material changes to actors, quantities, consent, hypothetical events or completed-versus-pending actions are errors. A late corrected final decision must not be replaced with an earlier proposal. A quoted misleading instruction must remain described as content rather than become a factual claim or an operational command.

Source-language preference is assessed separately from factual fidelity because the production prompt at this freeze does not explicitly demand the source language. Internal map notes provide diagnostic evidence, but cannot substitute for information missing from delivered outputs.

## Baseline result

The actual Qwen3 4B baseline finished all six requested cases in 567.814 seconds. Five produced structurally valid summaries and chapters; the long Greek case timed out during its first map request. All six original transcripts, exports and SQLite records survived in-process eviction and fresh-interpreter retrieval. The failed summary was surfaced as a warning while keeping the source transcript usable.

| Assistant classification | Cases |
| --- | ---: |
| Acceptable | 1 |
| Minor issue | 2 |
| Major error | 2 |
| Not evaluable | 1 |

The two material defects occurred during final synthesis after substantially faithful map notes: the oral-history summary assigned operation of the recorder to Beatrice instead of Hana, and the bicycle key points corrupted the correct €39.60 total to `€3:60`. The English long result preserved the decisive late West Hall / 21 September / 28 visitors correction, but broadened a photo/inventory qualifier and omitted a consent constraint. Both completed Greek short cases produced English summaries; source-language preference is recorded separately from factual fidelity.

The timed-out Greek request contained 6,451 user-text characters but 11,716 UTF-8 bytes. The corresponding first English long request contained 6,466 characters and 6,476 bytes. This exposes the uneven workload admitted by the old character-based cap; it does not isolate input size as the sole cause of the timeout. No complete Greek-long response was available to judge. The 240-second timeout remains a required limit.

Exact baseline evidence: `qwen3-baseline.json`, SHA-256 `bf7442d9361c200a92056add63b6303a0437b8a9ba9bb1fb46456d7902cf7520`. It is an unchanged copy of the raw QA report and contains full owned inputs, actual requests/responses, outputs, source hashes and export checksums. SQLite databases and per-run export folders remain outside this documentation directory. Detailed source/output evidence and classifications are in `assistant-review.json`.

The selected model digest was `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, using Ollama 0.40.12, temperature 0, context 8192, output limit 2048 and four CPU threads. All captured source hashes and selected-model/runtime metadata stayed unchanged. Repository HEAD changed because an unrelated QA-only commit was published; this is an exact-source-hash evaluation, not a claim that every repository file stayed fixed.

The baseline is not approved for general summary quality. General corrections and separately frozen validation are pending: direct source-grounded output for one chunk, UTF-8-bounded source and note/reduction requests including oversized segments, and explicit output language based on the known source language. Existing failed outputs remain preserved.

## Scope and limits

The text fixtures bypass speech recognition and translation so that summary behavior can be assessed against an exact known source. The harness still uses the actual application enhancement/save path, local inference transport, SQLite library and download routes. A separate combined workflow evaluation is needed to measure how ASR or translation errors propagate into summaries.

The integration checks establish source coverage, structured output, timestamp provenance and persistence/export consistency. They cannot establish that a summary is true merely because it is valid JSON or that a chapter title accurately describes its excerpt. Those questions require the separate source/output review in `assistant-review.json`.

Six deliberate diagnostic cases do not estimate accuracy on ordinary meetings, unseen languages, overlapping speech, or a broad document distribution. One local run is also not a latency benchmark. The results should be presented as measured behavior of a specific source/configuration/model, with any limitations visible to users of editable draft summaries.

## Correction under evaluation

The revised implementation sends a short source directly to one summary/key-points/chapter request. Longer sources are split at paragraph, sentence or word boundaries while retaining every original character and source index. Each direct/map/reduction/synthesis user message is capped at 3,200 decoded UTF-8 bytes, including timestamp prefixes and separators. The first correction bounded map notes at 2,400 bytes and reduced notes at 1,200 bytes; those intermediate guards proved too strict even when a result could fit the next bounded request. The next candidate aligns both note limits with the unchanged 3,200-byte input limit. Reduction must make strict total-byte progress, may use at most twelve rounds, and never silently slices away later notes. These limits are workload controls, not tokenizer-specific guarantees.

Known English or Greek source language is passed from the application and requested in every generated text field. When a single long source segment spans multiple internal requests, all pieces retain its original start and duplicate chapter starts are removed. No internal split invents a subtitle or chapter time. Final summary/key-point bounds reject an oversized result rather than silently remove its ending. The original 240-second transport limit and incomplete/output-limit checks remain in place.

The six original cases are now regression evidence. Separate validation sources were frozen before corrected inference in `tests/fixtures/summary_quality_validation_v2.json`, SHA-256 `3bf8f665ec0a87dcf8d4d125a1ff85e6299d2262d0398185406c746274e95559`: two new short cases (English duplicate refund and Greek donated/borrowed books) plus one long Greek quiz-score audit. The long case is a single 7,027-character / 12,775-byte segment with late corrected scores and ceremony timing. The new validation has not yet been evaluated; its expected facts are never additional model instructions.

### First corrected regression: preserved failure evidence

`qwen3-corrected-regression.json` is the exact actual report, SHA-256 `2423b0f6efb4033faa75f8f876fb14ba8c580d902736b8416f1604d8f3d6e821`. All six requested cases were processed in 679.833 seconds; four produced complete summaries and two retained the original transcript with a warning. Source hashes and selected runtime identity stayed fixed. All original transcript exports and fresh-interpreter reads passed. Ten actual inference requests and six successful unload controls were recorded separately; the largest inference user message was 3,186 UTF-8 bytes.

Assistant classifications were two acceptable, one minor issue, one major error and two not evaluable. The direct path repaired the original wrong operator and monetary corruption, and both completed Greek short cases returned Greek. The consent case still dropped the explicit publication action and added an unstated borrower. The bicycle output kept the correct facts in its main summary but had a payment-word typo and conditional-tense defect in a key point.

The English long pipeline completed all three maps. Its reducer shortened approximately 2,747 input bytes to 1,738 bytes, then the 1,200-byte guard rejected that useful contraction. The Greek long pipeline completed two smaller maps within the unchanged time limit (130.646 and 163.092 seconds); its second 2,531-byte note was rejected by the 2,400-byte map-note guard before later chunks were sent. Neither failure is a claim about an accepted final long summary, because none was produced.

The next candidate therefore changes the note guards without increasing outgoing input size or timeout, and makes the grounding instruction explicit about the action governed by permission/prohibition and the avoidance of unstated recipients, ownership, responsibilities or causes. Targeted regression and the unchanged fresh validation remain pending. No fixture-specific names, quantities or expected answers are encoded in the production prompt.

## Bounded-note and grounding regression — preserved full run

`qwen3-bounded-regression.json` is an exact copy of the next six-case actual
run on detached commit `e2895f5`. Its SHA-256 is
`9d618c75bf5f38947ec12e63e93d855ed4917d9e18be37b7ff0731f23c832324`.
All measured source hashes, the corpus and the selected model/runtime stayed
unchanged. This run predates the subsequent eight-point schema contract.

Four short cases pass the integration checks. Assistant review rates two
acceptable and two minor issues, with no material error observed in those four
complete outputs. The publication action and invented borrower errors are
repaired; the Greek bicycle result retains minor grammar and quote-status
compression concerns. This is case-specific evidence, not a general accuracy
approval.

Both long cases remain **not evaluable as delivered summaries**:

- English completed three maps, two reductions and synthesis, but returned
  **36 key points**, exceeding the then-accepted maximum of 30. The final raw
  response includes West Hall, 21 September and 28 visitors, but was correctly
  rejected and is not an accepted user result.
- Greek completed six maps and four reductions, then the fifth reduction
  returned **HTTP 500** after 0.585 seconds. No synthesis was attempted. Two
  completed reductions copied their input notes exactly. The server log ends
  with a runner-connection EOF while saving another prompt-cache state.

The full run took 1,628.348 seconds; the Greek case alone took 1,124.461 seconds.
There were 21 inference attempts, 20 completed responses and 6 unload controls.
Every inference user message stayed at or below 3,186 UTF-8 bytes, within the
3,200-byte bound. Original transcript exports, SQLite records and separate
interpreter retrieval survived both failures. These elapsed times are observed
QA runtime, not a controlled speed benchmark.

`runtime-cache-evidence.json` binds the raw server log checksum to its sanitized
archive. The log reported nine cached prompts using 2,837.489 MiB with an 8,192 MiB
limit, followed by another 436.114 MiB state-save attempt before the EOF. That
supports a memory-pressure hypothesis; it does not prove an OOM kill. The
bundled server’s help documents `LLAMA_ARG_CACHE_RAM` and `--cache-ram 0` to
disable that cache. Its inheritance and practical effect still require an
actual runtime check.

The next source revision explicitly requests and constrains at most eight
key points in direct/final responses, with a matching local guard. It retains
the source/note byte limits and does not clip generated points. This change
was first covered by engineering tests and then the mixed run below. Exact
completed English map/reduce responses can support clearly labeled mixed
replay/live regression; the failed Greek trace cannot be presented as a
complete pre-final replay. The three fresh summary cases remain unexposed
until these issues are resolved.

## Eight-point contract: mixed replay and live inference

`qwen3-eight-point-mixed-regression.json` preserves the complete two-case run
on unchanged detached commit `2760679`. Its SHA-256 is
`85a12389244825f2394e42c4f0459bdb4aabeac3d040326dd3727925499caea3`.
The process exited 0 and both cases passed the application, SQLite, export,
chapter-time and fresh-interpreter checks. Each accepted result has eight key
points, within the explicit request schema and matching local guard.

The consent case used one entirely new direct inference. The English long case
reused three completed map responses and two completed reductions from the
prior report, then made one new final inference. The replay helper required
exact ordered request and timeout matches and failed closed without a live
fallback. All five replayed stages, both live requests and two unload controls
are identified separately in the report. The 66.8-second elapsed time includes
replay and **is not fully live long-summary latency**. Replay source coverage
means the current code constructed the identical original requests; it does
not mean the model read that long source again.

Assistant review rates the English long final **acceptable**: it preserves
West Hall / 21 September / 28 visitors, the spending cap and unaccepted estimate,
volunteer uncertainty, no entry fee and the publication constraints. The
consent result has a **major error**: one key point says
`Equipment budget corrected to €8:84.75 from €847.50`. Its main prose correctly
says €84.75, but does not repair the contradictory malformed amount in the
separately displayed point. The other central roles, permission limits and
pending booking are retained. Valid JSON and a valid point count therefore do
not establish factual accuracy.

`qwen3-eight-point-mixed-manifest.json` records source/model/helper hashes,
the observed exit code, reproduction arguments and the exact evidence boundary.
`contract_replay_runner.py` and `contract_replay_runner_checks.py` preserve the
helper and historical checks without changing their bytes. Their **14-check
passing result belongs to frozen commit `2760679`**, not later summary contracts.
The archived checks intentionally have no `test_` filename prefix, so normal
current-suite collection does not run historical fixtures against new code.
The manifest also binds the raw server-log hash to its sanitized copy. A first launcher
attempt omitted the Python interpreter before the helper and failed before
client or model inference; the corrected invocation is the measured run.

The next candidate adds one general numerical-fidelity instruction and explicit
map/reduction note schemas. Map notes may contain at most 700 characters;
reduced notes at most 399. Two worst-case four-byte UTF-8 notes plus the
two-byte separator occupy 3,194 bytes, within the unchanged 3,200-byte request
limit. Matching local guards reject oversized output without clipping, and
reduction must still make strict total-byte progress. A separately coordinated
model-residency change addresses accumulated cache state. Consent and both
long cases must be run fully live with memory evidence before considering the
still-unexposed fresh validation. No broader summary-quality approval is given.
