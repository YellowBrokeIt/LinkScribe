# Small native validator build and zero-generation plan

**Prepared for review only. No acquisition into a build directory, compilation,
native grammar call, tokenizer call, model load or generation has run.**

The previous source-only preparation is unchanged and has an independent
source-level clearance. Its actual native enforcement is still untested. This
plan resolves the previously missing validator without rebuilding llama.cpp or
downloading any model or vocabulary.

## Reuse the actual retained parser

Read-only ELF inspection found every function used by the official validator in
the already verified runtime's `libllama.so.0.7.0`, including grammar
initialization, character acceptance, stack access, cleanup and UTF-8 conversion.
The parser library is 4,613,008 bytes, SHA-256
`75c36cc531f9c40453fe4f6d2961f365cc6c06c311cb31137fc232eaf68531bb`.
The exported string interfaces use the normal C++11 ABI.

The pinned `test-gbnf-validator.cpp` initializes that parser with a null model
vocabulary and checks characters directly. It does not load a model or call an
inference backend. We will compile this **unmodified** official program against
the **existing shared parser**. Its actual linking and behavior remain to be
tested; symbol inspection alone does not prove a successful build.

The Ollama compatibility patch at the pinned commit modifies only model-loading
and multimodal image-loading files, not these grammar headers or functions.
Exact patch and source identities are in `source-acquisition.json`.

## Exact minimal acquisition

The source allowlist contains 11 files, **289,300 bytes total**: the 3,402-byte
validator, nine headers forming its complete non-system include closure, and
the MIT license. Every path, byte count and Git blob identity is frozen at
llama.cpp commit `5320c87ff0d994845b44ce7976f10055ec697447` (`b11901`).

After separate authorization, acquire each allowlisted object once using its
immutable source URL or the official connector's exact pinned file content.
Retain the original directory layout and verify the exact byte count and Git
blob SHA-1, then record a SHA-256 manifest of the actual bytes. A truncated,
changed or unavailable object stops setup. No broad archive checkout, recursive
submodule acquisition, vocabulary GGUF, tokenizer asset, weights or runtime
package is required. No cache or existing experiment is deleted.

The isolated destination is
`/workspace/scratch/94360995dd61/linkscribe-grammar-validator-runtime`.
It does not exist as a built runtime yet. Sources, compiler temporary files,
binary, dependency file and logs stay below that owned directory.

## Exact build and dependencies

`build-command.json` records the complete proposed argument array. It invokes
the installed GCC **14.2.0** C++ compiler once, with C++17, `-O2`, no debug data,
`-march=x86-64`, `-mtune=generic`, and `_GLIBCXX_USE_CXX11_ABI=1`. It records the
actual header dependency list with `-MD -MF` and links the three pinned retained
core libraries using an explicit runtime search path.

This targets baseline x86-64 instructions for the new validator code, with no
`-march=native`, AVX-specific option, GPU target, CMake, package installation or
backend build. The resulting program is a local Linux x86-64 tool that depends
on the pinned shared runtime and system C++/C libraries; it is not a standalone
portable distribution. Existing runtime compatibility is a separate retained
fact, and the new link is not yet tested.

The actual compiler, `cc1plus`, assembler, linker, core shared libraries and
system C++/C dependency identities are in `retained-binary-metadata.json`.
The first guessed `cc1plus` location did not exist; the compiler's read-only
metadata query resolved its actual `/usr/libexec/...` path. The package database
had no matching entries, so this plan uses actual file hashes and compiler
metadata instead of assuming a package installation. No package was installed.

Use a small explicit environment: system tool path, UTF-8 locale, and an owned
temporary directory. Do not inherit compiler include/library override variables
or dynamic-loader injection variables. Do not modify `HOME` or shared runtime
files. The future controller must verify the frozen tool/library hashes before
compilation and preserve the exact command, environment allowlist, stdout,
stderr, exit status, elapsed time and resource samples.

After the one build, record the executable's SHA-256, ELF architecture, needed
libraries and runtime search path. Resolve the dependency graph with the system
dynamic loader's list mode, without running the program's main function, and
verify the retained core libraries and declared system dependencies. Bind every
actual header in the generated dependency file. Stop on a link error, missing
library, unexpected dependency or identity mismatch; do not alter flags or
silently try a full source build.

## Phase order and hard bounds

