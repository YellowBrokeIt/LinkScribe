# Krikri v1.5 format supplement

**No official public v1.5 GGUF was found in this bounded metadata check.** The ILSP Krikri repository API returned nine repositories without a pagination link. Its only GGUF repository is the original `Llama-Krikri-8B-Instruct-GGUF`. Neither v1.5 repository lists a GGUF file.

| Official release | Immutable revision | Observed weight package | Published bytes |
|---|---|---|---:|
| [Llama-Krikri-8B-Instruct-v1.5](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct-v1.5/tree/326e2c0ea90d771c19fcf06225fe87dc922b51b2) | `326e2c0ea90d771c19fcf06225fe87dc922b51b2` | Four full safetensors shards | 16,404,489,288 |
| [Llama-Krikri-8B-Instruct-v1.5-4bit-mlx](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct-v1.5-4bit-mlx/tree/140ab6af4203751d7f91896e6d534f11a1e1863d) | `140ab6af4203751d7f91896e6d534f11a1e1863d` | One 4-bit MLX safetensors package | 4,614,220,690 |

Both are public and ungated, declared `llama3.1`. The [v1.5 card](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct-v1.5/blob/326e2c0ea90d771c19fcf06225fe87dc922b51b2/README.md) describes a chat-focused alternative. All four full-weight shard hashes differ from the original Instruct release, so v1.5 is a genuinely separate checkpoint. The official MLX card identifies the MLX format; it is not a native GGUF package for the current Linux/Ollama screen.

The earlier finding remains narrowly correct: updates within the **original** Instruct repository were documentation-only, and its official Q4 object is unchanged. That finding did not establish that ILSP had no separately named newer checkpoint. This supplement records that distinction without rewriting the frozen earlier audit.

The original-Q4 six-case experiment and its source/criteria remain unchanged. Any result from it applies to that checkpoint, not to v1.5. No weights were downloaded, converted, loaded or run for this supplement. Public metadata can change; the exact returned inventory and immutable file identities are retained beside this note.
