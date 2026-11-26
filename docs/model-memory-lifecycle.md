# Local model lifetime

The application processes one job at a time. Its audio stages finish before
translation and summary. When a job needs text-model inference, it clears the
already-loaded Whisper, public SpeechBrain ECAPA, and shared Silero VAD caches
after audio analysis. It then collects Python reference cycles. Cleanup does not
import an unused optional model or delete downloaded weights.

Jobs that perform only transcription or speaker analysis retain those caches for
reuse. Selecting translation into the already-detected source language also
retains them unless summary is enabled. The next audio job after text enhancement
reloads its audio models from the existing local cache, trading some loading
latency for fewer simultaneously live model objects. Collection does not promise
that native allocators return every page immediately; measured RSS/PSS remains
the resource acceptance evidence. The optional legacy pyannote model is outside
this helper; the complete workflow resource check uses the public speaker path.

## Ollama phases

Each translation or summary operation captures its selected model before the
first model/protocol use and keeps that selection for all of its requests.
Translation fragments and summary map/reduce steps retain that exact selection
across reloads. The default policy allows two returned inference responses per
residency interval. Before a third inference request, the application sends an
`/api/chat` control request with that exact model, an empty messages array, and
`keep_alive: 0`. Its timeout is five seconds. The next inference is permitted
only when the response contains the boolean `done: true` and
`done_reason: "unload"`. A successful HTTP status alone is insufficient.

If this intermediate cleanup times out, fails, or lacks the acknowledgment, the
enhancement stops before the next inference. Its error explains that cleanup
could not be confirmed and that the original transcript remains available.
Partially generated translation or summary output is not substituted for a
complete result. The enclosing operation still attempts final cleanup.

After any actual inference was attempted, a finalizer makes one best-effort
unload request, including after inference failure. Final cleanup failure cannot
replace the original error or discard completed text; a short diagnostic states
that the model may remain loaded. No control is sent for a no-op translation,
native Marian translation, or an error before any Ollama inference was attempted.
These control requests contain no transcript text. The app does not modify global
Ollama daemon settings or unload unrelated models.

The two-response interval is an operational guard against accumulating model
state during long jobs, not a universal RAM bound. A long summary previously
failed with a runner EOF during a prompt-cache save; the retained runtime log
showed nine cached prompts totaling approximately 2837 MiB. That run lacked
concurrent memory samples and OOM counters, so memory pressure is a possible
explanation, not a proven OOM cause. See the retained
[summary evidence](summary-2026-11-26/runtime-cache-evidence.json).
Each confirmed unload means the next inference may reload weights and rebuild
prompt state, adding latency. Short operations with at most two inference
responses retain only their final unload request. The complete candidate still
requires a fully live long-input measurement and meaning review.

Ollama model residency belongs to the daemon rather than to an individual client.
Another application using the same model shares its warm cache. Explicit unload
can therefore require that other application to reload the same model. Users who
share a daemon and need its existing retention policy can set
`LINKSCRIBE_OLLAMA_RETAIN_MODELS=1` in the LinkScribe process. This disables
both LinkScribe's intermediate and phase-end unload requests. This choice is
captured at operation entry so it cannot change midway through that operation.
It does not override the daemon's own memory management or promise that a model
will remain loaded. The resulting memory footprint must be assessed separately.

The QA wrapper additionally configures one loaded Ollama model and one parallel
request. These are QA daemon settings, not settings silently imposed on an
existing user daemon. All QA observers distinguish `kind: "inference"` from
`kind: "control"`, retaining both request/response traces. Control requests are
excluded from inference/map/synthesis counts and source-coverage checks.

## Scope of evidence

Pure regressions verify ordering, reuse, optional-dependency behavior, model
selection, failure preservation and observer classification. They use synthetic
model responses. They do not establish memory reduction, timing, translation
quality or summary accuracy. Those require the complete real workflow report.

The long-summary memory wrapper starts the actual summary evaluator as its
child and observes that process tree alongside the verified Ollama daemon. It
does not start a model service, replay responses, or alter requests. Atomic
checkpoints retain partial measurements on interruption. Available Linux host
and cgroup OOM counters are recorded before and after; unavailable counters are
explicit, and a counter increase alone cannot attribute an event to this run.

The current process-tree sampler includes the app and Ollama descendants, reports
concurrent RSS as an upper bound and complete Linux PSS separately, and states
its sampling limits. It excludes unrelated processes and OS/browser headroom.
A run on a larger host against a process budget is not a whole-machine test on
a smaller RAM configuration.

The [actual combined run](full-workflow-2026-11-26/README.md) on source
`a3b8652f9bbef4f065c9b90dd6ac6c3df3434100` processed a 34.635-second recording
through Small, public speakers, default Qwen translation and summary, SQLite and
exports in 59.202 seconds. Its 266 complete samples peaked at 4584.3 MiB
concurrent RSS and 4576.3 MiB PSS, below the selected 6144 MiB process budget.
The host had 9967.3 MiB RAM. Both phase-end unload replies completed, but this
does not establish an exact amount saved relative to a no-cleanup baseline.
That run preceded the two-response residency guard and does not validate its
effect on a long operation.
The same run failed translation/summary quality; resource success does not
approve those features or a v1.0 release.

Primary API references:

- [Python cache reference retention](https://docs.python.org/3/library/functools.html#functools.lru_cache)
- [CTranslate2 model memory management](https://opennmt.net/CTranslate2/memory.html)
- [Ollama chat unload request](https://github.com/ollama/ollama/blob/main/docs/api.md#unload-a-model-1)
- [Ollama model retention and concurrency](https://docs.ollama.com/faq)
- [llama.cpp server prompt-cache RAM setting](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

The installed runner's documented `LLAMA_ARG_CACHE_RAM=0` option can disable
its prompt cache when that runner starts. LinkScribe cannot reconfigure an
already-running, shared user daemon with this environment setting, so this
policy uses documented per-model unload requests instead. The application does
not silently set daemon-wide cache or concurrency options.
