# Gemma 4 native thinking ablation

## Outcome

**Rejected after the single approved attempt.** Native thinking completed
normally within all fixed execution limits, but independent review classified
the final translation as a major semantic error. The borrowing relationship
remains unintelligible, the material is imprecise, and the denied-gift actor is
unclear. No repair, retry, additional case or promotion followed.

The actual final translation strings are retained unchanged:

> Η Αριάδνη διαθέτει το χάλκινο τηλεσκόπιο. Ο Μάρκος το לקρέφτηκε για την επίδειξη του ουρανού, αλλά δεν το έδωσε σε αυτόν.

> Πρέπει να το επιστρέψει σε εκείνη μετά την επίδειξη, ακόμα κι αν τελειώσει νωρίς.

The mixed Hebrew/Greek verb `לקρέφτηκε` does not convey that Markos borrowed
the telescope. `χάλκινο` gives copper/bronze wording rather than the precise
brass material. Night-sky loses night. Ariadne's possession, the return
obligation and the even-if-early condition survive. The independent reviewer
graded only the final translated content; the presence of a separate thought
channel did not count as semantic success.

| Observed measure | Result |
| --- | ---: |
| Generation attempts / acknowledged unload controls | 1 / 1 |
| Normal final stop | Yes |
| Actual native prompt tokens | 142 |
| Shared generated tokens, thinking plus final | 787 / 2048 maximum |
| Separate thinking field | Present, 2143 characters |
| Supervised elapsed time | 77.522 s |
| Peak concurrent process-tree RSS / PSS | 5793.3 / 5784.3 MiB |
| Complete memory samples | 353 |
| RSS margin below the fixed 6144 MiB stop | 350.7 MiB |
| Original source, schema and segment metadata | Preserved |
| Worker exit / owned process cleanup | Zero / confirmed |
| Independent semantic verdict | Major error |

The same non-thinking request previously used 140 prompt tokens and generated
98 tokens. This ablation changed only the thinking switch: the complete native
prompt grew by two tokens and total generation grew to 787 tokens. There is no
separately measured thought-token count; the recorded 2143 figure is characters.
More generation did not fix the actual first failure.

[`execution.json`](execution.json), [`native-preflight.json`](native-preflight.json),
[`resources.json`](resources.json) and [`request-metrics.json`](request-metrics.json)
retain the complete request, original model identity, native prompt/tokens,
raw response, output reconstruction and measured process scope. The exact
[`independent-review.json`](independent-review.json) retains criterion-by-criterion
judgments and its independent source/output bindings. The original source and
criteria were acknowledged before execution. The execution report's original
`unreviewed` label is preserved; the subsequent independent review is the
semantic decision.

The previous [complete exposed v2 screen](../gemma4-exposed-v2-2026-11-28/README.md)
remains immutable and rejected, with seven major errors, three minor issues and
two acceptable cases. No unused v3 input, summary test, whole-app test or
production switch was opened or run here. The process measurements are sampled,
exclude unrelated/OS/browser residency and do not approve full-app resources.

The following sections preserve the source rationale and predeclared controls.

## Exact setting change

The only proposed request change is `think:false` to `think:true`. A separate
copy of the already frozen 4096-context adapter would change its single
`body["think"] = False` assignment to `True`.
[`thinking-only.patch`](thinking-only.patch) contains that exact one-line patch;
the original adapter remains immutable.

The model is the same official Google E4B QAT Q4_0 text file, SHA256
`676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee`,
with the same imported native manifest, Ollama 0.40.12 binary, native small-model
renderer and thinking-capable `gemma4` parser. Temperature 0, context 4096,
maximum generated tokens 2048, four CPU threads, schema, complete messages,
fragmentation, metadata and unload behavior stay fixed. No projector, draft,
new weights, glossary, replacement or expected-answer hint is proposed.

The archived base adapter SHA256 is
`819568e7dd6939ffc9b9eb91130109235b97fb1cfee6192838645dc4e34aa178`;
applying only this patch produces SHA256
`c0ab3becf1565ef649480ed22cbca797723509f048965c055cbe8064769b17ac`.
The production checkout can change independently. A new experiment would bind
and execute this archived candidate explicitly and record the current checkout
separately, rather than rewrite historical source checks.

