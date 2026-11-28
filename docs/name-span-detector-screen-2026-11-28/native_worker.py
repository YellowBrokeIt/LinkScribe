"""Zero-forward token preparation or one fixed six-source native PERSON screen."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import struct
import sys
import time
from types import SimpleNamespace
import warnings

from common import HERE, RESEARCH, PLAN_SHA256, emit, model_files, read_plan, save, sha, utc, verify_freeze


def no_network(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
        raise RuntimeError("Offline detector worker attempted network access.")


def package_identity(plan):
    expected = {name: value["version"] for name, value in plan["runtime"]["existing_packages"].items() if value}
    expected.update({item["package"]: item["version"] for item in plan["runtime"]["new_wheels"]})
    result = {}
    for name, version in expected.items():
        distribution = metadata.distribution(name)
        if distribution.version != version:
            raise ValueError("Package version differs from the frozen runtime: " + name)
        result[name] = {"version": version,
                        "metadata_sha256": hashlib.sha256((distribution.read_text("METADATA") or "").encode()).hexdigest(),
                        "record_sha256": hashlib.sha256((distribution.read_text("RECORD") or "").encode()).hexdigest()}
        previous = plan["runtime"]["existing_packages"].get(name)
        if previous and (result[name]["metadata_sha256"] != previous["metadata_sha256"]
                         or result[name]["record_sha256"] != previous["record_sha256"]):
            raise ValueError("A reused read-only dependency changed: " + name)
    for name in ("flashdeberta", "llm2vec", "peft", "turbot5"):
        if importlib.util.find_spec(name) is not None:
            raise ValueError("An optional architecture replacement is unexpectedly installed: " + name)
    root = Path(plan["runtime"]["owned_package_target"]) / "gliner"
    source_mapping = {"model.py": "gliner-code-model.py", "config.py": "gliner-code-config.py",
                      "data_processing/tokenizer.py": "gliner-code-tokenizer.py",
                      "data_processing/processor.py": "gliner-code-processor.py",
                      "modeling/encoder.py": "gliner-code-encoder.py"}
    source_hashes = {}
    for relative, evidence in source_mapping.items():
        observed = sha(root / relative)
        if observed != sha(RESEARCH / evidence):
            raise ValueError("Installed native source differs from the audited pinned source: " + relative)
        source_hashes[relative] = observed
    return {"packages": result, "audited_native_source_sha256": source_hashes,
            "optional_architecture_replacements_absent": True}


def source_cases(plan):
    path = RESEARCH / plan["input"]["worker_input"]
    if sha(path) != plan["input"]["worker_input_sha256"]:
        raise ValueError("The exact source-only input changed.")
    corpus = json.loads(path.read_text())
    if set(corpus) != {"schema_version", "cases"} or corpus["schema_version"] != 1:
        raise ValueError("Unexpected source-only snapshot schema.")
    cases = corpus["cases"]
    if [case["id"] for case in cases] != plan["input"]["case_order"] or len(cases) != 6:
        raise ValueError("The six original cases or their order changed.")
    for case in cases:
        if set(case) != set(plan["input"]["allowed_case_fields"]):
            raise ValueError("A reference or unapproved field entered the source-only case.")
        if len(case["segments"]) != 2 or not all(isinstance(x["text"], str) and x["text"] for x in case["segments"]):
            raise ValueError("Original source segment count/text changed.")
    return cases


def source_text(case):
    text = "\n".join(segment["text"] for segment in case["segments"])
    cursor = 0
    offsets = []
    for index, segment in enumerate(case["segments"]):
        end = cursor + len(segment["text"])
        if text[cursor:end] != segment["text"]:
            raise ValueError("Original source segment reconstruction failed.")
        offsets.append({"segment_index": index, "start": cursor, "end": end})
        cursor = end + 1
    return text, offsets


def preflight(processor, case, collator_class):
    text, segments = source_text(case)
    split = list(processor.words_splitter(text))
    reference = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\w+(?:[-_]\w+)*|\S", text)]
    if split != reference or not split or len(split) > 384:
        raise ValueError("Native full-source words differ, are empty or exceed the 384-word cap.")
    words = [item[0] for item in split]
    if any(text[start:end] != word for word, start, end in split):
        raise ValueError("Native source word offsets are not exact slices.")
    covered = {position for _, start, end in split for position in range(start, end)}
    if any(not character.isspace() and index not in covered for index, character in enumerate(text)):
        raise ValueError("A nonwhitespace source character was omitted from the native words.")
    inputs, prompt_lengths = processor.prepare_inputs([words], ["person"])
    if inputs != [[processor.ent_token, "person", processor.sep_token] + words] or prompt_lengths != [3]:
        raise ValueError("Native entity prefix or complete source word sequence changed.")
    encoded = processor.transformer_tokenizer(inputs, is_split_into_words=True, return_tensors="pt",
                                               truncation=False, padding="longest")
    if encoded["input_ids"].shape[0] != 1 or encoded["input_ids"].shape[1] > 512:
        raise ValueError("The complete source/prefix exceeds 512 encoded tokens.")
    word_ids = encoded.word_ids(batch_index=0)
    source_word_ids = {index - 3 for index in word_ids if index is not None and index >= 3}
    if source_word_ids != set(range(len(words))):
        raise ValueError("Full uncropped encoding does not represent every original source word.")
    mask = processor.prepare_word_mask([words], encoded, prompt_lengths)
    if {number for number in mask[0] if number > 0} != set(range(1, len(words) + 1)):
        raise ValueError("The native word mask omits a full-source word.")
    arrays = {key: value.tolist() for key, value in encoded.items()}
    arrays["words_mask"] = mask
    # Exercise the exact native collator without constructing a model. This
    # verifies the real shared label-map contract and native truncation path.
    collator = collator_class(processor.config, data_processor=processor, return_tokens=True,
                              return_entities=True, return_id_to_classes=True, prepare_labels=False)
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*truncat.*", category=Warning)
        collated = collator([{"tokenized_text": words, "ner": None}], entity_types=["person"])
    actual_arrays = {key: collated[key].detach().cpu().tolist()
                     for key in ("input_ids", "attention_mask", "words_mask", "text_lengths")}
    if (any(actual_arrays[key] != arrays[key] for key in ("input_ids", "attention_mask", "words_mask"))
            or actual_arrays["text_lengths"] != [[len(words)]] or collated.get("tokens") != [words]
            or collated.get("id_to_classes") != {1: "person"}):
        raise ValueError("Actual zero-forward native collation differs from the complete fixed-label source.")
    return {"id": case["id"], "source_language": case["source_language"],
            "source_segments": copy.deepcopy(case["segments"]), "source_text": text,
            "source_text_sha256": hashlib.sha256(text.encode()).hexdigest(), "segment_offsets": segments,
            "native_words": [{"text": word, "start": start, "end": end} for word, start, end in split],
            "source_word_count": len(words), "entity_labels": ["person"], "native_input_words": inputs,
            "prompt_word_count": 3, "encoded_token_count": len(arrays["input_ids"][0]),
            "word_ids": word_ids, "arrays": arrays, "truncation": False,
            "native_collator": {"class": collator_class.__name__, "arrays": actual_arrays,
                                "shared_class_mapping": {"1": "person"}, "source_tokens": [words]},
            "all_original_source_words_represented": True}


def tokenizer_identity(tokenizer):
    vocabulary = json.dumps(tokenizer.get_vocab(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"class": type(tokenizer).__module__ + "." + type(tokenizer).__name__,
            "is_fast": tokenizer.is_fast, "vocabulary_size": len(tokenizer),
            "vocabulary_sha256": hashlib.sha256(vocabulary.encode()).hexdigest(),
            "special_tokens_map": tokenizer.special_tokens_map, "all_special_ids": tokenizer.all_special_ids,
            "model_max_length": tokenizer.model_max_length}


def header_identity(path):
    with path.open("rb") as stream:
        header_length = struct.unpack("<Q", stream.read(8))[0]
        if header_length > 8 * 1024 * 1024:
            raise ValueError("Unexpected safetensors header size.")
        raw = stream.read(header_length)
    header = json.loads(raw)
    tensors = {name: value for name, value in header.items() if name != "__metadata__"}
    if not tensors or any(value["dtype"] != "F32" for value in tensors.values()):
        raise ValueError("The selected checkpoint is not the declared F32 payload.")
    elements = sum(math.prod(value["shape"]) for value in tensors.values())
    if elements != 288949504:
        raise ValueError("Checkpoint tensor inventory differs from official metadata.")
    return {"header_bytes": header_length, "header_sha256": hashlib.sha256(raw).hexdigest(),
            "tensor_count": len(tensors), "f32_elements": elements,
            "tensors": tensors, "metadata": header.get("__metadata__", {})}


def validate_entities(raw, prepared):
    import regex
    text = prepared["source_text"]
    boundaries = {0, len(text)}
    for match in regex.finditer(r"\X", text):
        boundaries.add(match.start())
        boundaries.add(match.end())
    if not isinstance(raw, list):
        raise ValueError("Native entity result is not a list.")
    mapped = []
    for entity in raw:
        if not isinstance(entity, dict) or set(entity) != {"start", "end", "text", "label", "score"}:
            raise ValueError("Unexpected native span schema.")
        start, end, score = entity["start"], entity["end"], entity["score"]
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
                or start not in boundaries or end not in boundaries or entity["text"] != text[start:end]
                or entity["label"] != "person" or type(score) not in {int, float}
                or not math.isfinite(score) or not 0.5 <= score <= 1):
            raise ValueError("Native span offset/text/label/score integrity failed.")
        parents = [segment for segment in prepared["segment_offsets"]
                   if segment["start"] <= start and end <= segment["end"]]
        if len(parents) != 1:
            raise ValueError("Predicted person crosses an original segment boundary.")
        parent = parents[0]
        mapped.append({**entity, "segment_index": parent["segment_index"],
                       "segment_start": start - parent["start"], "segment_end": end - parent["start"]})
    ordered = sorted(mapped, key=lambda value: (value["start"], value["end"]))
    if any(left["end"] > right["start"] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("Native flat spans overlap.")
    return ordered


def prepare(plan, directory, packages, cases, report):
    from gliner.config import GLiNERConfig
    from gliner.model import GLiNER, BaseGLiNER
    from transformers import AutoTokenizer
    config = GLiNERConfig(**json.loads((directory / "gliner_config.json").read_text()))
    chosen = GLiNER._get_gliner_class(config)
    if chosen.__name__ != "UniEncoderSpanGLiNER" or chosen._get_special_tokens is not BaseGLiNER._get_special_tokens:
        raise ValueError("Unexpected native model/special-token class.")
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    tokens = BaseGLiNER._get_special_tokens(SimpleNamespace(config=config))
    if config.class_token_index != -1 or config.vocab_size != -1:
        raise ValueError("Unexpected checkpoint special-token initialization policy.")
    tokenizer.add_tokens(tokens, special_tokens=True)
    processor = chosen.data_processor_class(config, tokenizer, None)
    if type(config.encoder_config).__name__ != "DebertaV2Config" or config.encoder_config.max_position_embeddings != 512:
        raise ValueError("Unexpected native backbone configuration.")
    report.update({"packages": packages, "checkpoint": header_identity(directory / "model.safetensors"),
                   "model_class": chosen.__name__, "tokenizer": tokenizer_identity(tokenizer),
                   "native_added_tokens": tokens,
                   "sources": [preflight(processor, case, chosen.data_collator_class) for case in cases],
                   "model_initialized": False, "detector_forwards": 0, "translation_calls": 0,
                   "offline_network_audit_enforced": True, "complete": True})


def infer(plan, directory, packages, cases, report):
    import torch
    from gliner import GLiNER
    setup = json.loads((HERE / "prepare.json").read_text())
    if not setup["complete"] or setup["packages"] != packages:
        raise ValueError("Measured preflight/dependency identity changed.")
    original_loader = torch.nn.Module.load_state_dict
    load_records = []

    def bound_loader(module, state_dict, strict=True, *args, **kwargs):
        if strict is not True:
            raise ValueError("Native checkpoint loader did not request strict state loading.")
        result = original_loader(module, state_dict, strict=strict, *args, **kwargs)
        load_records.append({"class": type(module).__name__, "strict": strict,
                             "state_key_count": len(state_dict), "missing_keys": list(result.missing_keys),
                             "unexpected_keys": list(result.unexpected_keys)})
        return result

    torch.nn.Module.load_state_dict = bound_loader
    try:
        model = GLiNER.from_pretrained(str(directory), local_files_only=True, map_location="cpu", strict=True,
                                      load_tokenizer=True, resize_token_embeddings=True,
                                      compile_torch_model=False, load_onnx_model=False)
    finally:
        torch.nn.Module.load_state_dict = original_loader
    if len(load_records) != 1 or load_records[0]["missing_keys"] or load_records[0]["unexpected_keys"]:
        raise ValueError("Expected one complete strict native checkpoint load.")
    backbone = model.model.token_rep_layer.bert_layer.model
    if type(backbone).__module__ != "transformers.models.deberta_v2.modeling_deberta_v2" or type(backbone).__name__ != "DebertaV2Model":
        raise ValueError("The actual encoder is not the audited standard DebertaV2Model.")
    if model._inference_packing_config is not None or model.onnx_model or model.training:
        raise ValueError("Native execution mode differs from the frozen profile.")
    if (tokenizer_identity(model.data_processor.transformer_tokenizer) != setup["tokenizer"]
            or model.config.max_len != 384 or model.config.max_width != 12
            or any(value.dtype != torch.float32 or value.device.type != "cpu" for value in model.parameters())):
        raise ValueError("Actual tokenizer/limit/dtype/device identity changed.")
    report["initialization"] = {"strict_load_records": load_records,
                                "backbone_class": type(backbone).__module__ + "." + type(backbone).__name__,
                                "parameter_count": sum(value.numel() for value in model.parameters()),
                                "dtype": "float32", "device": "cpu", "torch_threads": torch.get_num_threads(),
                                "torch_interop_threads": torch.get_num_interop_threads(),
                                "offline_network_audit_enforced": True}
    save(HERE / "execution.json", report)
    emit("initialized")
    for case, expected in zip(cases, setup["sources"]):
        started = time.monotonic()
        emit("case_start", id=case["id"])
        output = HERE / (case["id"] + ".json")
        if output.exists():
            raise ValueError("Refusing to repeat an original detector case.")
        prepared = preflight(model.data_processor, case, model.data_collator_class)
        if prepared != expected:
            raise ValueError("Actual full-source preflight differs from its independent-review freeze.")
        result = {"schema_version": 1, "complete": False, "started_at": utc(), "id": case["id"],
                  "plan_sha256": PLAN_SHA256, "inference_freeze_sha256": sha(HERE / "inference-freeze.json"),
                  "source": prepared, "profile": plan["native_detection_profile"],
                  "raw_entities": None, "detector_calls": 0, "forward_observations": [],
                  "semantic_quality": "unreviewed", "translation_calls": 0}
        save(output, result)
        words = [item["text"] for item in prepared["native_words"]]
        source_before = copy.deepcopy(case)

        def top_hook(module, args, kwargs):
            observed = {key: kwargs[key].detach().cpu().tolist() if key in kwargs else None
                        for key in ("input_ids", "attention_mask", "words_mask", "text_lengths")}
            result["forward_observations"].append({"stage": "native_span_model", **observed,
                                                    "tokens": kwargs.get("tokens"),
                                                    "class_mapping": kwargs.get("id_to_classes"),
                                                    "class_mapping_type": type(kwargs.get("id_to_classes")).__name__})
            save(output, result)  # Retain actual inputs even when the following guard rejects them.
            if any(observed[key] != prepared["arrays"][key] for key in ("input_ids", "attention_mask", "words_mask")):
                raise ValueError("Actual native model tensors differ from the complete uncropped preflight.")
            if kwargs.get("tokens") != [words] or observed["text_lengths"] != [[len(words)]]:
                raise ValueError("Actual model source words were changed or truncated.")
            if kwargs.get("id_to_classes") != {1: "person"}:
                raise ValueError("Actual entity class mapping changed.")

        def encoder_hook(module, args, kwargs):
            ids = kwargs.get("input_ids", args[0] if args else None)
            mask = kwargs.get("attention_mask")
            observed = {"input_ids": ids.detach().cpu().tolist() if ids is not None else None,
                        "attention_mask": mask.detach().cpu().tolist() if mask is not None else None}
            result["forward_observations"].append({"stage": "actual_deberta_encoder", **observed})
            save(output, result)
            if ids is None or mask is None:
                raise ValueError("Cannot observe the actual encoder input and attention mask.")
            if any(observed[key] != prepared["arrays"][key] for key in observed):
                raise ValueError("Actual encoder input differs from the full native preflight.")

        handles = [model.model.register_forward_pre_hook(top_hook, with_kwargs=True),
                   backbone.register_forward_pre_hook(encoder_hook, with_kwargs=True)]
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("error", message=".*truncat.*", category=Warning)
                with torch.inference_mode():
                    result["detector_calls"] = 1
                    result["raw_entities"] = model.predict_entities(prepared["source_text"], labels=["person"],
                                                                   flat_ner=True, threshold=0.5, multi_label=False,
                                                                   batch_size=1, packing_config=None)
            save(output, result)  # Preserve unmodified native output before validation.
            if [item["stage"] for item in result["forward_observations"]] != ["native_span_model", "actual_deberta_encoder"]:
                raise ValueError("Expected exactly one bound model and encoder forward.")
            result["validated_source_spans"] = validate_entities(result["raw_entities"], prepared)
            if case != source_before:
                raise ValueError("Original source text or metadata changed.")
            result["complete"] = True
        except BaseException as error:
            result["error"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            for handle in handles:
                handle.remove()
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            result["finished_at"] = utc()
            save(output, result)
        report["cases"].append({"id": case["id"], "report": output.name, "sha256": sha(output),
                                 "complete": result["complete"], "detector_calls": result["detector_calls"]})
        save(HERE / "execution.json", report)
        emit("case_complete" if result["complete"] else "case_failed", id=case["id"], report=str(output), sha256=sha(output))
        if not result["complete"]:
            raise ValueError("The first structural/execution failure stops the fixed detector profile.")
    report["complete"] = len(report["cases"]) == 6 and all(value["complete"] for value in report["cases"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "infer"), required=True)
    args = parser.parse_args()
    plan = read_plan()
    verify_freeze("setup-freeze" if args.phase == "prepare" else "inference-freeze")
    output = HERE / ("prepare.json" if args.phase == "prepare" else "execution.json")
    if output.exists():
        raise ValueError("Refusing to overwrite a retained worker phase.")
    report = {"schema_version": 1, "started_at": utc(), "phase": args.phase, "complete": False,
              "plan_sha256": PLAN_SHA256, "cases": [], "translation_calls": 0,
              "semantic_quality": "unreviewed", "original_source_only": True}
    save(output, report)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Owned supervisor stop.")))
    started = time.monotonic()
    try:
        if not sys.dont_write_bytecode:
            raise ValueError("Read-only reused dependencies require bytecode writes to be disabled.")
        sys.addaudithook(no_network)
        packages = package_identity(plan)
        directory, identities = model_files(plan)
        report["actual_model_files_sha256"] = identities
        cases = source_cases(plan)
        import torch
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        if torch.get_num_threads() != 4 or torch.get_num_interop_threads() != 1 or len(os.sched_getaffinity(0)) > 4:
            raise ValueError("Actual CPU controls differ from the fixed four-thread limit.")
        if args.phase == "prepare":
            prepare(plan, directory, packages, cases, report)
        else:
            infer(plan, directory, packages, cases, report)
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        report["complete"] = False
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["finished_at"] = utc()
        save(output, report)
    emit("phase_complete", phase=args.phase, complete=report["complete"], report=str(output))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
