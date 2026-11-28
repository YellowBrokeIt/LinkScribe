"""Frozen, frontend-only comparison. Never loads a speech encoder or decoder."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


def validate(plan, path):
    assert digest(__file__) == plan["helper_sha256"]
    for item in plan["pinned_files"]:
        assert digest(item["path"]) == item["sha256"], item["path"]
    for package, version in plan["runtime_versions"].items():
        assert importlib.metadata.version(package) == version, package
    assert len(plan["cases"]) == 8
    assert plan["tolerance"] == {"atol": 0.0005, "rtol": 0.0001, "equal_nan": False}
    assert plan["speech_model_initialization_allowed"] is False
    return {"validated_at": stamp(), "plan_sha256": digest(path),
            "speech_model_initialized": False, "frontend_computed": False}


def worker(plan, path):
    out = Path(plan["results_directory"])
    progress = out / "progress.json"
    phase_start = time.monotonic()
    save(progress, {"phase": "initialization", "phase_started": phase_start})
    os.sched_setaffinity(0, {plan["cpu_core"]})
    attempts = []

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            attempts.append(event)
            raise RuntimeError("Network access is disabled for this offline check")

    sys.addaudithook(audit)
    import numpy as np
    import onnxruntime as ort

    ort.disable_telemetry_events()
    np.random.seed(plan["qa_seed"])
    ort.set_seed(plan["qa_seed"])
    original_constructor = ort.InferenceSession
    sessions = []
    permitted = Path(plan["supplied_onnx_frontend"]).resolve()

    def guarded_constructor(source, *args, **kwargs):
        assert isinstance(source, (str, Path)) and Path(source).resolve() == permitted
        assert not sessions, "Only one existing frontend session is permitted"
        session = original_constructor(source, *args, **kwargs)
        actual_options = session.get_session_options()
        sessions.append({"path": str(permitted), "sha256": digest(permitted),
                         "providers": session.get_providers(),
                         "intra_op_threads": actual_options.intra_op_num_threads,
                         "inter_op_threads": actual_options.inter_op_num_threads,
                         "execution_mode": str(actual_options.execution_mode)})
        return session

    ort.InferenceSession = guarded_constructor
    from onnx_asr.preprocessors.numpy_preprocessor import NemoPreprocessorNumpy

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    frontend = ort.InferenceSession(str(permitted), sess_options=options,
                                   providers=["CPUExecutionProvider"])
    assert frontend.get_providers() == ["CPUExecutionProvider"]
    assert {item.name for item in frontend.get_inputs()} == {"waveforms", "waveforms_lens"}
    assert {item.name for item in frontend.get_outputs()} == {"features", "features_lens"}
    numpy_frontend = NemoPreprocessorNumpy("nemo128")
    prior = {case["id"]: case for case in json.loads(Path(plan["original_report"]).read_text())["cases"]}
    report = {"started_at": stamp(), "plan_sha256": digest(path), "complete": False,
              "speech_model_initialized": False, "speech_recognition_performed": False,
              "frontend_computed": True, "frontend_sessions": sessions,
              "qa_seed": plan["qa_seed"], "dither": "Neither inspected frontend applies dither",
              "initialization_seconds": time.monotonic() - phase_start,
              "cpu_affinity": sorted(os.sched_getaffinity(0)), "cases": []}
    for case in plan["cases"]:
        started = time.monotonic()
        save(progress, {"phase": "case", "case": case["id"], "phase_started": started})
        wave = np.load(case["array_path"], allow_pickle=False)
        assert wave.dtype.str == "<f4" and list(wave.shape) == case["shape"]
        assert wave.size == case["sample_count"] and case["sample_rate_hz"] == 16000
        before = hashlib.sha256(wave.tobytes()).hexdigest()
        assert before == case["pcm_sha256"]
        lengths = np.array([wave.size], dtype=np.int64)
        batch = wave[None, :]
        numpy_features, numpy_lengths = numpy_frontend(batch, lengths)
        assert hashlib.sha256(wave.tobytes()).hexdigest() == before
        onnx_features, onnx_lengths = frontend.run(
            ["features", "features_lens"], {"waveforms": batch, "waveforms_lens": lengths})
        assert hashlib.sha256(wave.tobytes()).hexdigest() == before
        assert numpy_features.dtype.str == onnx_features.dtype.str == "<f4"
        assert numpy_lengths.dtype.str == onnx_lengths.dtype.str == "<i8"
        retained = out / (case["id"] + ".npz")
        np.savez_compressed(retained, numpy_features=numpy_features, onnx_features=onnx_features,
                            numpy_lengths=numpy_lengths, onnx_lengths=onnx_lengths)
        numpy_hash = hashlib.sha256(numpy_features.tobytes()).hexdigest()
        row = {"id": case["id"], "attempt_per_frontend": 1, "sample_count": wave.size,
               "pcm_sha256": before, "full_input_unchanged": True,
               "numpy_shape": list(numpy_features.shape), "onnx_shape": list(onnx_features.shape),
               "numpy_lengths": numpy_lengths.tolist(), "onnx_lengths": onnx_lengths.tolist(),
               "numpy_features_sha256": numpy_hash,
               "onnx_features_sha256": hashlib.sha256(onnx_features.tobytes()).hexdigest(),
               "numpy_matches_original_screen_features": numpy_hash == prior[case["id"]]["features"]["sha256"],
               "complete_feature_pair_file": retained.name,
               "complete_feature_pair_sha256": digest(retained)}
        same_shape = numpy_features.shape == onnx_features.shape
        same_lengths = np.array_equal(numpy_lengths, onnx_lengths)
        finite = bool(np.isfinite(numpy_features).all() and np.isfinite(onnx_features).all())
        row.update({"equal_shape": same_shape, "equal_lengths": bool(same_lengths), "all_finite": finite})
        if same_shape:
            diff = numpy_features.astype(np.float64) - onnx_features.astype(np.float64)
            close = np.isclose(numpy_features, onnx_features, **plan["tolerance"])
            absolute = np.abs(diff)
            row.update({"feature_values": diff.size, "violating_values": int((~close).sum()),
                        "max_absolute_difference": float(absolute.max()),
                        "mean_absolute_difference": float(absolute.mean()),
                        "rms_difference": float(np.sqrt((diff * diff).mean())),
                        "max_difference_index": list(map(int, np.unravel_index(absolute.argmax(), absolute.shape))),
                        "violations_per_frame": (~close).sum(axis=(0, 1)).tolist()})
            parity = bool(close.all())
        else:
            parity = False
        row["release_tolerance_pass"] = bool(same_shape and same_lengths and finite and parity)
        row["elapsed_seconds"] = time.monotonic() - started
        report["cases"].append(row)
        save(out / "report.json", report)
    report.update({"complete": True, "finished_at": stamp(), "python_network_attempts": attempts,
                   "all_eight_pass": all(x["release_tolerance_pass"] for x in report["cases"]),
                   "all_eight_match_original_numpy_features": all(x["numpy_matches_original_screen_features"] for x in report["cases"]),
                   "worker_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024})
    report["worker_measured_limits_pass"] = bool(
        report["worker_peak_rss_bytes"] <= plan["limits"]["rss_bytes"]
        and report["initialization_seconds"] <= plan["limits"]["startup_seconds"]
        and all(row["elapsed_seconds"] <= plan["limits"]["per_case_seconds"] for row in report["cases"]))
    validate(plan, path)
    report["pinned_files_unchanged_after_run"] = True
    save(out / "report.json", report)
    save(progress, {"phase": "complete", "phase_started": time.monotonic()})
    print(json.dumps({key: report[key] for key in ["complete", "all_eight_pass", "all_eight_match_original_numpy_features", "worker_peak_rss_bytes"]}), flush=True)


def execute(plan, path):
    out = Path(plan["results_directory"])
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(plan["environment"])
    command = [plan["python"], str(Path(__file__).resolve()), "--plan", str(path), "--worker"]
    started = time.monotonic()
    summary = {"started_at": stamp(), "plan_sha256": digest(path), "command": command,
               "worker_peak_sampled_rss_bytes": 0, "stopped_at_limit": None}
    with (out / "worker.log").open("w") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        summary["worker_pid"] = process.pid
        try:
            while process.poll() is None:
                now = time.monotonic()
                status = Path(f"/proc/{process.pid}/status")
                if status.exists():
                    lines = status.read_text().splitlines()
                    rss = next((int(x.split()[1]) * 1024 for x in lines if x.startswith("VmRSS:")), 0)
                    summary["worker_peak_sampled_rss_bytes"] = max(rss, summary["worker_peak_sampled_rss_bytes"])
                reason = None
                if summary["worker_peak_sampled_rss_bytes"] > plan["limits"]["rss_bytes"]:
                    reason = "rss_limit"
                if now - started > plan["limits"]["total_seconds"]:
                    reason = "total_time_limit"
                progress = out / "progress.json"
                if progress.exists():
                    current = json.loads(progress.read_text())
                    bound = plan["limits"]["per_case_seconds"] if current["phase"] == "case" else plan["limits"]["startup_seconds"]
                    if current["phase"] != "complete" and now - current["phase_started"] > bound:
                        reason = "phase_time_limit"
                if reason:
                    summary["stopped_at_limit"] = reason
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.05)
            code = process.wait(timeout=3)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
    summary.update({"returncode": code, "finished_at": stamp(), "elapsed_seconds": time.monotonic() - started})
    save(out / "execution.json", summary)
    print(json.dumps(summary, indent=2))
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    checked = validate(plan, args.plan)
    if args.worker:
        worker(plan, args.plan)
    elif args.execute:
        return execute(plan, args.plan)
    else:
        print(json.dumps(checked, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