## Documented mechanism and output budget

[Google's thinking documentation](https://gemma.ai/get-started/capabilities/thinking/)
describes enabling thinking for E2B/E4B by inserting the native `<|think|>`
control token in the first system turn. The
[pinned publisher template](https://huggingface.co/google/gemma-4-E4B-it/blob/4ecc2ba63bcac23ba4a767fc87025b1450f84c9c/chat_template.jinja)
has that exact branch. An offline render of the original full telescope request
matches the prior observed native prompt when thinking is false. With thinking
true, its only difference is the control token and newline. This check invokes
the template alone; it is not a new native-token measurement or inference.

The pinned Ollama
[renderer](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/model/renderers/gemma4.go)
accepts the boolean switch and uses the same control token. Its
[parser](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/model/parsers/gemma4.go)
separates the thought channel from final content. For a structured response, the
[native request implementation](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/llm/llama_server.go)
applies the requested JSON schema after the thought-closing marker. This avoids
placing translation-answer hints into the source messages.

The same native request implementation forwards the fixed `num_predict` value
as one `n_predict` allowance. Thinking, channel markers and the final answer
share those 2048 generated tokens. There is no additional 2048-token allowance
for the final JSON. The
[thinking grammar](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/llm/gbnf.go)
also permits ending before the thought-closing marker, so requested thinking
does not guarantee a final answer. Empty-final, malformed, incomplete or
length-limited output must remain a failure. No forced closing marker, retry or
larger output budget is proposed.

All six inspected runtime source files were verified against the Git blob
identities in commit `f067033f9126993b6172bdfffa71a74ad693fda4`.
[`source-evidence.json`](source-evidence.json) retains exact URLs and hashes;
[`publisher-render-check.json`](publisher-render-check.json) retains the
generation-free template comparison.

## Bounded first test

The proposal uses exactly one attempt at the original exposed
`v2-holdout-en-el-telescope-ownership` case. Both complete source segments,
timestamps, speaker fields and all original criteria are retained in
[`telescope-source-and-criteria.json`](telescope-source-and-criteria.json).
The model receives only the original system/user source messages, retained in
[`proposed-request.json`](proposed-request.json); reference translations and
review criteria are not sent to it. The prior failed non-thinking output is
the control and is not regenerated.

Before a generation, a new frozen worker and supervisor must verify the full
existing model and runtime identities, assert that the actual request differs
only in `think`, and preflight its actual native rendering and tokenizer. The
complete prompt plus 2048 output tokens and one end reserve must fit in 4096.
The previously measured non-thinking prompt was 140 tokens; the thinking prompt
count is deliberately unclaimed until that native preflight.

The external monitor covers loading and inference, with a 6144 MiB sampled
concurrent process-tree RSS stop, four threads, 180 seconds for initialization,
240 seconds for the single generation and 600 seconds for the entire case and
cleanup. More generated tokens may increase observed residency; earlier
non-thinking memory results do not guarantee this run fits. The monitor must
stop on measurement, memory or time failure, retain partial evidence, confirm
unload and stop only its owned processes.

The final JSON must stop normally, preserve the original schema and metadata,
match the actual native prompt count and remain below the output cap. The raw
response and separate thinking field will be retained, but only final translated
content is graded against the unchanged source and criteria by the independent
reviewer. A missing separate thought span will be reported explicitly. There
will be no repairs or second attempts. A failed result ends this ablation; a
passing result does not approve other v2 cases, fresh validation, summaries,
whole-app memory fit or production adoption.

The original proposal is [`proposal.json`](proposal.json), SHA256
`793f7222b98f9c9d3585c3a0257fccce97200a9f0ae6ca1417ffe740f39e724b`.
Its original `proposed_not_executed` status is retained unchanged as a historical
pre-approval artifact. Root subsequently approved exactly this one attempt.
[`inference-freeze.json`](inference-freeze.json), SHA256
`4fbbc0dd688e9d8500534a728de468b7222e5309a1138ff4ba260d1616d955f0`,
froze the new adapter, worker, supervisor, exact request and all executed/input
dependencies, including the independent original-criteria acknowledgment,
before model execution. All those identities remained unchanged through the run.
[`evidence-manifest.json`](evidence-manifest.json) freezes the complete experiment
and final independent rejection.
