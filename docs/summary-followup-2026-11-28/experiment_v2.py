#!/usr/bin/env python3
"""Actual paired short-source development experiment; never a semantic pass gate."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from smoke_full_local_workflow import ProcessMemory
from candidate_v2 import summarize


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checkpoint(path, report):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--profile", choices=["baseline", "candidate"], action="append")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite existing model evidence.")
    corpus_path = ROOT / "tests/fixtures/summary_quality_cases.json"
    corpus = json.loads(corpus_path.read_text())
    cases = [case for case in corpus["cases"] if case["id"] in args.case]
    if len(cases) != len(set(args.case)) or any(case["split"] != "development" for case in cases):
        raise SystemExit("Only known development cases may be selected by this script.")
    if any(case["long_form"] for case in cases):
        raise SystemExit("Candidate v2 is deliberately short-source only.")
    baseline_path = HERE / "baseline-enhancements.py"
    spec = importlib.util.spec_from_file_location("isolated_summary_baseline", baseline_path)
    implementation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(implementation)
    profiles = args.profile or ["baseline", "candidate"]
    report = {"experiment": "source-first revised single-generation short-summary v2", "complete": False,
              "started_utc": datetime.now(timezone.utc).isoformat(), "semantic_quality": "unreviewed",
              "limits": "Development diagnostics, not application/export/ASR validation. Exact quote/quantity checks do not prove semantic entailment, roles, tense, permission scope or completeness. Long-form summaries are not tested by this candidate.",
              "baseline_sha256": digest(baseline_path), "candidate_sha256": digest(HERE / "candidate_v2.py"),
              "candidate_dependency_sha256": digest(HERE / "candidate_v1.py"), "runner_sha256": digest(__file__), "corpus_sha256": digest(corpus_path),
              "selected_cases": args.case, "profiles": profiles,
              "runtime": {"version": implementation.local_ollama_json("/api/version"),
                          "tags": implementation.local_ollama_json("/api/tags"),
                          "options": implementation.ollama_inference_options(),
                          "model": implementation.ollama_settings("summary")[1]}, "runs": []}
    original = implementation.local_ollama_json
    checkpoint(args.output, report)
    for case in cases:
        for profile in profiles:
            run = {"id": case["id"], "profile": profile, "fixture": copy.deepcopy(case),
                   "complete": False, "requests": [], "result": None, "error": None}
            report["runs"].append(run)
            checkpoint(args.output, report)

            def observe(path, payload=None, timeout=1.5):
                call = {"path": path, "request": copy.deepcopy(payload), "timeout": timeout,
                        "control": implementation.is_ollama_control_request(payload), "response": None}
                run["requests"].append(call)
                checkpoint(args.output, report)
                start = time.monotonic()
                try:
                    response = original(path, payload, timeout)
                    call["response"] = copy.deepcopy(response)
                    return response
                except Exception as exc:
                    call["error"] = f"{type(exc).__name__}: {exc}"
                    raise
                finally:
                    call["wall_seconds"] = round(time.monotonic() - start, 3)
                    checkpoint(args.output, report)

            implementation.local_ollama_json = observe
            sampler = ProcessMemory(int(os.environ["LINKSCRIBE_OLLAMA_SERVER_PID"]))
            sampler.verify_endpoint("http://127.0.0.1:11434")
            sampler.start()
            started = time.monotonic()
            print(json.dumps({"starting": case["id"], "profile": profile}), flush=True)
            try:
                if profile == "baseline":
                    run["result"] = implementation.summarize_segments(case["segments"], case["source_language"])
                    run["accepted"] = True
                else:
                    run.update(summarize(implementation, case["segments"], case["source_language"]))
            except Exception as exc:
                run["accepted"] = False
                run["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                implementation.local_ollama_json = original
                sampler.stop()
                run["memory"] = sampler.snapshot()
                run["wall_seconds"] = round(time.monotonic() - started, 3)
                run["complete"] = True
                checkpoint(args.output, report)
                print(json.dumps({"finished": case["id"], "profile": profile,
                                  "accepted": run["accepted"], "seconds": run["wall_seconds"],
                                  "error": run["error"], "validation_errors": run.get("validation_errors", []),
                                  "peak_pss_mib": run["memory"]["peak_combined_pss_mib"]}), flush=True)
    report["complete"] = True
    report["completed_utc"] = datetime.now(timezone.utc).isoformat()
    report["hashes_unchanged"] = (
        digest(baseline_path) == report["baseline_sha256"] and
        digest(HERE / "candidate_v2.py") == report["candidate_sha256"] and
        digest(corpus_path) == report["corpus_sha256"] and
        digest(HERE / "candidate_v1.py") == report["candidate_dependency_sha256"])
    checkpoint(args.output, report)
    return 0 if report["hashes_unchanged"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