| Phase | CPU | Process-group RSS limit | Time limit | Disk/write limit |
| --- | ---: | ---: | ---: | --- |
| Acquire the 11 source objects | At most 4 | 256 MiB | 120 s total | Exactly 289,300 source bytes; no extra objects |
| Compile, inspect and run validator sanity controls | At most 4, one compile job | 512 MiB | 120 s total | 64 MiB total owned build tree; 16 MiB per file |
| Owned native zero-generation preflight | 4 | 6,144 MiB | 600 s total; 180 s initialization | Existing model cache reused; no import/copy/download |
| Validate the frozen emitted grammars | At most 4, sequential probes | 256 MiB | 60 s total; 2 s per probe | 64 KiB capture per validator process |

The aggregate planned ceiling is **900 seconds**, with the existing **1 GiB
free-disk reserve checked before and throughout each phase**. The latest source
planning observation is about 1.65 GB free; even the 64 MiB build ceiling leaves
the reserve. These are proposed stops, not measured build/runtime results.

The existing reviewed process-group observer and cleanup behavior should be
reused with these phase-specific limits, including surviving children after a
leader exits. No large model may run concurrently with the native preflight.
The model must be explicitly unloaded and its owned group stopped before the
standalone validation phase. No full model is resident during compilation or
validator-only controls.

## Validator sanity and status contract

Before trusting any candidate grammar, validate the tiny fixed grammar
`root ::= "ok"` with `ok` (accept), `no` (reject) and `o` (reject as incomplete).
The exact inputs and expected statuses are in `validator-sanity.json`; they
contain no names, translation sources or candidate answers.

The official CLI returns **zero for both accepted and rejected content**. The
prepared `status_contract.py` therefore requires the exact complete success
line for acceptance, or the exact first rejection line plus the documented
error/input structure for rejection. It never searches for the loose substring
`valid`. Unexpected stderr, process failure, ambiguous output, truncation or a
capture limit is an operational failure, not acceptance or semantic rejection.
Raw stdout/stderr and the full input/grammar hashes are retained for every
decision. This status helper has not been used to execute the native validator.

## Actual zero-generation converter and prompt gate

The six source-derived schemas and one deliberately unsupported sentinel remain
exactly the frozen `proposed-native-grammar-queries.json` from preparation.
Use the owned native server underlying the same pinned Ollama runtime to submit
each empty-prompt, zero-prediction request once and retain its actual returned
`generation_settings/grammar`. This is the path already used by Ollama's own
schema-grammar helper; no translated text is generated or evaluated by these
queries. Bind the owned native PID/port to the exact verified server binary.

For each real schema, require nonempty GBNF and the expected native grammar
backend. Preserve sanitized converter diagnostics and reject any unsupported
pattern warning or unrestricted-string fallback. The exact original-six
messages must also be rendered and token-counted with the same template,
4096 context, 2048 full output reserve plus terminal token, temperature zero,
non-thinking mode and four threads. All inputs remain complete and unchanged.

After unloading and cleanup, feed **all 285 frozen raw JSON probes** to the
corresponding emitted grammar and require every declared positive and negative
result. This tests actual tuple arity, per-entry marker ownership and
multiplicity, all allowed orders and serialized JSON gaps. The known
normalization-lookalike and meaning-loss probes stay explicit structural passes
that still require existing postguards or independent meaning review.

For the separately labelled unsupported-lookahead sentinel, either retain a
native converter error as closed rejection or demonstrate that the missing-tag
probe is accepted by its weakened grammar and therefore **rejected by the
enforcement gate**. The sentinel never becomes a translation profile. A failed
real grammar, probe mismatch, timeout or resource limit stops this stage with
all evidence retained. There is no schema revision or retry within this plan.

## Required artifacts and authorization boundary

Retain acquisition receipts and hashes; exact build/dependency/loader records;
validator sanity results; all actual schema requests, grammars and diagnostics;
complete native message renderings/token vectors; all 285 raw probe receipts;
sentinel gate result; full resource samples; explicit unload, empty resident
list and owned-process cleanup; and final manifest. An independent reviewer
must check the actual outputs and original frozen criteria/source binding.

This plan does not itself authorize acquiring/building the validator or starting
the native phase. A concrete controller adaptation and phase receipts must be
reviewed before execution. **No translation generation is authorized**, even
if these mechanical checks later pass. Pronouns, actor roles, omitted meaning
and the existing detector-boundary limitations remain outside a grammar's
guarantee; the original independent meaning criteria remain unchanged.

## Primary sources

- [Unmodified official validator](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/tests/test-gbnf-validator.cpp)
- [Pinned internal grammar API](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/src/llama-grammar.h)
- [Ollama's empty-prompt schema conversion route](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/llm/llama_server.go#L1480-L1540)
- [Ollama compatibility patch](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/llama/compat/001-llama-cpp-hooks.patch)

These sources were read only. The compatible parser exports were inspected as
ELF metadata; none was called. The previous frozen bundles remain unchanged.
