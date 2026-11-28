# Separate speaker timing from recognition

**Status: production source and model-free checks prepared; the source-bound
hosted speaker pipeline has not run yet.** This is a reliability change within
version 0.3.0. It does not approve ASR, word timing, speaker accuracy or a v1 release.

The change removes a coupling in the previous speaker path: requesting speakers
enabled native word timing during recognition, where faster-whisper may change
later recognition seeks and therefore later words. The new path completes one
ordinary recognition pass with `word_timestamps=False`, accepts the complete
baseline under the existing source/duration/no-speech checks, and only then
attempts fixed-text timing for optional speaker assignment.

## Production contract

`RecognitionResult` keeps the authoritative baseline, optional speaker-input
segments, detected language, bounded warnings and small ASR provenance separate.
The result carries no model, decoded audio, features, original token arrays,
native alignment paths or exception objects. Ordinary link/upload callers and
current smoke consumers use this explicit result together; frozen historical
experiments remain unchanged.

The new `asr_timing.py` adapter uses the same engine and full waveform. It derives
the frontend, tokenizer and window layout from that engine, retains exact yielded
native text/tokens/seek, and makes fixed-token encode/align calls on those original
windows. It does not transcribe again, generate replacements, redetect language,
re-encode the recognized text, trim the source or change recognition seeks.
It uses the inspected upstream word timing/punctuation adjustments and `get_end`
state update. Conflicting intervals revert both involved segments to their exact
physically bounded baseline; repeated conflict detection handles newly affected
neighbors. Invalid private words clear the entire segment's optional word evidence.

The application passes independent baseline/raw copies into this optional helper
and validates candidate text, order and bounds before accepting it. A helper that
mutates its input and raises, returns changed text or fails late cannot replace
the accepted baseline. Speaker-backend failure likewise saves the original
baseline. Warnings remain visible through the existing durable warning path;
`_words` is stripped before persistence and text AI.

Optional timing explicitly supports the inspected **faster-whisper 1.2.1 and
CTranslate2 4.9.1** interface. Other permitted recognition runtimes retain ordinary
recognition but receive a visible timing-unavailable fallback. This guard does
not narrow the base recognizer's package requirements or silently change a model.

After recognition and optional timing return, production clears only the
recognizer cache before acoustic speaker inference, preserving reusable
speaker/VAD caches. Existing full audio-cache release before translation/summary
remains. Weak-reference/order tests cover this lifetime; immediate return of all
native allocator pages to the operating system is not promised.

## Evidence and meaningful checks

- [Approved architecture proposal and original inspection](proposal/PROPOSAL.md).
- [Exact current integration source inventory](source-inventory.json).
- [Independent production-source review](independent-review/independent-core-source-review.json),
  which found no concrete blocker in the baseline, native window/token contract,
  fallback, persistence or lifetime implementation.
- [Final independent hosted-contract review](independent-review/independent-hosted-contract-review.json),
  which verified all 21 plan-bound source files and independently passed the five
  correction controls without models or provider requests.
- [Retained focused test records](local-checks.json). Earlier 93-, 94-, 201- and
  123-pass results retain their original chronological scope. The final hosted
  control file passed **18 tests in 0.39 seconds**, with no models or providers.
- [Source-bound validation-only result](local-checks/hosted-preflight.json).
  It explicitly records no model construction or inference.

Controls cover one baseline recognition with speakers on/off, complete waveform
and dynamic 80/128-row frontend mapping, original tokens/window/terminal endpoint,
upstream sequential state, late and malformed timing failures, immutable baseline
defense, conflict propagation, bounded warnings that still persist, speaker failure
fallback, cache lifetime and exact replay of the five retained pure projections.
The hosted controller has separate controls for source drift, a duplicate attempt,
final/phase resource limits, complete fixture construction, owned-child cleanup,
unreadable process accounting, malformed native returns and non-instantiating
speaker configuration inspection.

The [initial hosted preparation](preparation-history/hosted-before-review/snapshot.json)
and its 13-pass control result are preserved. Independent review identified two
evidence defects there: unreadable process RSS could be skipped, and native
alignment returns were only recorded after validation. The corrected helper
retains per-member accounting/errors, fails incomplete measurements, and records
raw native returns through an ephemeral guard proxy **before** validation. It
does not mutate the engine's cached native model. The archived initial plan was
not yet rebound after fixture-construction refactoring; it is preparation history,
not an executable frozen source contract.

