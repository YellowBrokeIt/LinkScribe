"""Pinned Krikri native preflight with only the full-summary input layout adapted.

No call occurs on import. The original native format/BOS/token/runner checks
are retained; see native-preflight-layout-only.patch for the exact difference.
"""
import hashlib
import re
from pathlib import Path
from context import common

def native_preflight(body, case, process, plan, header):
    if [m["role"] for m in body["messages"]] != ["system", "user"]:
        raise ValueError("Unexpected application message layout.")
    response = common.api("/api/chat", {**body, "_debug_render_only": True}, timeout=180)
    rendered = response.get("_debug_info", {}).get("rendered_template")
    if not isinstance(rendered, str) or response.get("eval_count", 0) or response.get("message", {}).get("content"):
        raise ValueError("Native render-only request did not return an answer-free prompt.")
    system, user = [m["content"] for m in body["messages"]]
    bos = "<|begin_of_text|>"
    prefix = "<|start_header_id|>system<|end_header_id|>\n\n"
    suffix = system + "<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n" + user + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    # Ollama may select its recognized native Llama format or the embedded
    # publisher Jinja. Both preserve the exact original two messages. Any
    # unknown wrapper stops setup and is retained for explicit review.
    layout = None
    for beginning in (bos, ""):
        if rendered == beginning + prefix + suffix:
            layout = "native_llama_headers"
        expected_start = beginning + prefix + "Cutting Knowledge Date: December 2023\nToday Date: "
        if rendered.startswith(expected_start):
            date, separator, tail = rendered[len(expected_start):].partition("\n\n")
            if re.fullmatch(r"\d{2} [A-Za-z]{3} \d{4}", date) and separator and tail == suffix:
                layout = "publisher_llama31_jinja_date_headers"
    if layout is None:
        raise ValueError("Actual native wrapper is not either declared source-preserving Llama format.")
    expected_excerpt = "\n".join(f"[{segment['start']:.1f}s] {segment['text']}" for segment in case["segments"])
    if user != expected_excerpt:
        raise ValueError("Actual summary request differs from the complete original timestamped excerpt.")
    runner = common.runner_identity(process)
    command = runner["command"]
    thread_flag = "-t" if "-t" in command else "--threads"
    if command[command.index(thread_flag) + 1] != "4":
        raise ValueError("Native runner does not use the fixed four CPU threads.")
    model_flag = "-m" if "-m" in command else "--model"
    if Path(command[command.index(model_flag) + 1]).resolve() != common.model_blob(Path(plan["storage"]["owned_runtime_directory"]), plan).resolve():
        raise ValueError("Native runner did not open the exact declared GGUF path.")
    if runner["executable_sha256"] != plan["runtime"]["files_sha256"]["lib/ollama/llama-server"]:
        raise ValueError("Actual native runner binary differs from the frozen runtime.")
    # The complete native Jinja rendering already contains its BOS; the
    # recognized Go format omits it and the native tokenizer supplies it.
    add_special = not rendered.startswith(bos)
    token_response = common.api("/tokenize", {"content": rendered, "add_special": add_special, "parse_special": True}, port=runner["port"])
    tokens = token_response.get("tokens")
    if (not isinstance(tokens, list) or not tokens or any(type(t) is not int for t in tokens)
            or tokens[0] != 128000 or tokens.count(128000) != 1 or len(tokens) + 2048 + 1 > 4096):
        raise ValueError("Full native prompt plus all 2048 possible response tokens does not fit.")
    return {"id": case["id"], "request": body, "debug_response": response, "rendered_prompt": rendered,
            "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(), "layout": layout,
            "tokenize_add_special": add_special, "tokens": tokens, "prompt_tokens": len(tokens),
            "maximum_output_tokens": 2048, "context_tokens": 4096,
            "unused_capacity_after_maximum_output": 4096 - len(tokens) - 2048,
            "one_bos_in_accounted_tokens": True, "complete_source_segments": len(case["segments"]),
            "runner": runner, "actual_generation_prompt_count_must_match": True}
