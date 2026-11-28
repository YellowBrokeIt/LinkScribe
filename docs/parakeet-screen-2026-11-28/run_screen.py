"""Frozen recognizer-only Parakeet screen. Validate by default; --execute runs once."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def require(value, label):
    if not value:
        raise ValueError(label)


def verify(plan, plan_path):
    require(sha(__file__) == plan["helper_sha256"], "helper changed")
    for name, expected in plan["runtime_versions"].items():
        require(version(name) == expected, "runtime changed: " + name)
    for item in plan["pinned_files"]:
        path = Path(item["path"])
        require(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
                "pinned file changed: " + str(path))
    require(plan["attempts_per_case"] == 1 and len(plan["case_inputs"]) == 8, "fixed eight-case protocol")
    require(plan["vad"] is False and plan["source_language_argument"] is None
            and plan["target_language_argument"] is None, "fixed recognition policy")
    require(len(plan["cpu_affinity"]) == 4 and set(plan["cpu_affinity"]) <= os.sched_getaffinity(0),
            "four pinned CPUs unavailable")
    return sha(plan_path)


def worker(plan, plan_path, output, expected_plan_sha):
    require(verify(plan, plan_path) == expected_plan_sha, "worker plan identity")
    os.sched_setaffinity(0, set(plan["cpu_affinity"]))
    for key, value in plan["environment"].items():
        require(os.environ.get(key) == value, "environment differs: " + key)
    report = {"created_at": now(), "complete": False, "plan_sha256": expected_plan_sha,
              "helper_sha256": sha(__file__), "scope": "isolated_recognizer_only",
              "app_integration_exercised": False, "fresh_validation": False,
              "semantic_quality": "unreviewed", "reference_supplied_to_decoder": False,
              "source_language_argument": None, "target_language_argument": None,
              "detected_language_returned_by_runtime": False,
              "runtime_versions": plan["runtime_versions"], "cpu_affinity": sorted(os.sched_getaffinity(0)),
              "environment": plan["environment"], "onnx_sessions": [], "cases": [],
              "python_network_attempts": []}
    progress_path = output.parent / "progress.json"
    def progress(stage, case_id=None):
        write_json(progress_path, {"stage": stage, "case_id": case_id, "started_monotonic": time.monotonic(),
                                   "at": now(), "pid": os.getpid()})
    def no_network(event, arguments):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            report["python_network_attempts"].append({"event": event, "at": now()})
            raise RuntimeError("Python network access is disabled in the offline recognition worker")
    sys.addaudithook(no_network)
    start = time.monotonic()
    try:
        progress("initialization")
        # Heavy imports and all model/session construction occur only in this child,
        # after the coordinator explicitly starts --execute.
        import numpy as np
        import onnxruntime as rt
        rt.disable_telemetry_events()
        np.random.seed(plan["qa_random_seed"])
        rt.set_seed(plan["qa_random_seed"])
        report["qa_random_seed"] = plan["qa_random_seed"]
        report["onnxruntime_disable_telemetry_events_called"] = True
        import onnx_asr
        options = rt.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
        original_session = rt.InferenceSession
        def observed_session(source, *args, **kwargs):
            if isinstance(source, (str, Path)):
                identity = {"kind": "path", "path": str(source), "sha256": sha(source)}
            else:
                identity = {"kind": "embedded_bytes", "bytes": len(source),
                            "sha256": hashlib.sha256(source).hexdigest()}
            session = original_session(source, *args, **kwargs)
            settings = session.get_session_options()
            identity.update(providers=session.get_providers(), intra_op_num_threads=settings.intra_op_num_threads,
                            inter_op_num_threads=settings.inter_op_num_threads,
                            execution_mode=str(settings.execution_mode))
            require(identity["providers"] == ["CPUExecutionProvider"] and
                    settings.intra_op_num_threads == 4 and settings.inter_op_num_threads == 1,
                    "unexpected actual session CPU configuration")
            report["onnx_sessions"].append(identity)
            return session
        rt.InferenceSession = observed_session
        try:
            model = onnx_asr.load_model(
                "nemo-parakeet-tdt-0.6b-v3", plan["model_directory"], quantization="int8",
                providers=["CPUExecutionProvider"], sess_options=options,
                preprocessor_config={"max_concurrent_workers": 1, "use_numpy_preprocessors": True},
                resampler_config={"providers": ["CPUExecutionProvider"], "sess_options": options},
            ).with_timestamps()
        finally:
            rt.InferenceSession = original_session
        require(type(model.asr).__name__ == "NemoConformerTdt", "unexpected recognizer class")
        require(type(model.asr._preprocessor).__name__ == "NemoPreprocessorNumpy", "unexpected frontend")
        require(model.asr._vocab_size == plan["tokenizer"]["vocabulary_entries"]
                and model.asr._blank_idx == plan["tokenizer"]["blank_id"]
                and model.asr._max_tokens_per_step == plan["tokenizer"]["normal_max_tokens_per_step"]
                and model.asr.window_step * model.asr._subsampling_factor == plan["tokenizer"]["emission_frame_seconds"],
                "actual tokenizer/decoder differs from frozen policy")
        report["actual_tokenizer"] = {"vocabulary_entries": model.asr._vocab_size,
                                      "blank_id": model.asr._blank_idx,
                                      "emission_frame_seconds": model.asr.window_step * model.asr._subsampling_factor}
        for name in ("encoder-model.int8.onnx", "decoder_joint-model.int8.onnx"):
            expected_path = str(Path(plan["model_directory"]) / name)
            require(sum(s.get("path") == expected_path for s in report["onnx_sessions"]) == 1,
                    "selected model file was not loaded exactly once")
        report["model_initialized_at"] = now()
        report["initialization_elapsed_seconds"] = round(time.monotonic() - start, 6)
        report["actual_model_config"] = model.asr.config
        report["actual_frontend"] = type(model.asr._preprocessor).__name__
        report["token_timestamp_kind"] = "token emission frame * 0.01 seconds * subsampling_factor; no word ends invented"
        report["max_tokens_per_step"] = model.asr._max_tokens_per_step
        current = {}
        original_preprocessor = model.asr._preprocessor
        original_decode = model.asr._decode_tokens
        def observed_preprocessor(waveforms, lengths):
            require(waveforms.shape == (1, current["sample_count"])
                    and lengths.tolist() == [current["sample_count"]]
                    and waveforms.dtype.str == "<f4", "frontend did not receive complete float32 audio")
            current["frontend_input_pcm_sha256"] = hashlib.sha256(waveforms[0].tobytes()).hexdigest()
            require(current["frontend_input_pcm_sha256"] == current["pcm_sha256"], "frontend audio changed")
            features, feature_lengths = original_preprocessor(waveforms, lengths)
            current["frontend_calls"] = current.get("frontend_calls", 0) + 1
            current["features"] = {"shape": list(features.shape), "dtype": features.dtype.str,
                                   "lengths": feature_lengths.tolist(),
                                   "sha256": hashlib.sha256(features.tobytes()).hexdigest()}
            return features, feature_lengths
        def observed_decode(ids, indices, logprobs):
            ids, indices, logprobs = list(ids), list(indices), list(logprobs)
            result = original_decode(ids, indices, logprobs)
            current.setdefault("decode_calls", []).append({"token_ids": ids, "emission_frame_indices": indices,
                "token_logprobs": [float(x) for x in logprobs], "output": asdict(result)})
            return result
        model.asr._preprocessor = observed_preprocessor
        model.asr._decode_tokens = observed_decode
        for item in plan["case_inputs"]:
            current = {"id": item["id"], "sample_count": item["sample_count"], "pcm_sha256": item["pcm_sha256"],
                       "started_at": now(), "attempt": 1, "source_language_argument": None,
                       "target_language_argument": None, "vad_used": False, "audio_trimmed": False}
            report["cases"].append(current)
            progress("recognition", item["id"])
            case_start = time.monotonic()
            waveform = np.load(item["array_path"], allow_pickle=False)
            require(waveform.shape == (item["sample_count"],) and waveform.dtype.str == "<f4", "frozen PCM shape/dtype")
            require(hashlib.sha256(waveform.tobytes()).hexdigest() == item["pcm_sha256"], "frozen PCM digest")
            waveform.flags.writeable = False
            # No source/target language, reference, prompt, glossary or correction is supplied.
            result = model.recognize(waveform, sample_rate=16000)
            current["raw_result"] = asdict(result)
            current["elapsed_seconds"] = round(time.monotonic() - case_start, 6)
            current["process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            require(current["frontend_calls"] == 1 and len(current["decode_calls"]) == 1, "one complete decode per case")
            require(current["decode_calls"][0]["output"] == current["raw_result"], "raw result changed")
            require(hashlib.sha256(waveform.tobytes()).hexdigest() == item["pcm_sha256"], "input changed after recognition")
            stamps, tokens, logprobs = result.timestamps, result.tokens, result.logprobs
            current["checks"] = {
                "nonempty_text": bool(result.text.strip()),
                "complete_original_pcm_to_frontend": True,
                "single_unmodified_runtime_decode": True,
                "token_fields_same_length": len(stamps) == len(tokens) == len(logprobs),
                "finite_token_fields": all(math.isfinite(x) for x in stamps + logprobs),
                "token_times_ordered_in_recording": all(0 <= x <= item["duration_seconds"] + 0.08 for x in stamps)
                    and all(a <= b for a, b in zip(stamps, stamps[1:])),
            }
            current["structural_status"] = "pass" if all(current["checks"].values()) else "fail"
            current["finished_at"] = now()
            write_json(output, report)
            require(current["structural_status"] == "pass", "structural recognition failure")
            require(current["process_peak_rss_bytes"] <= plan["rss_limit_bytes"], "recorded RSS exceeded limit")
        require(verify(plan, plan_path) == expected_plan_sha, "post-run provenance changed")
        report["pinned_files_unchanged_after_run"] = True
        report["complete"] = len(report["cases"]) == 8
        progress("complete")
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        report["finished_at"] = now()
        report["elapsed_seconds"] = round(time.monotonic() - start, 6)
        report["process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        write_json(output, report)
    return 0 if report["complete"] else 1


def process_group_rss(pgid):
    total = 0
    page = os.sysconf("SC_PAGE_SIZE")
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == pgid:
                total += int((path / "statm").read_text().split()[1]) * page
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return total


def terminate_owned(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--expected-plan-sha", help=argparse.SUPPRESS)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    plan_sha = verify(plan, args.plan)
    output_dir = Path(plan["output_directory"])
    if args.worker:
        return worker(plan, args.plan, output_dir / "recognizer-report.json", args.expected_plan_sha)
    if not args.execute:
        print(json.dumps({"validated": True, "plan_sha256": plan_sha,
                          "model_initialized": False, "inference_performed": False}))
        return 0
    require(not output_dir.exists(), "Preserve prior attempt; output directory already exists")
    output_dir.mkdir()
    environment = dict(os.environ, **plan["environment"])
    command = [sys.executable, str(Path(__file__).resolve()), "--plan", str(args.plan.resolve()),
               "--worker", "--expected-plan-sha", plan_sha]
    record = {"started_at": now(), "plan_sha256": plan_sha, "command": command,
              "sampled_process_group_peak_rss_bytes": 0, "stopped_at_limit": None}
    started = time.monotonic()
    try:
        with (output_dir / "worker.log").open("xb") as log:
            process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            while process.poll() is None:
                elapsed = time.monotonic() - started
                rss = process_group_rss(process.pid)
                record["sampled_process_group_peak_rss_bytes"] = max(record["sampled_process_group_peak_rss_bytes"], rss)
                reason = None
                if rss > plan["rss_limit_bytes"]:
                    reason = "process_group_rss"
                elif elapsed > plan["total_wall_seconds"]:
                    reason = "total_wall_time"
                progress_path = output_dir / "progress.json"
                if progress_path.exists():
                    state = json.loads(progress_path.read_text())
                    if state["stage"] == "initialization" and elapsed > plan["initialization_wall_seconds"]:
                        reason = "initialization_wall_time"
                    elif state["stage"] == "recognition" and (
                        time.monotonic() - state["started_monotonic"] > plan["per_case_wall_seconds"]
                    ):
                        reason = "recognition_wall_time"
                elif elapsed > plan["initialization_wall_seconds"]:
                    reason = "startup_wall_time"
                if reason:
                    record["stopped_at_limit"] = reason
                    terminate_owned(process)
                    break
                time.sleep(0.1)
            record["returncode"] = process.wait()
    except BaseException:
        if "process" in locals() and process.poll() is None:
            terminate_owned(process)
        raise
    finally:
        record["finished_at"] = now()
        record["elapsed_seconds"] = round(time.monotonic() - started, 6)
        write_json(output_dir / "execution.json", record)
        print(json.dumps(record), flush=True)
    return 0 if record.get("returncode") == 0 and record["stopped_at_limit"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
