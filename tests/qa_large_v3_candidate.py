"""Hosted-only full large-v3 screen using the unchanged production recognizer.

Validation uses the standard library only. Model download and recognition require
GitHub Actions. Existing Qwen preparation and owned-group cleanup utilities are
reused without changing that frozen helper or its historical evidence.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_large_v3_shared_qa", Path(__file__).with_name("qa_qwen3_asr_candidate.py"))
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)
now, require, sha256, write_json = common.now, common.require, common.sha256, common.write_json
repo_file, cpu_selection = common.repo_file, common.cpu_selection
DEFAULT_PLAN = ROOT / "docs/large-v3-screen-2026-11-28/plan.json"


def canonical_ast(value):
    """Location-free syntax identity, stable for empty 3.12 type-parameter fields."""
    if isinstance(value, ast.AST):
        return [type(value).__name__, [[key, canonical_ast(item)] for key, item in ast.iter_fields(value)
                                      if not (key == "type_params" and not item)]]
    if isinstance(value, list):
        return [canonical_ast(item) for item in value]
    return value


def production_policy():
    path = ROOT / "app.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_recognize"]
    require(len(functions) == 1, "one production _recognize function required")
    node = functions[0]
    def number(expression):
        if isinstance(expression, ast.Constant) and type(expression.value) in {int, float}:
            return expression.value
        if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Mult):
            return number(expression.left) * number(expression.right)
        raise ValueError("unexpected production numeric constant expression")
    constants = {}
    for item in tree.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id in {"MAX_SECONDS", "ASR_NO_SPEECH_THRESHOLD"}:
                    constants[target.id] = number(item.value)
    syntax = json.dumps(canonical_ast(node), ensure_ascii=False, separators=(",", ":"))
    return {"module": "app.py", "module_sha256_at_observation": sha256(path),
            "function": "_recognize", "function_ast_sha256": hashlib.sha256(syntax.encode()).hexdigest(),
            "constants": constants, "function_source_lf": ast.get_source_segment(source, node) + "\n"}, node


def validate_request(kwargs):
    expected = {"language": None, "beam_size": 5, "vad_filter": False,
                "no_speech_threshold": 0.6, "condition_on_previous_text": False}
    require(kwargs == expected, "actual production transcription request changed")


def validate_effective_options(options):
    expected = {"beam_size": 5, "best_of": 5, "patience": 1, "length_penalty": 1,
                "repetition_penalty": 1, "no_repeat_ngram_size": 0,
                "temperatures": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                "compression_ratio_threshold": 2.4, "log_prob_threshold": -1.0,
                "no_speech_threshold": 0.6, "condition_on_previous_text": False,
                "prompt_reset_on_temperature": 0.5, "initial_prompt": None,
                "prefix": None, "hotwords": None, "without_timestamps": False,
                "max_initial_timestamp": 1.0, "word_timestamps": False,
                "max_new_tokens": None, "clip_timestamps": "0",
                "hallucination_silence_threshold": None}
    for key, value in expected.items():
        actual = options.get(key)
        if isinstance(actual, tuple):
            actual = list(actual)
        require(actual == value, "effective native option changed: " + key)


def validate_native_segment_times(segments):
    previous_start, previous_end = -1.0, -1.0
    for segment in segments:
        start, end = segment["start"], segment["end"]
        require(type(start) in {int, float} and type(end) in {int, float} and
                math.isfinite(start) and math.isfinite(end) and 0 <= start < end and
                start >= previous_start and end >= previous_end,
                "native segment times are not finite and ordered")
        previous_start, previous_end = start, end


def validate_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    require(plan["model_id"] == "Systran/faster-whisper-large-v3" and
            plan["model_revision"] == "edaa852ec7e145841d8ffdb056a99866b5f0a478", "wrong full large-v3 checkpoint")
    require(plan["compute_type"] == "int8" and plan["device"] == "cpu" and plan["max_cpu_threads"] == 4 and
            plan["num_workers"] == 1, "native CPU int8/thread policy changed")
    require(plan["attempts_per_case"] == plan["model_initializations"] == 1, "one-attempt protocol required")
    require((plan["rss_limit_bytes"], plan["startup_seconds"], plan["per_case_seconds"], plan["total_worker_seconds"])
            == (6 * 1024**3, 180, 180, 1800), "declared resource limits changed")
    require(plan["source_language_argument"] is None and plan["word_timestamps"] is False and
            plan["references_supplied_to_decoder"] is False, "language/text/timing guidance changed")
    for item in plan["source_files"]:
        source = repo_file(item["path"])
        require(source.stat().st_size == item["bytes"] and sha256(source) == item["sha256"],
                "frozen source changed: " + item["path"])
    original = {x["id"]: x for x in json.loads(repo_file(plan["original_fixtures_path"]).read_text())["cases"]}
    arrays = {x["id"]: x for x in json.loads(repo_file(plan["original_arrays_path"]).read_text())["cases"]}
    require(len(plan["cases"]) == 8 and [x["id"] for x in plan["cases"]] == list(original), "original eight cases/order changed")
    for item in plan["cases"]:
        common.safe_filename(item["id"])
        old, array = original[item["id"]], arrays[item["id"]]
        require(item["audio_sha256"] == old["audio_sha256"] and
                item["sample_count"] == old["provenance"]["dataset_num_samples"] == array["sample_count"] and
                item["sample_rate_hz"] == old["provenance"]["dataset_sample_rate"] == 16000 and
                item["pcm_sha256"] == array["pcm_sha256"] and array["dtype"] == "<f4" and
                array["full_untrimmed_recording"] is True and array["vad_applied"] is False,
                "original complete recording identity changed")
    pinned = json.loads(repo_file(plan["production_policy_path"]).read_text())
    observed, _ = production_policy()
    require(observed["function_ast_sha256"] == pinned["function_ast_sha256"] and
            observed["constants"] == pinned["constants"] == {"MAX_SECONDS": 7200, "ASR_NO_SPEECH_THRESHOLD": 0.6},
            "production recognition policy changed")
    model_files = json.loads(repo_file(plan["model_files_path"]).read_text())
    require(model_files["repo_id"] == plan["model_id"] and model_files["revision"] == plan["model_revision"],
            "model inventory mismatch")
    for item in model_files["files"]:
        common.safe_filename(item["filename"])
        require(item["immutable_url"].startswith("https://huggingface.co/" + plan["model_id"] + "/resolve/" +
                                                plan["model_revision"] + "/"), "model URL is not revision pinned")
    return plan


def compile_production_recognizer(factory):
    observed, node = production_policy()
    class ReadableError(Exception):
        pass
    namespace = {"math": math, "Path": Path, "ReadableError": ReadableError, "_whisper_model": factory,
                 **observed["constants"]}
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, node], type_ignores=[]))
    exec(compile(module, str(ROOT / "app.py"), "exec"), namespace)
    return namespace["_recognize"], ReadableError, observed


def worker(plan, plan_path, work, evidence, expected_plan_sha):
    common.require_hosted()
    require(sha256(plan_path) == expected_plan_sha, "worker plan identity changed")
    import dataclasses
    import importlib.metadata
    import inspect
    import resource
    cpu_ids = cpu_selection(os.sched_getaffinity(0))
    os.sched_setaffinity(0, set(cpu_ids))
    report = {"started_at": now(), "complete": False, "structural_pass": False, "semantic_quality": "unreviewed",
              "plan_sha256": expected_plan_sha, "helper_sha256": sha256(__file__), "commit": os.environ.get("GITHUB_SHA"),
              "model_initialized": False, "model_initializations": 0, "runtime_versions": {}, "cases": [],
              "cpu_affinity": cpu_ids, "python_network_attempts": [], "source_language_argument": None,
              "references_supplied_to_decoder": False, "app_integration": False, "fresh_validation": False,
              "timestamps": "native decoder segment times only; conditional word timestamps disabled"}
    output = evidence / "recognizer-report.json"
    started = time.monotonic()

    def progress(stage, case_id=None):
        write_json(evidence / "progress.json", {"stage": stage, "case_id": case_id,
                   "started_monotonic": time.monotonic(), "at": now(), "pid": os.getpid()})

    def deny_network(event, arguments):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            report["python_network_attempts"].append({"event": event, "at": now()})
            raise RuntimeError("network disabled during offline model initialization and recognition")

    sys.addaudithook(deny_network)
    write_json(output, report)
    try:
        progress("initialization")
        for name, expected in plan["runtime_versions"].items():
            report["runtime_versions"][name] = importlib.metadata.version(name)
            require(report["runtime_versions"][name] == expected, "runtime pin differs: " + name)
        common.verify_model(plan, work / "model")
        import numpy as np
        import onnxruntime
        import ctranslate2
        from faster_whisper import WhisperModel
        onnxruntime.disable_telemetry_events()
        np.random.seed(plan["qa_seed"])
        ctranslate2.set_random_seed(plan["qa_seed"])
        loading = {"device": "cpu", "compute_type": "int8", "cpu_threads": len(cpu_ids),
                   "num_workers": 1, "local_files_only": True}
        report["model_initialization_attempted"] = True
        report["model_constructor_arguments"] = loading
        write_json(output, report)
        engine = WhisperModel(str(work / "model"), **loading)
        report.update({"model_initialized": True, "model_initializations": 1,
                       "initialization_seconds": time.monotonic() - started,
                       "actual_model": {"device": engine.model.device, "compute_type": engine.model.compute_type,
                                        "cpu_threads_requested": len(cpu_ids), "num_workers_requested": 1,
                                        "num_workers_observed": engine.model.num_workers,
                                        "multilingual": engine.model.is_multilingual, "max_length": engine.max_length,
                                        "n_mels": engine.model.n_mels, "loaded": engine.model.model_is_loaded}})
        require(engine.model.device == "cpu" and engine.model.compute_type in {"int8", "int8_float32"},
                "actual model is not native CPU int8")
        require(engine.model.num_workers == 1 and engine.model.n_mels == 128 and engine.model.model_is_loaded,
                "actual native worker/model configuration changed")
        require(report["initialization_seconds"] <= plan["startup_seconds"], "recorded initialization exceeded cap")
        report["native_runtime_source_files"] = {}
        for module_name in ["faster_whisper.transcribe", "faster_whisper.audio", "faster_whisper.feature_extractor",
                            "faster_whisper.tokenizer", "faster_whisper.vad"]:
            module_path = Path(sys.modules[module_name].__file__)
            report["native_runtime_source_files"][module_name] = {"filename": module_path.name, "sha256": sha256(module_path)}
        current = {}
        native_model, native_frontend = engine.model, engine.feature_extractor
        eot = engine.hf_tokenizer.token_to_id("<|endoftext|>")
        report["native_eot_token_id"] = eot

        class DecoderObserver:
            def __getattr__(self, name):
                return getattr(native_model, name)

            def generate(self, encoded, prompts, **kwargs):
                trace = {"call": len(current["decoder_calls"]) + 1, "prompt_ids": prompts,
                         "effective_generate_arguments": kwargs, "started_at": now(), "results": []}
                current["decoder_calls"].append(trace)
                write_json(output, report)
                results = native_model.generate(encoded, prompts, **kwargs)
                for result in results:
                    sequences = result.sequences_ids
                    trace["results"].append({"sequences_ids": sequences, "scores": result.scores,
                        "no_speech_prob": result.no_speech_prob,
                        "num_generated_tokens_if_exposed": getattr(result, "num_generated_tokens", None),
                        "token_strings": [[engine.hf_tokenizer.id_to_token(t) for t in seq] for seq in sequences],
                        "text_without_special_tokens": [engine.hf_tokenizer.decode([t for t in seq if t < eot]) for seq in sequences],
                        "sequence_plus_prompt_lengths": [len(seq) + len(prompts[0]) for seq in sequences]})
                trace["finished_at"] = now()
                write_json(output, report)
                return results

        class FrontendObserver:
            def __getattr__(self, name):
                return getattr(native_frontend, name)

            def __call__(self, waveform, *args, **kwargs):
                require(waveform.dtype.str == "<f4" and waveform.shape == (current["sample_count"],) and
                        hashlib.sha256(waveform.tobytes()).hexdigest() == current["pcm_sha256"],
                        "native frontend did not receive the complete unchanged PCM")
                features = native_frontend(waveform, *args, **kwargs)
                current["frontend_calls"].append({"sample_count": waveform.size,
                    "pcm_sha256": hashlib.sha256(waveform.tobytes()).hexdigest(),
                    "arguments": kwargs, "feature_shape": list(features.shape), "feature_dtype": features.dtype.str,
                    "feature_sha256": hashlib.sha256(features.tobytes()).hexdigest()})
                return features

        engine.model, engine.feature_extractor = DecoderObserver(), FrontendObserver()

        class EngineObserver:
            def transcribe(self, waveform, **kwargs):
                validate_request(kwargs)
                require(waveform.dtype.str == "<f4" and waveform.shape == (current["sample_count"],) and
                        hashlib.sha256(waveform.tobytes()).hexdigest() == current["pcm_sha256"],
                        "production recognizer did not pass the full unchanged PCM")
                current["transcribe_calls"] += 1
                current["actual_transcribe_request"] = kwargs
                current["transcribe_input_pcm_sha256"] = hashlib.sha256(waveform.tobytes()).hexdigest()
                bound = inspect.signature(engine.transcribe).bind(waveform, **kwargs)
                bound.apply_defaults()
                current["effective_transcribe_arguments"] = {key: value for key, value in bound.arguments.items() if key != "audio"}
                require(current["effective_transcribe_arguments"]["language"] is None and
                        current["effective_transcribe_arguments"]["task"] == "transcribe",
                        "native task or automatic language changed")
                segments, info = engine.transcribe(waveform, **kwargs)
                current["transcribe_info"] = dataclasses.asdict(info)
                validate_effective_options(current["transcribe_info"]["transcription_options"])
                duration = current["sample_count"] / 16000
                require(abs(info.duration - duration) < 1e-8 and abs(info.duration_after_vad - duration) < 1e-8,
                        "native duration indicates truncation or VAD")
                write_json(output, report)

                def observe_segments():
                    for segment in segments:
                        raw = dataclasses.asdict(segment)
                        raw["token_strings"] = [engine.hf_tokenizer.id_to_token(t) for t in segment.tokens]
                        raw["text_redecoded_from_tokens"] = engine.hf_tokenizer.decode([t for t in segment.tokens if t < eot])
                        current["raw_segments"].append(raw)
                        require(raw["text"] == raw["text_redecoded_from_tokens"], "native segment text/token mismatch")
                        validate_native_segment_times(current["raw_segments"])
                        write_json(output, report)
                        yield segment
                    current["native_segment_iterator_exhausted"] = True
                    current["transcribe_info_after_exhaustion"] = dataclasses.asdict(info)
                return observe_segments(), info

        observer = EngineObserver()
        def factory(name):
            require(name == "large-v3", "unexpected production model selector")
            return observer
        recognize, ReadableError, observed_policy = compile_production_recognizer(factory)
        report["observed_production_policy"] = observed_policy
        for item in plan["cases"]:
            case_start = time.monotonic()
            current = {"id": item["id"], "attempt": 1, "sample_count": item["sample_count"],
                       "pcm_sha256": item["pcm_sha256"], "started_at": now(), "transcribe_calls": 0,
                       "frontend_calls": [], "decoder_calls": [], "raw_segments": [],
                       "native_segment_iterator_exhausted": False}
            report["cases"].append(current)
            progress("recognition", item["id"])
            write_json(output, report)
            waveform = np.load(evidence / "inputs" / (item["id"] + ".npy"), allow_pickle=False)
            require(waveform.dtype.str == "<f4" and waveform.shape == (item["sample_count"],) and
                    hashlib.sha256(waveform.tobytes()).hexdigest() == item["pcm_sha256"], "saved complete PCM changed")
            path = evidence / "inputs" / (item["id"] + ".wav")
            require(sha256(path) == item["audio_sha256"], "original WAV changed")
            try:
                result, language = recognize(path, "auto", "large-v3", word_timestamps=False)
                current["production_segments"] = result
                current["detected_language"] = language
                current["production_transcript"] = " ".join(segment["text"] for segment in result)
                current["production_outcome"] = "success"
            except ReadableError as error:
                current["production_outcome"] = "rejected"
                current["production_error"] = {"type": type(error).__name__, "message": str(error),
                    "cause": None if error.__cause__ is None else {"type": type(error.__cause__).__name__, "message": str(error.__cause__)}}
            current["raw_transcript"] = "".join(segment["text"] for segment in current["raw_segments"])
            current["checks"] = {"one_production_transcribe_call": current["transcribe_calls"] == 1,
                "one_complete_frontend_call": len(current["frontend_calls"]) == 1,
                "native_iterator_completed": current["native_segment_iterator_exhausted"],
                "raw_native_tokens_match_text": all(x["text"] == x["text_redecoded_from_tokens"] for x in current["raw_segments"]),
                "conditional_word_timestamps_off": all(x["words"] is None for x in current["raw_segments"]),
                "native_times_finite_ordered": all(
                    math.isfinite(x["start"]) and math.isfinite(x["end"]) and 0 <= x["start"] < x["end"] and
                    (index == 0 or (x["start"] >= current["raw_segments"][index - 1]["start"] and
                                    x["end"] >= current["raw_segments"][index - 1]["end"]))
                    for index, x in enumerate(current["raw_segments"])),
                "production_returned_transcript": current["production_outcome"] == "success",
                "native_decoder_results_retained": bool(current["decoder_calls"]) and all(
                    call["results"] and all(result["sequences_ids"] for result in call["results"])
                    for call in current["decoder_calls"]),
                "no_decoder_sequence_at_length_cap": all(
                    length < call["effective_generate_arguments"]["max_length"]
                    for call in current["decoder_calls"] for result in call["results"]
                    for length in result["sequence_plus_prompt_lengths"])}
            current["elapsed_seconds"] = time.monotonic() - case_start
            current["native_times_exceeding_audio_duration"] = [index for index, segment in enumerate(current["raw_segments"])
                if segment["end"] > item["sample_count"] / 16000 + 0.02]
            current["recorded_process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            current["finished_at"] = now()
            current["structural_status"] = "pass" if all(current["checks"].values()) else "fail"
            write_json(output, report)
            require(current["elapsed_seconds"] <= plan["per_case_seconds"], "recorded case time exceeded cap")
            require(current["recorded_process_peak_rss_bytes"] <= plan["rss_limit_bytes"], "recorded worker RSS exceeded cap")
        validate_plan(plan_path)
        common.verify_model(plan, work / "model")
        report["pinned_sources_and_model_files_unchanged"] = True
        report["complete"] = len(report["cases"]) == 8
        report["structural_pass"] = report["complete"] and all(x["structural_status"] == "pass" for x in report["cases"])
        progress("complete")
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        report["finished_at"] = now()
        report["elapsed_seconds"] = time.monotonic() - started
        report["recorded_process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        report["recorded_limits_pass"] = (report["elapsed_seconds"] <= plan["total_worker_seconds"] and
                                          report["recorded_process_peak_rss_bytes"] <= plan["rss_limit_bytes"])
        report["structural_pass"] = report["structural_pass"] and report["recorded_limits_pass"]
        write_json(output, report)
    return 0 if report["structural_pass"] else 1


def execute(plan, plan_path, work, evidence, *, test_command=None):
    """Existing owned-group monitor plus an archived RSS sample series."""
    common.require_hosted()
    require(json.loads((evidence / "input-preparation.json").read_text())["complete"], "inputs incomplete")
    require(json.loads((evidence / "model-download.json").read_text())["complete"], "model files unverified")
    with (evidence / "execution-requested.json").open("x") as stream:
        json.dump({"started_at": now(), "plan_sha256": sha256(plan_path), "one_attempt_only": True}, stream)
    cpu_ids = cpu_selection(os.sched_getaffinity(0))
    env = {key: value for key, value in os.environ.items() if key in {
        "PATH", "LANG", "LC_ALL", "TZ", "TMPDIR", "TEMP", "TMP", "VIRTUAL_ENV", "SYSTEMROOT", "HOME",
        "GITHUB_ACTIONS", "GITHUB_SHA", "CI"}}
    env.update(plan["worker_environment"])
    env["OMP_NUM_THREADS"] = env["MKL_NUM_THREADS"] = str(len(cpu_ids))
    env["HF_HOME"] = str(work / "offline-hf-cache")
    command = test_command or [sys.executable, str(Path(__file__).resolve()), "--action", "worker", "--plan", str(plan_path.resolve()),
               "--work", str(work.resolve()), "--evidence", str(evidence.resolve()), "--expected-plan-sha", sha256(plan_path)]
    started = time.monotonic()
    summary = {"started_at": now(), "plan_sha256": sha256(plan_path), "command": command, "cpu_affinity": cpu_ids,
               "sampled_group_peak_rss_bytes": 0, "sample_count": 0, "sample_interval_seconds": 0.1, "stop_reason": None}
    samples_path = evidence / "resource-samples.jsonl"
    with (evidence / "worker.log").open("w") as log, samples_path.open("w") as samples:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        summary["owned_process_group_id"] = process.pid
        try:
            while True:
                elapsed = time.monotonic() - started
                rss = common.group_rss(process.pid)
                samples.write(json.dumps({"elapsed_seconds": elapsed, "rss_bytes": rss}) + "\n")
                samples.flush()
                summary["sample_count"] += 1
                summary["sampled_group_peak_rss_bytes"] = max(summary["sampled_group_peak_rss_bytes"], rss)
                if process.poll() is not None:
                    break
                reason = None
                if rss > plan["rss_limit_bytes"]:
                    reason = "owned_process_group_rss_limit"
                if elapsed > plan["total_worker_seconds"]:
                    reason = "total_worker_time_limit"
                progress_path = evidence / "progress.json"
                if progress_path.exists():
                    progress = json.loads(progress_path.read_text())
                    summary["last_observed_progress"] = progress
                    if progress["stage"] == "initialization" and elapsed > plan["startup_seconds"]:
                        reason = "startup_time_limit"
                    if progress["stage"] == "recognition" and time.monotonic() - progress["started_monotonic"] > plan["per_case_seconds"]:
                        reason = "case_time_limit"
                elif elapsed > plan["startup_seconds"]:
                    reason = "worker_start_time_limit"
                if reason:
                    summary["stop_reason"] = reason
                    common.terminate_owned(process)
                    break
                time.sleep(0.1)
            process.wait(timeout=5)
        except Exception as error:
            summary["stop_reason"] = "controller_error"
            summary["controller_failure"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            summary["cleanup"] = common.terminate_owned(process)
    summary.update({"finished_at": now(), "elapsed_seconds": time.monotonic() - started, "returncode": process.poll(),
                    "owned_worker_exited": process.poll() is not None, "resource_samples_sha256": sha256(samples_path)})
    if summary["elapsed_seconds"] > plan["total_worker_seconds"] and summary["stop_reason"] is None:
        summary["stop_reason"] = "recorded_total_time_exceeded"
    if summary["sampled_group_peak_rss_bytes"] > plan["rss_limit_bytes"] and summary["stop_reason"] is None:
        summary["stop_reason"] = "recorded_group_rss_exceeded"
    if summary["cleanup"]["live_group_members_after_cleanup"] or not summary["cleanup"]["leader_exited"]:
        summary["stop_reason"] = "owned_process_group_cleanup_failed"
    write_json(evidence / "execution.json", summary)
    return 0 if summary["returncode"] == 0 and summary["stop_reason"] is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=["validate", "prepare-inputs", "download-model", "execute", "worker"], default="validate")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--local-audio", type=Path)
    parser.add_argument("--expected-plan-sha", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.evidence:
        args.evidence.mkdir(parents=True, exist_ok=True)
    try:
        plan = validate_plan(args.plan)
        if args.action == "validate":
            result = {"validated_at": now(), "plan_sha256": sha256(args.plan), "helper_sha256": sha256(__file__),
                      "model_initialized": False, "inference_performed": False, "python": sys.version,
                      "platform": platform.platform(), "github_sha": os.environ.get("GITHUB_SHA")}
            if args.evidence:
                write_json(args.evidence / "preflight.json", result)
            print(json.dumps(result))
            return 0
        require(args.work is not None and args.evidence is not None, "work/evidence directories required")
        args.work.mkdir(parents=True, exist_ok=True)
        require(args.work.resolve() != args.evidence.resolve() and not args.work.resolve().is_relative_to(args.evidence.resolve()),
                "model weights/work must remain outside uploaded evidence")
        if args.action == "prepare-inputs":
            common.prepare_inputs(plan, args.evidence, args.local_audio)
        elif args.action == "download-model":
            common.download_model(plan, args.work, args.evidence)
        elif args.action == "execute":
            return execute(plan, args.plan, args.work, args.evidence)
        else:
            return worker(plan, args.plan, args.work, args.evidence, args.expected_plan_sha)
        return 0
    except Exception as error:
        result = {"failed_at": now(), "action": args.action, "error_type": type(error).__name__, "error": str(error),
                  "model_initialization_not_claimed_by_controller": True}
        if args.evidence:
            write_json(args.evidence / (args.action + "-failure.json"), result)
        print(json.dumps(result), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
