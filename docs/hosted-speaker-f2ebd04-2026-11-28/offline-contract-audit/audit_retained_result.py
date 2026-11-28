#!/usr/bin/env python3
"""Offline audit of one immutable hosted result; no application/model imports.

The original failed GitHub run remains failed.  This corrects one constructor
expectation, with source-enforced CPU launch limits distinguished from absent
inference-side affinity/thread readback.  No original evidence is rewritten.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_function(path, name, extra=None, *, constructor_correction=False):
    source = Path(path).read_text(encoding="utf-8")
    if constructor_correction:
        old = 'report["model_initializations"][0]["cpu_threads"] == 4'
        require(source.count(old) == 1, "Original constructor comparison is not unique")
        source = source.replace(old, old[:-1] + "0")
    module = ast.parse(source)
    names = {name, "label_at"} if name == "score" else {name}
    body = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in names]
    require(len(body) == len(names), "Missing frozen pure function")
    namespace = {"require": require, "math": math, **(extra or {})}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def final_resources(plan, execution, samples):
    require(execution["returncode"] == 0 and execution["stop_reason"] is None, "Worker failure")
    require(execution["elapsed_seconds"] <= plan["total_worker_seconds"], "Controller deadline")
    require(execution["cpu_affinity"] == [0, 1, 2, 3] and plan["maximum_cpus"] == 4,
            "Original four-CPU launch scope changed")
    require(execution["sample_count"] == len(samples) > 0, "Incomplete resource series")
    previous = -1.0
    for sample in samples:
        require(sample["complete"] and not sample["read_errors"], "Unreadable owned member")
        require(math.isfinite(sample["elapsed_seconds"]) and previous < sample["elapsed_seconds"] <= plan["total_worker_seconds"],
                "Resource chronology or time cap")
        previous = sample["elapsed_seconds"]
        pids = [member["pid"] for member in sample["members"]]
        require(len(pids) == len(set(pids)), "Duplicate owned member")
        require(sample["rss_bytes"] == sum(member["rss_bytes"] for member in sample["members"]), "RSS member sum")
        require(0 <= sample["rss_bytes"] <= plan["rss_limit_bytes"], "RSS cap")
    require(max(sample["rss_bytes"] for sample in samples) == execution["sampled_group_peak_rss_bytes"], "RSS peak mismatch")
    cleanup = execution["cleanup"]
    require(cleanup["leader_exited"] and not cleanup["live_group_members_after_cleanup"], "Owned cleanup failed")
    final = cleanup["strict_final_sample"]
    require(execution["all_resource_samples_complete"] and final["complete"] and not final["read_errors"] and
            all(member["state"] in {"Z", "X", "exited_during_sample"} for member in final["members"]),
            "Incomplete final accounting")


def audit(binding_path):
    binding_path = Path(binding_path).resolve()
    root = binding_path.parent
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    evidence = Path(binding["retained_evidence_directory"])
    for item in binding["pinned_files"]:
        path = (root if item["location"] == "audit" else evidence) / item["path"]
        require(sha(path) == item["sha256"], "Pinned file changed: " + item["path"])
    manifest = json.loads((evidence / "artifact-manifest.json").read_text(encoding="utf-8"))
    require(sha(evidence / "artifact.zip") == manifest["zip_sha256"] == binding["artifact_zip_sha256"], "Artifact ZIP changed")
    for item in manifest["files"]:
        path = evidence / "artifact" / item["path"]
        require(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
                "Retained artifact member changed: " + item["path"])
    plan = json.loads((root / "source/original-hosted-plan.json").read_text(encoding="utf-8"))
    report = json.loads((evidence / "artifact/speaker-app-report.json").read_text(encoding="utf-8"))
    execution = json.loads((evidence / "artifact/execution.json").read_text(encoding="utf-8"))
    require(execution["github_sha"] == binding["head_sha"] and execution["plan_sha256"] == sha(root / "source/original-hosted-plan.json"),
            "Hosted source/plan changed")
    require(execution == json.loads((root / "history/original-failed-execution.json").read_text(encoding="utf-8")), "Original failure changed")
    require(execution["passed"] is False and execution["final_failure"] == {
        "type": "ValueError", "message": "Unexpected native model runtime"}, "Unexpected original failure")
    controller = root / "source/controller-f2.py"
    original = load_function(controller, "completed_contract")
    try:
        original(plan, report)
    except ValueError as exc:
        require(str(exc) == "Unexpected native model runtime", "Original contract failed elsewhere")
    else:
        raise ValueError("Original wrong constructor gate did not reject")
    corrected = load_function(controller, "completed_contract", constructor_correction=True)
    corrected(plan, report)
    samples_path = evidence / "artifact/resource-samples.jsonl"
    require(sha(samples_path) == execution["resource_samples_sha256"], "Resource sample hash changed")
    samples = [json.loads(line) for line in samples_path.read_text(encoding="utf-8").splitlines()]
    final_resources(plan, execution, samples)
    preparation = json.loads((evidence / "artifact/preparation.json").read_text(encoding="utf-8"))
    recognition = report["actual_transcribe_calls"][0]
    waveform = recognition["waveform"]
    require(waveform["sample_count"] == plan["fixture"]["sample_count"] and
            waveform["sha256"] == preparation["fixture"]["decoded_pcm_sha256"], "Original full PCM binding")
    timing = report["fixed_text_timing_calls"]
    require(len(timing) == 1 and timing[0]["completed"] and timing[0]["waveform"] == waveform and
            timing[0]["engine_identity"] == recognition["engine_identity"] == report["model_initializations"][0]["engine_identity"],
            "Same-engine full-input timing contract")
    require(recognition["effective_options"]["word_timestamps"] is False and recognition["generator_exhausted"], "Baseline recognition changed")
    require(timing[0]["raw_segments"] == [row for row in recognition["raw_segments"] if row["text"].strip()], "Native source tokens changed")
    require(len(report["native_align_calls"]) == len(report["timing_encode_calls"]) == 2 and
            all(row["completed"] and row["native_returned"] and row["contract_validated"] for row in report["native_align_calls"]),
            "Incomplete native alignment")
    baseline = report["actual_recognizer_calls"][0]["segments"]
    require(timing[0]["baseline_segments"] == baseline and timing[0]["segments"] == report["actual_speaker_calls"][0]["input_segments"],
            "Production timing-to-speaker binding")
    normalize = lambda rows: " ".join(" ".join(row["text"].split()) for row in rows)
    require(normalize(baseline) == normalize(report["record"]["segments"]) and report["recognized_words_preserved"], "Saved source text changed")
    require(all("_words" not in row for row in report["record"]["segments"]), "Private words leaked to storage")
    release = report["audio_model_release_calls"]
    require(len(release) == 1 and release[0]["options"] == {"recognizer_only": True} and
            release[0]["recognizer_references_released"] and release[0]["after"]["recognizer"] == 0 and
            report["actual_speaker_calls"][0]["recognizer_released_before_call"], "Recognizer lifetime contract")
    require(report["speaker_decode_calls"][0]["waveform"] == waveform and
            report["separate_process_sqlite"]["record"] == report["record"] and
            report["separate_process_sqlite"]["matches_saved_record"] and report["durable_download_after_job_eviction"],
            "Full speaker source or durable reload contract")
    # Reuse the unchanged predeclared acoustic score; references never enter inference.
    import numpy as np
    score = load_function(root / "source/original-acoustic-score.py", "score", {"np": np})
    case = {"id": "two_speakers_returning", "kind": "clean", "expected_speakers": 2,
            "reference_intervals": plan["fixture"]["reference_intervals"]}
    assessment = score(case, report["acoustic_analysis_calls"][0]["result"])
    require(assessment["status"] == "passed", "Original acoustic criteria failed")
    return {"schema_version": 1, "scope": "Offline correction of one constructor assertion on the retained actual hosted result",
            "binding_sha256": sha(binding_path), "head_sha": binding["head_sha"], "run_id": binding["run_id"],
            "original_github_conclusion": "failure", "original_execution_rewritten": False,
            "corrected_constructor_and_pipeline_contract_pass": True,
            "constructor_cpu_threads": report["model_initializations"][0]["cpu_threads"],
            "thread_limit_evidence": {"source_enforced_launch_affinity": execution["cpu_affinity"],
                "source_set_OMP_NUM_THREADS": "4", "source_set_MKL_NUM_THREADS": "4",
                "native_zero_meaning": "Use OMP_NUM_THREADS, otherwise native default min(4, hardware_concurrency)",
                "inference_side_affinity_readback_recorded": False, "effective_thread_count_measured": False},
            "resource_sample_count": len(samples), "sampled_group_peak_rss_bytes": execution["sampled_group_peak_rss_bytes"],
            "process_high_water_bytes": report["peak_process_rss_bytes"], "worker_seconds": report["elapsed_seconds"],
            "controller_seconds": execution["elapsed_seconds"], "owned_cleanup_pass": True,
            "controlled_fixture_acoustic_assessment": assessment,
            "broader_speaker_or_word_timing_accuracy_approved": False,
            "new_model_initializations_or_inference": 0,
            "limitations": binding["limitations"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Refusing to overwrite an existing audit")
    result = audit(args.bindings)
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, ensure_ascii=False)
        target.write("\n")
    print(json.dumps({"corrected_contract_pass": True, "original_github_conclusion": "failure",
                      "acoustic": result["controlled_fixture_acoustic_assessment"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