The first root combined-suite attempt stopped during collection: pytest also
discovered historical `test_*.py` snapshots under `docs/`, where old relative
imports collided and a standalone experiment's execution-denial audit hook could
affect unrelated tests. The root-owned `pytest.ini` repair limits normal discovery
to maintained `tests/`; the historical snapshots and standalone controls remain
unchanged. The original collection failure and the same-command follow-up are
retained separately in `docs/integration-2026-11-28/speaker-timing-local`.
The corrected maintained suite passed **834 tests and 54 subtests in 11.55 seconds**;
the root's [source-bound verification](../integration-2026-11-28/speaker-timing-local/maintained-suite/verification.json)
and [pytest output](../integration-2026-11-28/speaker-timing-local/maintained-suite/pytest.txt)
are retained separately from this preparation manifest.

## One prospective hosted pipeline

[The frozen plan](hosted-plan.json),
[runtime pins](hosted-runtime.txt),
[controller](../../tests/qa_speaker_integration.py) and
[workflow](../../.github/workflows/speaker-integration-qa.yml) define one original
two-reader upload through the actual application, without translation or summary.
No local model installation or execution is part of this preparation.

The input is the already exposed, licensed LibriSpeech/LibriVox-derived
`two_speakers_returning.wav`: 554,160 samples at 16 kHz, 34.635 seconds, SHA256
`dc977c1cb0af1a30946eeb0c59218039987412462d2e8c5a2d23990b559f087f`.
Preparation recovers the same four original FLAC identities and exactly
reconstructs the historical fixture; it checks the complete WAV hash and original
annotations. The full constructed WAV enters the application unchanged. Known
reader intervals are used only after the owned model process exits.

| Component | Frozen identity / contract |
|---|---|
| Recognition | Systran/faster-whisper-small, revision `536b0662742c02347bc0e980a01041f333bce120`; four exact files |
| Speakers | speechbrain/spkrec-ecapa-voxceleb, revision `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`; four checkpoints plus exact YAML |
| Native policy | One automatic-language transcribe, beam 5, VAD off, normal fallback, previous-text conditioning off, word timestamps false |
| Optional timing | Same engine; fixed source strings/tokens and original seek windows; raw requests/returns retained separately |
| Resources | At most four available CPUs, 6 GiB owned-group RSS, 600 seconds total; bounded phases; one attempt |
| Persistence | Actual SQLite save, reload in a fresh process, durable downloads after job eviction, TXT/JSON/SRT/VTT/ZIP and backup |
| Observed lifetime | Recognizer cache and weak references released before actual acoustic speaker analysis |

The controller retains a 100 ms per-process-group sample series, known member
states/RSS, read errors, final worker high-water RSS, phase times and cleanup.
Incomplete accounting cannot pass. Sampled and OS high-water evidence are still
measurement methods, not proof of a continuous whole-machine memory bound.

Pinned SpeechBrain 1.1.2 source inspection shows existing savedir files resolve
before a Hugging Face fetch; it does not request `custom.py` in this path.
The exact YAML was absent locally. A small metadata fetch was rejected by
automatic approval review as outside the no-download scope, and was not retried.
During separately authorized hosted acquisition, the helper first verifies its
known SHA, preserves its exact bytes, and uses `yaml.compose` nodes to check that
the declared loadables/paths resolve only to the four seeded checkpoints. That
inspection performs no HyperPyYAML object construction. Actual hosted preparation
must supply the remaining cache evidence before inference can begin.

Offline Hugging Face/Transformers/dataset flags and telemetry settings are declared
for the worker after acquisition. This is not a claim of OS-wide network isolation
or observed zero socket attempts. Since translation and summary are disabled,
the actual run can verify recognizer-before-speakers release; audio-before-text-AI
release remains source and controlled-test evidence.

Two output labels establish pipeline execution only. The separate original
controlled acoustic score requires two clusters, at least 80% assigned core
coverage and at least 95% permutation-matched label purity. Raw acoustic turns,
native timing and saved text remain available for independent comparison with
the original annotations. No natural-meeting, overlapping-speaker, Greek,
multilingual or general word-time accuracy is inferred from this constructed
English fixture.

## Preserved limits and history

The earlier [original global-fallback diagnostic](../post-asr-alignment-diagnostic-2026-11-28/README.md)
remains rejected for its full-film improvement goal. The separately reviewed
[offline local projection](../post-asr-local-projection-2026-11-28/README.md)
retained 78/86 word-bearing film segments and passed six broad segment windows,
but only three word windows; large movements around short utterances remain.
Those outputs motivate the defensive integration and provide exact pure replay
controls. They do not certify this future application revision or acoustic truth.

Every recognized lexical error remains a lexical error. Forced timing does not
establish that a word was spoken. Unsupported or malformed optional timing keeps
the accepted transcript with a warning. OS/native process death cannot be made
transcript-preserving by an in-process exception handler; process-death recovery
and long-recording resource fit remain distinct outstanding risks.

No ASR default, model weights, version, provider access policy, frozen reference
window or historical result was changed to make these checks pass.
