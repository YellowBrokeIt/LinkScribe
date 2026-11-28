#!/usr/bin/env python3
"""Isolated M2M100 conversion and native translation; no production integration."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from prepare_source import save, sha
from evaluate_translation_quality import read_corpus, structural_checks, review_flags


def utc():
    return datetime.now(timezone.utc).isoformat()


def emit(event, **values):
    print("M2M_EVENT " + json.dumps({"event": event, **values}), flush=True)


def tokenize_cases(tokenizer, corpus, plan):
    cases = []
    for case in corpus["cases"]:
        tokenizer.src_lang = case["source_language"]
        source_marker = tokenizer.lang_code_to_token[case["source_language"]]
        target_marker = tokenizer.lang_code_to_token[case["target_language"]]
        sources = []
        for segment in case["segments"]:
            ids = tokenizer.encode(segment["text"], add_special_tokens=True, truncation=False)
            tokens = tokenizer.convert_ids_to_tokens(ids)
            if (not tokens or len(tokens) > plan["protocol"]["max_source_tokens"]
                    or tokens[0] != source_marker or tokens[-1] != tokenizer.eos_token
                    or tokenizer.unk_token_id in ids):
                raise ValueError("Source tokenization is incomplete, unsupported, or outside the frozen bound.")
            sources.append({"text": segment["text"], "token_ids": ids, "tokens": tokens,
                            "source_language_token": source_marker,
                            "source_language_token_id": tokenizer.get_lang_id(case["source_language"]),
                            "target_prefix": [target_marker],
                            "target_language_token_id": tokenizer.get_lang_id(case["target_language"])})
        cases.append({"id": case["id"], "source_language": case["source_language"],
                      "target_language": case["target_language"], "segments": sources})
    return {"schema_version": 1, "case_ids": [case["id"] for case in cases],
            "case_count": len(cases), "tokenizer_class": type(tokenizer).__name__,
            "eos_token": tokenizer.eos_token, "eos_token_id": tokenizer.eos_token_id,
            "source_truncation": False, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("convert", "infer"), required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    plan = json.loads((HERE / "plan.json").read_text())
    if sha(HERE / "plan.json") != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("The predeclared plan changed.")
    for name, expected in plan["versions"].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError("Unexpected isolated package version: " + name)
    import torch
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    import ctranslate2
    from transformers import AutoTokenizer
    corpus = read_corpus(HERE / "development-cases.json")
    if ([case["id"] for case in corpus["cases"]] != plan["evaluation"]["case_ids"]
            or any(case["split"] != "development" for case in corpus["cases"])):
        raise ValueError("Only the exact six exposed development cases are authorized.")
    source = runtime / "source"
    converted = runtime / "converted-float32"
    tokenizer = AutoTokenizer.from_pretrained(str(source), local_files_only=True,
                                               trust_remote_code=False, use_fast=False)
    tokenized = tokenize_cases(tokenizer, corpus, plan)
    if args.phase == "convert":
        if converted.exists() or (HERE / "converted-identity.json").exists():
            raise ValueError("Refusing to overwrite a converted model or conversion evidence.")
        from ctranslate2.converters import TransformersConverter
        emit("conversion_start")
        converter = TransformersConverter(str(source), load_as_float16=False,
                                          low_cpu_mem_usage=True, trust_remote_code=False)
        converter.convert(str(converted), quantization="float32")
        files = {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)}
                 for path in sorted(converted.iterdir()) if path.is_file()}
        identity = {"complete": True, "created_at": utc(), "inference_calls": 0,
                    "plan_sha256": sha(HERE / "plan.json"), "model": plan["model"],
                    "quantization": "float32", "load_as_float16": False,
                    "low_cpu_mem_usage": True, "trust_remote_code": False,
                    "versions": plan["versions"], "files": files}
        save(HERE / "source-tokenization.json", tokenized)
        identity["source_tokenization_sha256"] = sha(HERE / "source-tokenization.json")
        save(HERE / "converted-identity.json", identity)
        emit("conversion_complete", files=len(files), bytes=sum(item["bytes"] for item in files.values()))
        return 0

    freeze = json.loads((HERE / "inference-freeze.json").read_text())
    if (sha(HERE / "inference-freeze.json") != (HERE / "inference-freeze.sha256").read_text().strip()
            or freeze["plan_sha256"] != sha(HERE / "plan.json")
            or sha(HERE / "source-tokenization.json") != freeze["source_tokenization_sha256"]
            or tokenized != json.loads((HERE / "source-tokenization.json").read_text())):
        raise ValueError("Inference identities or full source tokens differ from the pre-inference freeze.")
    output = HERE / "development.json"
    if output.exists() or any((HERE / (case["id"] + ".json")).exists() for case in corpus["cases"]):
        raise ValueError("Refusing to overwrite previous actual outputs.")
    report = {"schema_version": 1, "started_at": utc(), "complete": False,
              "evidence_type": "actual_native_m2m100_translation_not_production_integration",
              "semantic_quality": "unreviewed", "plan_sha256": sha(HERE / "plan.json"),
              "inference_freeze_sha256": sha(HERE / "inference-freeze.json"),
              "model": plan["model"], "versions": plan["versions"], "cases": []}
    save(output, report)
    translator = None
    try:
        translator = ctranslate2.Translator(str(converted), device="cpu", compute_type="float32",
                                            inter_threads=1, intra_threads=4, max_queued_batches=1)
        report["native_runtime"] = {"device": translator.device, "compute_type": translator.compute_type,
                                    "num_translators": translator.num_translators,
                                    "torch_threads": torch.get_num_threads(),
                                    "torch_interop_threads": torch.get_num_interop_threads()}
        if (translator.device != "cpu" or translator.compute_type != "float32"
                or translator.num_translators != 1):
            raise ValueError("Native runtime did not honor the frozen CPU/float32 profile.")
        options = plan["protocol"]["translate_batch_options"]
        for case, encoded in zip(corpus["cases"], tokenized["cases"]):
            result = {**copy.deepcopy(case), "complete": False, "semantic_quality": "unreviewed",
                      "translation": None, "structural_checks": {}, "review_flags": [],
                      "native_request": {"source": [item["tokens"] for item in encoded["segments"]],
                                         "target_prefix": [item["target_prefix"] for item in encoded["segments"]],
                                         "source_texts": [item["text"] for item in encoded["segments"]],
                                         "options": copy.deepcopy(options)},
                      "raw_response_available": False, "started_at": utc()}
            report["cases"].append(result)
            case_output = HERE / (case["id"] + ".json")

            def checkpoint():
                save(case_output, {"schema_version": 1, "complete": result["complete"],
                                   "semantic_quality": "unreviewed", "model": plan["model"],
                                   "plan_sha256": report["plan_sha256"],
                                   "inference_freeze_sha256": report["inference_freeze_sha256"],
                                   "cases": [result]})
                save(output, report)

            checkpoint()
            emit("case_start", case_id=case["id"])
            started = time.monotonic()
            before = copy.deepcopy(case["segments"])
            try:
                answers = translator.translate_batch(result["native_request"]["source"],
                                                      target_prefix=result["native_request"]["target_prefix"],
                                                      **options)
                result["raw_response"] = [{"hypotheses": answer.hypotheses, "scores": answer.scores}
                                          for answer in answers]
                result["raw_response_available"] = True
                checkpoint()  # Preserve unmodified token output before any acceptance decision.
                if len(answers) != len(case["segments"]):
                    raise ValueError("Native output count differs from the full source segment count.")
                translated = []
                completion = []
                for segment, source_tokens, answer in zip(case["segments"], encoded["segments"], answers):
                    if len(answer.hypotheses) != 1 or len(answer.scores) != 1 or not math.isfinite(answer.scores[0]):
                        raise ValueError("Expected one finite-scored native hypothesis per source segment.")
                    hypothesis = answer.hypotheses[0]
                    prefix = source_tokens["target_prefix"][0]
                    checks = {"target_language_prefix": bool(hypothesis) and hypothesis[0] == prefix,
                              "actual_end_token": bool(hypothesis) and hypothesis[-1] == tokenizer.eos_token,
                              "strictly_below_length_cap": len(hypothesis) < options["max_decoding_length"],
                              "nonempty_content_tokens": len(hypothesis) > 2,
                              "no_unexpected_special_content_tokens": not any(token in tokenizer.all_special_tokens
                                                                               for token in hypothesis[1:-1])}
                    completion.append(checks)
                    result["completion_checks"] = completion
                    if not all(checks.values()):
                        raise ValueError("Native output is incomplete, length-limited, or contains unexpected special tokens.")
                    ids = tokenizer.convert_tokens_to_ids(hypothesis[1:-1])
                    text = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
                    if not text.strip() or len(text.encode("utf-8")) > plan["protocol"]["max_output_bytes"]:
                        raise ValueError("Native translated text is empty or exceeds the output bound.")
                    translated.append({**segment, "text": text.strip()})
                result["translation"] = translated
                result["structural_checks"] = structural_checks(before, case["segments"], translated)
                if not all(result["structural_checks"].values()):
                    raise ValueError("Source text/metadata or output structure failed preservation checks.")
                result["review_flags"] = review_flags(case, translated)
                result["automatic_status"] = "review" if result["review_flags"] else "pass"
                result["complete"] = True
            except Exception as error:
                result["error"] = {"type": type(error).__name__, "message": str(error)}
                result["automatic_status"] = "error"
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            result["finished_at"] = utc()
            checkpoint()
            emit("case_complete" if result["complete"] else "case_failed", case_id=case["id"],
                 report=str(case_output), semantic_quality="unreviewed")
            if not result["complete"]:
                report["stop_reason"] = "first_execution_or_completion_failure"
                break
        report["complete"] = len(report["cases"]) == len(corpus["cases"]) and all(case["complete"] for case in report["cases"])
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if translator is not None:
            translator.unload_model()
            report["native_model_unloaded"] = not translator.model_is_loaded
        report["finished_at"] = utc()
        save(output, report)
    emit("screen_complete", complete=report["complete"], cases=len(report["cases"]),
         native_model_unloaded=report.get("native_model_unloaded"), semantic_quality="unreviewed")
    return int(not report["complete"] or report.get("error") is not None)


if __name__ == "__main__":
    raise SystemExit(main())
