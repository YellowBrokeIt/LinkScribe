# Hosted speaker preparation: declared source filenames

**Status: correction prepared and tested without models; a new hosted result is
still pending.** The original application integration and its complete published
[preparation bundle](../asr-speaker-timing-integration-2026-11-28/README.md) remain
unchanged. This follow-up changes only hosted model preparation and the workflow's
explicit plan reference.

## First observed failure

[Run 46121980993](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46121980993),
job `140908265951`, ran exact commit
`d62df26c870f175f7454fe0c3900d97891c8bff5` and stopped during preparation at
2026-11-28 07:37:28 UTC with **HTTP 404**. Source-plan validation, CPU runtime
installation and `pip check` passed. The application/model execution step was
skipped; there is no execution marker, recognizer output or speaker result.

The retained preparation report proves all four original FLAC identities and the
complete original 34.635-second WAV matched. Independent inspection also matches
its 554,160 decoded samples to PCM SHA256
`70f602e7be70e59448259d311dad673459d551198cf274c3615a2649f513b194`.
All 16 installed runtime versions match the original plan. Four Small files and
the ECAPA classifier, YAML and mean/variance checkpoint were downloaded and
hash-verified before the failure.

The committed sequential loop identifies the next attempted URL as the pinned
ECAPA repository's `label_encoder.ckpt`. The original HTTP exception did not
record a URL, so this attribution is explicitly derived from source order and
the completed download checkpoints. The literal alternative `label_encoder.txt`
is **not established by locally retained metadata** and is not guessed in this
correction.

The exact ZIP is artifact `15254385257`, 1,872,129 bytes, SHA256
`be2651874e1eb4019114bc208553a36934772d5db0a5aaa03a6f31698dc32aa2`.
Its [complete member inventory](first-hosted-failure/artifact-manifest.json),
[raw preparation report](first-hosted-failure/artifact/preparation.json),
[original exception](first-hosted-failure/artifact/prepare-failure.json),
[job log](first-hosted-failure/job.log), and
[independent first-failure review](independent-first-failure-review/independent-failure-review.json)
are retained. The independent audit passed all 34 artifact/source/PCM checks.

The [archive selection](first-hosted-failure/archive-selection.json) states which
of the original 12 artifact members are included here. Five reproducible licensed
audio files are omitted from this Git bundle, with their exact sizes/hashes;
the complete verified ZIP and extracted audio remain in the recorded scratch
location. This selected archive does not claim to contain those audio bytes.

## Concrete cause and correction

The pinned SpeechBrain 1.1.2 `Pretrainer.collect_files` implementation takes the
**remote filename from `self.paths[name]`**, while independently setting
**`save_filename = name + '.ckpt'`**. The first hosted helper incorrectly used
local cache filenames as remote repository filenames. That source/cache-name
equivalence is not the native API contract.

The corrected preparation follows the retained primary source:

1. Fetch the same exact pinned `hyperparams.yaml`, verify its unchanged SHA256,
   and preserve its bytes immediately, before another ECAPA transfer can fail.
2. Inspect YAML nodes without object construction. Keep the exact expected
   Pretrainer class, four loadable references and repository base; resolve only
   each explicit `<pretrained_path>/<single filename>` declaration.
3. Reject extra or duplicate entries, unresolved references, traversal, absolute
   URLs/paths, query strings, fragments and backslashes. Record the complete
   declared source-to-cache mapping before checkpoint transfers.
4. Fetch each declared remote filename from the same pinned repository revision
   into its unchanged local `<loadable>.ckpt` filename, enforcing the unchanged
   expected file SHA. Seed the HF snapshot under its **remote** filename and the
   savedir under its **local** filename using identical bytes.
5. Record stage, family, source filename, local filename, public request URL and
   expected SHA before each transfer. Preserve the original exception and HTTP
   status on failure. Early runtime errors have an initialized stage and cannot
   be masked by a secondary missing-key error.

No model is constructed by this preparation. The previously rejected ad hoc
metadata fetch was not retried or routed around. The separately authorized
hosted preparation must acquire the already pinned YAML and supply its actual
declarations; the correction does not claim those absent bytes were inspected
locally.

## Frozen scope and checks

[The separate follow-up plan](hosted-plan.json) retains its original parent plan
and binds the corrected controller/workflow. The
[parent comparison](parent-comparison.json) verifies that the fixture, model
identities, runtime, decoder policy, meaning criteria, resource caps, worker
environment, observation contract and attempt count are unchanged. Nineteen
other execution-source bindings remain identical. Production `app.py`,
`asr_timing.py`, speaker implementation and the actual smoke observer are unchanged.

The original [controller](published-before-correction/controller.py),
[controls](published-before-correction/controls.py),
[workflow](published-before-correction/workflow.yml) and
[plan](published-before-correction/hosted-plan.json) are preserved exactly.
Historical failed evidence is not rewritten to describe the correction.

The [focused model-free controls](mapping-controls.txt) passed **30 tests in
0.48 seconds**. New controls prove different source/cache names, correct HF
snapshot names, YAML/mapping retention before transfer failure, rejection of
unsafe path forms before checkpoint transfer, extra-loadable rejection and
preservation of an early runtime exception. Existing one-attempt, resource,
cleanup, full-fixture and raw-return controls remain in that same file.

[Validation-only preflight](preflight.json) also passed with no model construction
or inference. The [final independent correction review](independent-correction-review/independent-correction-review.json)
found no remaining blocker, with 50 passing source-binding/AST checks and no
additional model or provider execution. It keeps actual pinned-YAML/source-name
observation explicitly pending. The upcoming reviewed hosted attempt retains all original
application/persistence/acoustic checks. Preparation success alone will not
establish actual timing, speaker, semantic or v1 release quality.
