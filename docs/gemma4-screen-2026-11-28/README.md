# Gemma 4 E4B QAT: bounded text-only development screen

This experiment tests one distinct, publicly available local model against the
same six exposed English/Greek translation cases. It changes no production
default. Preparation and results are recorded separately, and execution success
does not approve translation meaning, summaries, or v1.0 readiness.

## Outcome

The single six-case screen completed. Independent semantic review classified
five cases as acceptable and one as a minor issue, with no major errors. This
is a promising development result. It is not approval of unseen inputs, longer
translations, summaries, the full application memory budget or a production
default.

| Original case | Independent meaning assessment |
| --- | --- |
| English → Greek: transcript, recording and translation chronology | Minor issue: incorrect Greek article/accent and less precise recording terminology; required propositions and chronology preserved |
| Greek → English: people and roles | Acceptable: Nikos, Eleni and Elena remain distinct with the correct recipient and roles |
| English → Greek: receipt, separate transfer, Bitcoin amounts and units | Acceptable: values, negated amount, separate transfer and distinct units preserved |
| Greek → English: negation scope | Acceptable: attribution, Anna, yesterday's negation and today's uncertainty preserved |
| English → Greek: conditional publication | Acceptable: Anna/Giannis, approval requirement, Friday deadline and Monday fallback preserved |
| Greek → English: uncertain question | Acceptable: Maria, the 12-or-21 question, unresolved answer and title-only limitation preserved |

For example, the first case correctly distinguishes completed transcription
from translation that has not started. Its Greek contains `το μεταγραφή` and
`αποθηκεύσε`, which are grammatical/accent errors, and uses the less specific
`καταγραφή` for recording. Those defects remain in the retained output; no
correction or second attempt was applied.

| Measured phase | Elapsed | Peak concurrent RSS | Peak concurrent PSS |
| --- | ---: | ---: | ---: |
| Successful import and native render/token preflight | 14.139 s | 5742.7 MiB | 5733.9 MiB |
| Six actual translations, including model loads and unloads | 82.220 s | 5799.3 MiB | 5790.4 MiB |

The inference monitor retained 385 complete samples. The maximum RSS was about
5.66 GiB, only 344.7 MiB below the 6 GiB process limit; that margin must not be
mistaken for a full-app or larger-context resource pass. Each of the six model
responses stopped normally, had empty reasoning, preserved the schema, and was
followed by an acknowledged unload. Actual prompt counts exactly matched
preflight: 129, 158, 148, 149, 125 and 154 tokens. Output counts were 74, 48, 89,
55, 82 and 55 tokens, well below 2048. Raw returned JSON and the application's
parsed translation strings agree exactly. Owned model/daemon processes exited.

`infer.json` retains the case checks; `infer-resources.json` retains the
external resource observations and process exits; `request-metrics.json` binds
each raw response, final content and report by hash. The independent review
retains its own source/criteria, report and output bindings. No unused validation
input, summary call, retry or production edit occurred.

An initial setup check failed before model loading: official create succeeded,
but the verifier looked in the legacy manifest directory. This Ollama version
writes newly created models under `manifests-v2/ollama.com`. The initial plan,
script, failure and resource report remain under `initial-*`. The revised plan
changes only that observed cache-layout verification and pins the resulting
native manifest. The selected original model blob, parameters, prompts and
semantic criteria are unchanged. Import reused the single 5,154,947,072-byte
physical payload allocation; all imported blobs together occupied
5,154,959,360 bytes.

## Why this candidate

The selected file is Google's own
[Gemma 4 E4B instruction-tuned QAT Q4_0 GGUF](https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf),
at revision `4b4a2c1d584be7264f87aac328a1bc739ce81b6c`. It is an Apache-2.0,
public, ungated release with a native llama.cpp/Ollama path. The model family,
training, native turn format and quantization-aware training are distinct from
the previously rejected Gemma 3/TranslateGemma, Qwen, Hy-MT, Marian and M2M100
profiles. This is a reason to test it, not evidence that its meanings are right.

