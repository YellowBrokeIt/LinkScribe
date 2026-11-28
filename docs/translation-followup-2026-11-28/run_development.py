"""Run the predeclared translation comparison in an isolated local daemon.

No models are downloaded here. Use the verified shared runtime and model cache
after the other experiment has released its inference slot.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import evaluate_translation_quality as qa
from measure_summary_memory import oom_deltas, oom_snapshot
from smoke_full_local_workflow import ProcessMemory


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_local(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:11434" + path, timeout=3) as response:
        return json.load(response)


def load_profile(name, expected):
    path = HERE / f"{name}-enhancements.py"
    if sha(path) != expected:
        raise ValueError("The predeclared candidate source changed.")
    spec = importlib.util.spec_from_file_location(f"translation_trial_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stop_owned(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("baseline", "thinking", "both"), default="both")
    parser.add_argument("--max-seconds", type=int, default=900)
    args = parser.parse_args()
    if not 60 <= args.max_seconds <= 1200:
        parser.error("--max-seconds must be between 60 and 1200.")
    plan = json.loads((HERE / "plan.json").read_text())
    corpus = ROOT / plan["evaluation"]["corpus"]
    unused = ROOT / plan["untouched_validation"]["path"]
    if sha(corpus) != plan["evaluation"]["corpus_sha256"] or sha(unused) != plan["untouched_validation"]["sha256"]:
        raise ValueError("A frozen corpus changed; do not continue this experiment.")
    if sha(ROOT / "enhancements.py") != plan["baseline_sha256"]:
        raise ValueError("Production source changed after the comparison was declared.")
    profiles = ("baseline", "thinking") if args.profile == "both" else (args.profile,)
    for name in profiles:
        if (HERE / f"{name}-development.json").exists():
            raise ValueError(f"Refusing to overwrite existing {name} evidence.")
    binary = args.runtime_dir.resolve() / "bin/ollama"
    if not binary.is_file() or not args.models_dir.is_dir():
        raise ValueError("The prepared runtime/model cache is unavailable.")
    if sha(binary) != plan["verified_runtime"]["binary_sha256"]:
        raise ValueError("The runtime binary differs from the verified release archive.")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 11434))
    summary = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
               "plan_sha256": sha(HERE / "plan.json"), "runner_sha256": sha(__file__),
               "ollama_binary_sha256": sha(binary), "profiles": [], "complete": False,
               "semantic_quality": "unreviewed"}
    output = HERE / f"execution-{args.profile}.json"
    if output.exists():
        raise ValueError("Refusing to overwrite an existing execution report.")
    save = lambda: qa.atomic_checkpoint(output, summary)
    save()
    environment = os.environ.copy()
    environment.update({"OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(args.models_dir.resolve()),
                        "OLLAMA_NO_CLOUD": "1", "OLLAMA_NUM_PARALLEL": "1",
                        "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_CONTEXT_LENGTH": "8192",
                        "OLLAMA_KEEP_ALIVE": "1m"})
    os.environ.update({"LINKSCRIBE_TRANSLATION_BACKEND": "ollama", "LINKSCRIBE_TRANSLATION_MODEL": "qwen3:4b",
                       "LINKSCRIBE_OLLAMA_THREADS": "4", "LINKSCRIBE_OLLAMA_URL": "http://127.0.0.1:11434"})
    os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
    original_identity = qa.source_identity
    original_checkpoint = qa.atomic_checkpoint
    deadline = time.monotonic() + args.max_seconds
    signal.signal(signal.SIGALRM, lambda _number, _frame: (_ for _ in ()).throw(KeyboardInterrupt()))
    signal.alarm(args.max_seconds)
    try:
        with (HERE / f"daemon-{args.profile}.log").open("w") as log:
            process = subprocess.Popen([str(binary), "serve"], env=environment,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                for _ in range(120):
                    if process.poll() is not None:
                        raise RuntimeError("Owned Ollama daemon exited before readiness.")
                    try:
                        version = read_local("/api/version")
                        break
                    except OSError:
                        time.sleep(0.25)
                else:
                    raise TimeoutError("Owned Ollama daemon did not start.")
                tags = read_local("/api/tags")
                model = next((item for item in tags.get("models", []) if item.get("name") == "qwen3:4b"), None)
                if version.get("version") != plan["model"]["runtime"] or not model or model.get("digest") != plan["model"]["digest"]:
                    raise ValueError("Runtime/model identity differs from the predeclared comparison.")
                summary["runtime"] = version
                summary["model"] = model
                summary["host"] = {"memory_total_mib": round(__import__("psutil").virtual_memory().total / 1024**2, 1),
                                   "available_before_mib": round(__import__("psutil").virtual_memory().available / 1024**2, 1)}
                save()
                for profile in profiles:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Predeclared experiment time budget exhausted.")
                    key = "baseline_sha256" if profile == "baseline" else "candidate_sha256"
                    module = load_profile(profile, plan[key])
                    qa.enhancements = module

                    def identity(path, profile=profile, module=module):
                        result = original_identity(path)
                        result["executed_enhancements"] = {"file": str(Path(module.__file__).relative_to(ROOT)),
                                                            "sha256": sha(module.__file__)}
                        result["comparison_profile"] = profile
                        result["plan_sha256"] = sha(HERE / "plan.json")
                        return result

                    qa.source_identity = identity
                    meter = ProcessMemory(process.pid)
                    meter.verify_endpoint("http://127.0.0.1:11434")
                    before_oom = oom_snapshot([os.getpid(), process.pid])
                    meter.start()

                    def checkpoint(path, report):
                        report["memory"] = meter.snapshot()
                        original_checkpoint(path, report)

                    qa.atomic_checkpoint = checkpoint
                    try:
                        report, status = qa.evaluate(corpus, HERE / f"{profile}-development.json", splits=["development"])
                    finally:
                        meter.stop()
                        qa.atomic_checkpoint = original_checkpoint
                    after_oom = oom_snapshot([os.getpid(), process.pid])
                    report["memory"] = meter.snapshot()
                    report["oom_counters"] = {"before": before_oom, "after": after_oom,
                                               "deltas": oom_deltas(before_oom, after_oom)}
                    report["unused_validation_sha256_after"] = sha(unused)
                    report["unused_validation_unchanged"] = sha(unused) == plan["untouched_validation"]["sha256"]
                    original_checkpoint(HERE / f"{profile}-development.json", report)
                    summary["profiles"].append({"name": profile, "exit_code": status,
                                                 "complete": report["complete"], "counts": report["counts"],
                                                 "memory": report["memory"]})
                    save()
                    if status == 130:
                        raise KeyboardInterrupt
                summary["complete"] = len(summary["profiles"]) == len(profiles)
            finally:
                stop_owned(process)
    except BaseException as error:
        summary["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        signal.alarm(0)
        qa.atomic_checkpoint = original_checkpoint
        qa.source_identity = original_identity
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        summary["unused_validation_unchanged"] = sha(unused) == plan["untouched_validation"]["sha256"]
        save()
    print(json.dumps({"complete": summary["complete"], "profiles": [entry["name"] for entry in summary["profiles"]],
                      "error": summary.get("error"), "report": str(output)}))
    return int(not summary["complete"] or any(entry["exit_code"] for entry in summary["profiles"]))


if __name__ == "__main__":
    raise SystemExit(main())
