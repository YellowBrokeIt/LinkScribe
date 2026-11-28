"""Read the selected publisher GGUF and verify its actual native text contract.

No model responses, references or expected translations enter these checks.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from staging import HERE, common


def digest_json(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class HeaderReader:
    """Bounded little-endian GGUF metadata reader; never reads tensor payloads."""
    def __init__(self, stream):
        self.stream = stream

    def read(self, size):
        if size < 0 or self.stream.tell() + size > 64 * 1024 * 1024:
            raise ValueError("GGUF header exceeds the fixed 64 MiB inspection bound.")
        value = self.stream.read(size)
        if len(value) != size:
            raise ValueError("Truncated GGUF header.")
        return value

    def number(self, fmt):
        return struct.unpack("<" + fmt, self.read(struct.calcsize("<" + fmt)))[0]

    def string(self):
        return self.read(self.number("Q")).decode("utf-8")

    def value(self, kind, depth=0):
        formats = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
        if kind in formats:
            return self.number(formats[kind])
        if kind == 8:
            return self.string()
        if kind == 9 and depth < 2:
            item_kind, count = self.number("I"), self.number("Q")
            if count > 1000000:
                raise ValueError("Unexpectedly large metadata array.")
            return [self.value(item_kind, depth + 1) for _ in range(count)]
        raise ValueError("Unsupported or malformed GGUF metadata type.")


def inspect_header(blob, reference, plan):
    with blob.open("rb") as stream:
        reader = HeaderReader(stream)
        if reader.read(4) != b"GGUF":
            raise ValueError("Official payload has no GGUF magic.")
        version, tensor_count, metadata_count = reader.number("I"), reader.number("Q"), reader.number("Q")
        if version not in (2, 3) or tensor_count > 10000 or metadata_count > 1000:
            raise ValueError("Unsupported bounded GGUF header layout.")
        metadata = {}
        for _ in range(metadata_count):
            name = reader.string()
            if name in metadata:
                raise ValueError("Duplicate GGUF metadata key.")
            metadata[name] = reader.value(reader.number("I"))
        tensors = []
        for _ in range(tensor_count):
            name, dimensions = reader.string(), reader.number("I")
            if not 1 <= dimensions <= 4:
                raise ValueError("Unexpected tensor dimensionality.")
            shape = [reader.number("Q") for _ in range(dimensions)]
            tensors.append({"name": name, "shape": shape, "type": reader.number("I"), "offset": reader.number("Q")})
        inspected_bytes = stream.tell()
    publisher = json.loads(reference.read_text())
    vocabulary = publisher["model"]["vocab"]
    if set(vocabulary.values()) != set(range(plan["native_setup"]["expected_vocabulary_size"])):
        raise ValueError("Publisher vocabulary is not the exact complete expanded vocabulary.")
    ordered_tokens = [None] * len(vocabulary)
    for token, index in vocabulary.items():
        ordered_tokens[index] = token
    merges = [" ".join(value) if isinstance(value, list) else value for value in publisher["model"]["merges"]]
    tokens = metadata["tokenizer.ggml.tokens"]
    if tokens != ordered_tokens or metadata["tokenizer.ggml.merges"] != merges:
        raise ValueError("Actual GGUF tokenizer/merge order differs from the complete publisher tokenizer.")
    template = metadata.get("tokenizer.chat_template", "")
    if hashlib.sha256(template.encode()).hexdigest() != plan["native_setup"]["expected_template_sha256"]:
        raise ValueError("Actual selected Q4 embedded template differs from the publisher template.")
    fixed = {"general.architecture": "llama", "llama.block_count": 32, "llama.embedding_length": 4096,
             "llama.attention.head_count": 32, "llama.attention.head_count_kv": 8,
             "llama.context_length": 131072, "tokenizer.ggml.bos_token_id": 128000}
    if any(metadata.get(k) != v for k, v in fixed.items()):
        raise ValueError("Actual selected Q4 architecture or BOS differs from the pinned native model.")
    generation = json.loads((HERE / "publisher-generation_config.json").read_text())
    if metadata.get("tokenizer.ggml.eos_token_id") not in generation["eos_token_id"]:
        raise ValueError("Native EOS is not a publisher-declared end token.")
    if any(tokens[index] != token for index, token in {128000: "<|begin_of_text|>", 128001: "<|end_of_text|>",
                                                      128008: "<|eom_id|>", 128009: "<|eot_id|>"}.items()):
        raise ValueError("Native special token identities changed.")
    parameters = sum(math.prod(t["shape"]) for t in tensors)
    if parameters != 8202227776:
        raise ValueError("Selected native tensor dimensions do not match the publisher parameter count.")
    arrays = {k: {"count": len(v), "sha256_canonical_json": digest_json(v)} for k, v in metadata.items() if isinstance(v, list)}
    scalars = {k: v for k, v in metadata.items() if not isinstance(v, list) and k != "tokenizer.chat_template"}
    return {"version": version, "tensor_count": tensor_count, "metadata_count": metadata_count,
            "header_bytes_inspected": inspected_bytes, "tensor_parameters": parameters,
            "tensor_descriptors_sha256": digest_json(tensors), "metadata_scalars": scalars,
            "metadata_arrays": arrays, "template": template, "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
            "publisher_tokenizer_sha256": common.sha(reference), "complete_vocabulary_equal": True,
            "complete_ordered_merges_equal": True, "all_publisher_added_token_ids_equal": all(tokens[t["id"]] == t["content"] for t in publisher["added_tokens"]),
            "generation_eos_ids": generation["eos_token_id"], "no_tensor_payload_read": True}


def cache_identity(runtime, plan):
    name, tag = plan["model"]["local_name"].split(":")
    manifest_path = runtime / "models/manifests-v2/ollama.com/library" / name / tag
    manifest = json.loads(manifest_path.read_text())
    descriptors = [manifest["config"], *manifest["layers"]]
    content = {}
    for item in descriptors:
        path = runtime / "models/blobs" / item["digest"].replace(":", "-")
        if path.is_symlink() or path.stat().st_size != item["size"] or common.sha(path) != item["digest"].split(":", 1)[1]:
            raise ValueError("Imported descriptor fails exact size/full SHA256 verification.")
        if item["mediaType"] != "application/vnd.ollama.image.model":
            content[item["mediaType"]] = path.read_text()
    models = [x for x in manifest["layers"] if x["mediaType"] == "application/vnd.ollama.image.model"]
    if len(models) != 1 or models[0]["digest"] != "sha256:" + plan["model"]["sha256"]:
        raise ValueError("Native package is not exactly the single selected text GGUF.")
    forbidden = {"application/vnd.ollama.image.projector", "application/vnd.ollama.image.draft", "application/vnd.ollama.image.system"}
    if any(x["mediaType"] in forbidden for x in manifest["layers"]):
        raise ValueError("Unrequested persona/projector/draft in imported package.")
    params = json.loads(content.get("application/vnd.ollama.image.params", "{}"))
    if params != plan["native_setup"]["import_parameters"]:
        raise ValueError("Native import parameters do not match fixed context/stops/sampling.")
    return {"manifest_sha256": common.sha(manifest_path), "manifest": manifest,
            "descriptor_text": content, "all_descriptor_bytes_verified": True,
            "system_persona_projector_draft_absent": True}


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
    rows = json.loads(user.split("JSON input: ", 1)[1])
    if rows != [{"id": i, "text": s["text"]} for i, s in enumerate(case["segments"])]:
        raise ValueError("Actual request does not contain every complete original source segment.")
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
