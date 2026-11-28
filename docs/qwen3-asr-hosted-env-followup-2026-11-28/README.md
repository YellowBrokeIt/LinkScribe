# Hosted path setup correction — no model output yet

The first published Qwen screen at commit
[`a4ca88ec`](https://github.com/YellowBrokeIt/LinkScribe/commit/a4ca88ec2820f8c0e1c29f4a7f5d36b8f0a32db3)
was rejected before GitHub created any job. The
[failed run](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46098646055)
reported: `(Line: 30, Col: 21): Unrecognized named-value: 'runner'. Located at position 1 within expression: runner.temp`.

The [retained run record](failed-run.json) records zero jobs and zero artifacts.
No runtime installation, model download, initialization, recognition attempt or
hypothesis exists from that run. There is no artifact ZIP or digest to retrieve.
The exact [failed workflow](failed-workflow.yml) is preserved. The original
[plan](../qwen3-asr-screen-2026-11-28/plan.json) and
[manifest](../qwen3-asr-screen-2026-11-28/manifest.json) remain byte-for-byte unchanged
as the historical published preparation.

## Correction

The [current workflow](../../.github/workflows/qwen3-asr-candidate-qa.yml) sets
`QWEN_QA_ROOT` in an initial shell step using the runner's `RUNNER_TEMP` and
`GITHUB_ENV`, then passes this directory to all later steps. GitHub's
[context availability reference](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability)
does not permit the `runner` context in job-level `env`; it is available at step
level. The artifact upload retains its valid step-level `runner.temp` expression.

Every helper action now explicitly names the [corrected plan](plan.json).
The unit harness uses that plan, and scoped LF attributes preserve its exact
source identities across platforms. The original helper remains unchanged at
SHA256 `f578d2b534506e42f8636d45bd5d43d2fea64902961ad265f62b82b3a5d0fc8f`.

The execution protocol is unchanged: the same pinned native model and CPU runtime,
same eight full recordings and meaning criteria, automatic language identification,
one initialization and one attempt per clip, the same greedy/EOS policy, and the
same resource limits. This correction does not alter recognition settings or
represent a repeated recognition attempt; the first workflow never reached one.

## Verification and next observation

[Local validation](local-validation.json) confirms all 14 non-model tests passed,
all six shell blocks parse, the setup step works with a temporary path containing
spaces, and all four helper actions select the corrected plan. The plan comparison
found no execution change beyond the workflow's byte identity. The original plan
and manifest hashes remain unchanged. [Validate-only](local-preflight.json) imports
no model and performs no inference.
The [independent followup binding](hosted-env-followup-binding.json) confirms the
path-only scope, preserving the [original pre-output criteria binding](source-and-criteria-before-output.json).
The [manifest](manifest.json) freezes this correction and its evidence.

The next observation must come from an actual hosted job at its new commit.
The [original screen documentation](../qwen3-asr-screen-2026-11-28/README.md)
describes the unchanged raw-output, full-input, completion and resource checks.
Structural completion still requires independent review of all eight unrepaired
transcripts. This note makes no claim that the candidate has loaded or passed.
