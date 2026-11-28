"""Harmless paired regression: an exited child's cleanup exceeds the phase budget."""
from __future__ import annotations
import sys


def forbid_native(event, args):
    if event.startswith("socket."):
        raise RuntimeError("Network is forbidden in this source-only regression.")
    if event == "subprocess.Popen" and args[0] != sys.executable:
        raise RuntimeError("Only harmless Python child processes are allowed.")
    if event == "import" and args and str(args[0]).split(".")[0] in {
        "torch", "transformers", "tokenizers", "sentencepiece", "gliner", "onnxruntime", "llama_cpp", "numpy"}:
        raise RuntimeError("Model/tokenizer imports are forbidden.")


sys.addaudithook(forbid_native)

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
V1 = HERE.parent / "krikri-marker-grammar-controller-2026-11-28"
OWNED = HERE.parents[1].parent / "linkscribe-grammar-validator-runtime"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_monitor(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if OWNED.exists():
        raise RuntimeError("No actual native build root may exist during these source controls.")
    output = HERE / "late-finalization-control"
    output.mkdir()
    result_path = output / "result.json"
    program = 'print(\'GEMMA_EVENT {"event":"initialized"}\', flush=True)'
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    limits = {"rss_bytes": 256 * 1024**2, "total_seconds": 1.0,
              "initialization_seconds": 10, "case_seconds": 10}
    original_affinity = os.sched_getaffinity(0)
    results = []
    try:
        for label, folder, expected_pass in [("v1", V1, True), ("v2", HERE, False)]:
            module = load_monitor(folder / "resource_monitor.py", "finalization_monitor_" + label)
            original_stop = module.stop_owned
            calls = []

            def slow_final_cleanup(process, identities):
                started = time.monotonic()
                stopped = original_stop(process, identities)
                # The actual owned process is stopped first. This bounded delay
                # represents late cleanup, not a change to a worker/model call.
                time.sleep(1.25)
                calls.append({"cleanup_complete_before_delay": stopped,
                              "elapsed_seconds": time.monotonic() - started})
                return stopped

            module.stop_owned = slow_final_cleanup
            prefix = output / label
            report_path = output / (label + "-resources.json")
            samples_path = output / (label + "-samples.jsonl")
            report = module.monitor([sys.executable, "-c", program], environment,
                output / (label + "-log.txt"), report_path, samples_path, limits,
                {"control": "late-finalization", "revision": label,
                 "monitor_sha256": sha(folder / "resource_monitor.py"),
                 "harmless_python_program": program,
                 "injected_cleanup_delay_seconds": 1.25})
            module.stop_owned = original_stop
            matched = (report["worker_exit_code"] == 0
                       and report["elapsed_seconds"] > limits["total_seconds"]
                       and report["passed"] is expected_pass
                       and report["owned_processes_stopped"]
                       and report["measurement_complete"]
                       and len(calls) == 1 and calls[0]["cleanup_complete_before_delay"])
            if label == "v2":
                matched = matched and report["phase_time_limit_exceeded"] is True and report["stop_reason"] == "aggregate_time_limit"
            results.append({"revision": label, "expected_pass": expected_pass,
                "matched_expected_result": matched, "actual_passed": report["passed"],
                "elapsed_seconds": report["elapsed_seconds"], "phase_limit_seconds": limits["total_seconds"],
                "cleanup_complete": report["owned_processes_stopped"], "cleanup_calls": calls,
                "resource_report": {"path": report_path.name, "sha256": sha(report_path)},
                "samples": {"path": samples_path.name, "sha256": sha(samples_path)}})
    finally:
        os.sched_setaffinity(0, original_affinity)
    result = {"schema_version": 1, "passed": all(row["matched_expected_result"] for row in results),
              "v1_false_pass_preserved": results[0]["matched_expected_result"],
              "v2_rejects_same_late_finalization": results[1]["matched_expected_result"],
              "results": results, "actual_phase_receipts_created": 0,
              "compiler_native_library_converter_tokenizer_model_network_calls": 0,
              "real_owned_build_root_exists": OWNED.exists()}
    with result_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False); stream.write("\n")
    print({"passed": result["passed"], "v1_false_pass": result["v1_false_pass_preserved"],
           "v2_rejected": result["v2_rejects_same_late_finalization"], "native_calls": 0}, flush=True)
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
