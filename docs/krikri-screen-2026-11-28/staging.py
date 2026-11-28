#!/usr/bin/env python3
"""One authorized rejected-payload cleanup and pinned Krikri download."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
import urllib.parse
import urllib.request
import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORIGINAL = ROOT / "docs/gemma4-screen-2026-11-28"
sys.path.insert(0, str(ORIGINAL))
import experiment as common


def read_plan():
    if common.sha(HERE / "plan.json") != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("The pre-cleanup/download plan changed.")
    plan = json.loads((HERE / "plan.json").read_text())
    for rel, expected in plan["source_sha256"].items():
        if common.sha(ROOT / rel) != expected:
            raise ValueError("Frozen source changed: " + rel)
    for rel, expected in plan["runtime"]["files_sha256"].items():
        if common.sha(Path(plan["runtime"]["directory"]) / rel) != expected:
            raise ValueError("The verified native runtime changed: " + rel)
    return plan


def check_owned_gemma_stopped(plan):
    reports = []
    for rel in plan["cleanup"]["stopped_process_reports"]:
        data = json.loads((ROOT / rel).read_text())
        if data.get("owned_process_group_stopped") is not True or data.get("worker_exit_code") != 0:
            raise ValueError("A previous owned Gemma process group is not confirmed stopped.")
        reports.append({"report": rel, "sha256": common.sha(ROOT / rel),
                        "owned_process_group_stopped": True, "worker_exit_code": 0})
    conflicts = []
    target = plan["cleanup"]["exact_payload_path"]
    cache_directory = str(Path(target).parents[2])
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            args = process.info["cmdline"] or []
            name = process.info["name"] or ""
            if name in {"ollama", "llama-server"} and any(target in a or cache_directory in a for a in args):
                conflicts.append({"pid": process.pid, "name": name})
            if any(f.path == target for f in process.open_files()):
                conflicts.append({"pid": process.pid, "name": name, "open_payload": True})
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise ValueError("Cannot complete the accessible-process payload check.") from exc
    if conflicts:
        raise ValueError("An accessible process still owns the rejected Gemma payload.")
    return {"prior_owned_supervisor_exit_evidence": reports,
            "accessible_namespace_conflicts": conflicts,
            "scope": "Prior owned sessions exited and their supervisors confirm cleanup; current accessible PID namespace also checked. Other PID namespaces are not claimed visible.",
            "coordination": "Root reserved the local model slot; no other owned Gemma inference is queued."}


def cleanup(plan, report, output):
    item = plan["cleanup"]
    path = Path(item["exact_payload_path"])
    if str(path.resolve()) != item["exact_payload_path"] or path.is_symlink():
        raise ValueError("The specifically authorized payload is not the exact regular path.")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size != item["bytes"] or before.st_nlink != 1:
        raise ValueError("The rejected payload size/type/link identity changed.")
    report["process_check"] = check_owned_gemma_stopped(plan)
    report["space_before_bytes"] = shutil.disk_usage(path.parent).free
    report["payload_before"] = {"path": str(path), "bytes": before.st_size, "allocated_bytes": before.st_blocks * 512,
                                "inode": before.st_ino, "device": before.st_dev, "hardlinks": before.st_nlink}
    report["verified_full_sha256"] = common.sha(path)
    if report["verified_full_sha256"] != item["sha256"]:
        raise ValueError("The complete rejected model hash does not match the authorization.")
    current = path.stat()
    if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns):
        raise ValueError("Payload changed between identity verification and unlink.")
    report["ready_for_exact_unlink"] = True
    common.save(output, report)
    path.unlink()
    report["unlinked_exact_path"] = str(path)
    report["path_absent_after"] = not path.exists()
    report["space_after_bytes"] = shutil.disk_usage(path.parent).free
    report["free_bytes_change"] = report["space_after_bytes"] - report["space_before_bytes"]
    report["preserved"] = "Every evidence/template/config/manifest/script file and every shared runtime/model cache; only this authorized payload path was unlinked."
    report["complete"] = report["path_absent_after"]


def download_one(item, destination, report, output):
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    if destination.exists() or partial.exists():
        raise ValueError("Refusing to repeat or overwrite a download.")
    record = {"name": item["filename"], "url": item["url"], "destination": str(destination),
              "expected_bytes": item["bytes"], "expected_sha256": item["sha256"],
              "complete": False, "bytes_received": 0, "attempts": 1}
    report["downloads"].append(record)
    common.save(output, report)
    digest = hashlib.sha256()
    started = time.monotonic()
    checkpoint_bytes = 0
    with urllib.request.urlopen(item["url"], timeout=60) as response, partial.open("xb") as stream:
        record["http_status"] = response.status
        record["effective_host"] = urllib.parse.urlsplit(response.url).hostname
        record["content_length"] = response.headers.get("Content-Length")
        while block := response.read(4 * 1024 * 1024):
            record["bytes_received"] += len(block)
            if record["bytes_received"] > item["bytes"]:
                raise ValueError("The download exceeds its fixed published size.")
            stream.write(block)
            digest.update(block)
            if record["bytes_received"] - checkpoint_bytes >= 64 * 1024 * 1024:
                record["elapsed_seconds"] = round(time.monotonic() - started, 3)
                common.save(output, report)
                checkpoint_bytes = record["bytes_received"]
        stream.flush()
        os.fsync(stream.fileno())
    record["received_sha256"] = digest.hexdigest()
    if record["bytes_received"] != item["bytes"] or record["received_sha256"] != item["sha256"]:
        raise ValueError("The original downloaded payload fails its full size/hash identity.")
    partial.replace(destination)
    record["saved_sha256"] = common.sha(destination)
    if record["saved_sha256"] != item["sha256"]:
        raise ValueError("The saved payload hash differs from the received original.")
    details = destination.stat()
    record.update({"complete": True, "elapsed_seconds": round(time.monotonic() - started, 3),
                   "saved_bytes": details.st_size, "allocated_bytes": details.st_blocks * 512,
                   "inode": details.st_ino, "hardlinks": details.st_nlink})
    common.save(output, report)


def download(plan, runtime, report, output):
    prior = json.loads((HERE / "cleanup.json").read_text())
    if not prior.get("complete") or prior.get("unlinked_exact_path") != plan["cleanup"]["exact_payload_path"]:
        raise ValueError("The authorized storage preparation has not completed.")
    needed = plan["model"]["bytes"] + plan["tokenizer_reference"]["bytes"] + plan["storage"]["reserve_bytes"]
    report["free_before_bytes"] = shutil.disk_usage(runtime).free
    report["required_payloads_plus_reserve_bytes"] = needed
    if report["free_before_bytes"] < needed:
        raise ValueError("Insufficient disk for the single original payload, tokenizer reference and reserve.")
    report["downloads"] = []
    download_one(plan["model"], runtime / "models/blobs" / ("sha256-" + plan["model"]["sha256"]), report, output)
    download_one(plan["tokenizer_reference"], runtime / "reference-tokenizer/tokenizer.json", report, output)
    report["free_after_bytes"] = shutil.disk_usage(runtime).free
    if report["free_after_bytes"] < plan["storage"]["reserve_bytes"]:
        raise ValueError("Working disk reserve was lost during the download.")
    report["complete"] = all(x["complete"] for x in report["downloads"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("cleanup", "download"), required=True)
    args = parser.parse_args()
    plan = read_plan()
    runtime = Path(plan["storage"]["owned_runtime_directory"])
    runtime.mkdir(parents=True, exist_ok=True)
    output = HERE / (args.action + ".json")
    if output.exists():
        raise ValueError("Refusing to repeat retained storage preparation evidence.")
    report = {"schema_version": 1, "action": args.action, "started_at": datetime.now(timezone.utc).isoformat(),
              "plan_sha256": common.sha(HERE / "plan.json"), "complete": False, "generation_calls": 0}
    common.save(output, report)
    try:
        if args.action == "cleanup":
            cleanup(plan, report, output)
        else:
            download(plan, runtime, report, output)
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        report["complete"] = False
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
        report["complete"] &= report["frozen_inputs_unchanged"]
        common.save(output, report)
    common.event("phase_complete", phase=args.action, complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
