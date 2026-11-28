"""One measured native Krikri import/load/render-only preparation; no generation."""
from __future__ import annotations
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess

from staging import HERE, ROOT, common, read_plan
from native_verify import cache_identity, inspect_header, native_preflight


def verify_freeze():
    path = HERE / "native-preparation-freeze.json"
    if common.sha(path) != (HERE / "native-preparation-freeze.sha256").read_text().strip():
        raise ValueError("Native preparation freeze changed.")
    freeze = json.loads(path.read_text())
    for rel, expected in freeze["files_sha256"].items():
        if common.sha(ROOT / rel) != expected:
            raise ValueError("Frozen native preparation input changed: " + rel)


def main():
    verify_freeze()
    plan = read_plan()
    runtime = Path(plan["storage"]["owned_runtime_directory"])
    output = HERE / "prepare.json"
    if output.exists():
        raise ValueError("Refusing to repeat native model preparation.")
    report = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "generation_calls": 0, "plan_sha256": common.sha(HERE / "plan.json"),
              "native_preparation_freeze_sha256": common.sha(HERE / "native-preparation-freeze.json")}
    common.save(output, report)
    process = None
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("External supervisor stopped preparation.")))
    try:
        common.verify_blob(runtime, plan)
        blob = common.model_blob(runtime, plan)
        reference = runtime / "reference-tokenizer/tokenizer.json"
        if common.sha(reference) != plan["tokenizer_reference"]["sha256"]:
            raise ValueError("Publisher tokenizer reference changed.")
        report["header"] = inspect_header(blob, reference, plan)
        common.save(HERE / "selected-gguf-header.json", report["header"])
        common.save(output, report)
        gc.collect()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 11434))
        fd = os.open(runtime / "prepare-daemon-private.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as log:
            process = subprocess.Popen([str(Path(plan["runtime"]["directory"]) / "bin/ollama"), "serve"],
                                       env=common.daemon_environment(runtime), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            report["runtime"] = common.ready(process)
            if report["runtime"].get("version") != plan["runtime"]["version"]:
                raise ValueError("Runtime version differs from the pinned release.")
            before = blob.stat()
            report["storage_before_import"] = {"free_bytes": shutil.disk_usage(runtime).free, "payload_inode": before.st_ino,
                                               "allocated_bytes": before.st_blocks * 512, "hardlinks": before.st_nlink}
            if report["storage_before_import"]["free_bytes"] < plan["storage"]["reserve_bytes"]:
                raise ValueError("Native import would begin without the fixed disk reserve.")
            body = {"model": plan["model"]["local_name"], "stream": False,
                    "files": {plan["model"]["filename"]: "sha256:" + plan["model"]["sha256"]},
                    "parameters": plan["native_setup"]["import_parameters"],
                    "license": (HERE / "model-license.txt").read_text()}
            report["create_request"] = body
            common.save(output, report)
            common.event("import_start")
            report["create_response"] = common.api("/api/create", body, timeout=180)
            report["cache"] = cache_identity(runtime, plan)
            after = blob.stat()
            all_allocated = sum(p.stat().st_blocks * 512 for p in (runtime / "models/blobs").iterdir() if p.is_file())
            report["storage_after_import"] = {"free_bytes": shutil.disk_usage(runtime).free, "payload_inode": after.st_ino,
                                              "allocated_bytes": after.st_blocks * 512, "hardlinks": after.st_nlink,
                                              "all_blob_allocated_bytes": all_allocated}
            if (before.st_ino != after.st_ino or before.st_blocks != after.st_blocks or
                    all_allocated - after.st_blocks * 512 > 16 * 1024 * 1024 or
                    report["storage_after_import"]["free_bytes"] < plan["storage"]["reserve_bytes"]):
                raise ValueError("Import duplicated the payload or lost the working disk reserve.")
            report["show"] = common.api("/api/show", {"model": plan["model"]["local_name"]})
            report["tags"] = common.api("/api/tags")
            if report["show"].get("system", "") or report["show"].get("details", {}).get("quantization_level") != "Q4_K_M":
                raise ValueError("Native imported model has a persona or unexpected quantization.")
            common.save(output, report)
            common.event("import_complete", manifest_sha256=report["cache"]["manifest_sha256"])
            cases = json.loads((HERE / "development-cases.json").read_text())["cases"]
            expected = json.loads((HERE / "expected-requests.json").read_text())
            report["prompts"] = []
            for case, request in zip(cases, expected):
                if case["id"] != request["id"]:
                    raise ValueError("Declared request/case order differs.")
                value = native_preflight(request["request"], case, process, plan, report["header"])
                if not report["prompts"]:
                    common.event("case_start", id="native-render-only-setup", generation_calls=0)
                report["prompts"].append(value)
                common.save(output, report)
            report["unload_response"] = common.api("/api/chat", {"model": plan["model"]["local_name"], "messages": [], "keep_alive": 0, "stream": False})
            report["resident_after_unload"] = common.api("/api/ps")
            if report["unload_response"].get("done_reason") != "unload" or report["resident_after_unload"].get("models") != []:
                raise ValueError("Native render-only preparation did not unload cleanly.")
            report["complete"] = True
            common.event("case_complete", id="native-render-only-setup", generation_calls=0,
                         prompt_token_counts=[p["prompt_tokens"] for p in report["prompts"]])
    except BaseException as error:
        report["complete"] = False
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if process is not None:
            common.stop_owned(process)
            report["owned_daemon_stopped"] = process.poll() is not None
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
        report["complete"] &= report["frozen_inputs_unchanged"]
        common.save(output, report)
    common.event("phase_complete", phase="prepare", complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