The complete text file `gemma-4-E4B_q4_0-it.gguf` contains 5,154,941,280 bytes
(4.80 GiB), SHA256
`676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee`.
The separately published 991,552,256-byte image/audio projector is optional and
is not downloaded or imported. No draft model is used. This experiment claims
only text input and text output.

The current ordinary Ollama `gemma4:e4b` Linux manifest is larger: its text
weights alone are 5,493,439,296 bytes, with a 991,552,256-byte projector and
98,653,280-byte draft. Its displayed effective parameter count is not its full
stored size. The selected publisher QAT file avoids that package's additional
components and uses a single verified payload in an isolated model cache.

[Google's deployment guidance](https://gemma.ai/models/gemma-4/) recommends its
QAT GGUF files for local llama.cpp execution. Its weight/mobile/GPU estimates
are not measurements of our CPU process. Actual import, native loading and
generation therefore have an external sampled 6 GiB process-tree stop. Browser,
OS and unrelated memory remain outside that measurement; the 7.3 GiB whole
machine goal is not approved by this screen.

The [publisher model card](https://huggingface.co/google/gemma-4-E4B-it) describes
140+ pretraining languages and 35+ supported languages but does not enumerate
Greek or provide a Greek translation score in the examined primary materials.
We make no Greek-specific quality claim from that description. The original
English/Greek sources and semantic criteria are the actual test.

## Fixed protocol and limits

The production translation implementation is copied to
`enhancements-context4096.py` with exactly one code change: context allocation
8192 becomes 4096. `context-only.patch` records it. The root production file is
unchanged. The model's native formatting changes with the model, while the
system/user instructions, schema, source text, four CPU threads, temperature 0,
2048 output-token cap, non-thinking request, 240-second request timeout and
explicit unload policy remain the same. The imported native sampling defaults
are Google's temperature 1 / top-p 0.95 / top-k 64; the explicit production
temperature 0 overrides that temperature during the test.

Before any quality output, all six complete system/user requests are rendered
through the actual native runtime in render-only mode and compared with the
[official small-Gemma format](https://gemma.ai/get-started/capabilities/thinking/).
The complete rendered prompts are tokenized by the loaded native runner. Every
prompt must fit with the entire 2048-token response allowance and an end-token
reserve. The reduced context is specific to this short development screen; it
does not justify a long-summary limit or a production change.

There is one attempt per original case, in the original order. A structural,
execution, protocol, cleanup, response-length, time or sampled-memory failure
stops the screen. All completed and partial outputs are retained. No glossary,
name replacement, source rewriting, retry, alternate quantization, summary
call or unused validation input is allowed. The independent reviewer judges
the original meanings, including people/roles, numbers and relationships,
negation, uncertainty, chronology, actions and conditions. Lexical indicators
cannot approve those meanings.

## Preparation and reproduction

`plan.json` and `plan.sha256` freeze the candidate, input files, isolated code
snapshot, native runtime identities, controls and stop rules before download or
candidate output. `publisher-render-verification.json` checks the selected
six-request format against the pinned publisher Jinja template without running
a model. `source-provenance.json` retains the official metadata and source-file
hashes; the publisher README's Git blob identity is verified as well.

The download goes directly to the experiment's isolated content-addressed
Ollama blob path. `/api/create` references that existing SHA, avoiding a second
physical copy and leaving shared models untouched. Imported manifest/layer
hashes and allocated disk bytes are verified and recorded. Native render-only
preparation may load/warm up the model but generates no answer; its memory and
time are measured separately from quality inference. Daemon logs stay private.

The runner refuses existing output reports. Reproduction requires a new owned
output location; overwriting the retained result would destroy the experiment's
history. The setup evidence and native token identities are frozen again before
the first quality request. Only completed reports are sent for independent
semantic review.

Additional primary sources: the
[Gemma 4 technical report](https://arxiv.org/html/2607.02770v1),
[native prompt format](https://gemma.ai/get-started/prompt-formatting/),
[Ollama v0.40.12 source](https://github.com/ollama/ollama/tree/v0.40.12), and
[Apache-2.0 license](https://gemma.ai/resources/apache-2/).
