# Archive the completed Qwen experiment workflow

The isolated Qwen CPU screen completed at commit
[`7ee0c7f2`](https://github.com/YellowBrokeIt/LinkScribe/commit/7ee0c7f2ac319d817ae9861a1d632a56ed62908e),
with its [actual outputs and independent rejection](../qwen3-asr-hosted-results-2026-11-28/README.md)
preserved separately. Its eight exposed cases had six major meaning errors and
two acceptable results. No production adoption or fresh validation followed.

The completed workflow listened to feature-branch pushes. Integrating its
previously verified runner-directory correction would otherwise launch another
expensive download and recognition run with the same rejected candidate. This
checkpoint therefore removes that experiment workflow from the active workflow
directory. Every ordinary application test, browser, actual-upload, installation,
package and Ollama workflow remains active and unchanged by this retirement.

[completed-hosted-workflow.yml](completed-hosted-workflow.yml) preserves the exact
3459 bytes from the completed screen, SHA-256
`1ef312a65ff80a8000ef29733f69ed34520ef2e930bdfa014cf060a0a9ed3c42`.
The original and corrected plans, runner, criteria, inputs and actual outputs are
unchanged. Reproduction uses the published `qa/qwen3-asr-a4ca88e-env` branch or its
exact commit above. The immutable plan intentionally does not validate the live
checkout after its bound workflow is retired.

The non-model contract tests now construct an explicit historical source view:
every plan-bound file must match its original size and SHA-256, and the archived
workflow occupies its original relative path within the temporary view. The
original positive, mutation-rejection, no-ML-import, token/completion and resource
checks run against that view. They do not claim that historical model outputs
verify the later application. The [preceding test file](historical-unit.py) is
retained unchanged. Scoped LF rules preserve these frozen bytes on all platforms.

No model is downloaded or run for this change, and no release acceptance gate is
removed. This is housekeeping for a completed failed experiment, not a result
change or a v1.0 approval.

[Independent review](independent-review.json) confirms the archive matches the
actual completed Git object, all 14 historical tests are retained, and the five
ordinary application workflows are byte-identical to the preceding checkpoint.
The complete local suite subsequently passed 753 tests and 54 subtests.
