"""Acquire only the approved safetensors, tokenizer and four pinned wheels once."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile

from common import HERE, RESEARCH, PLAN_SHA256, emit, read_plan, save, sha, utc, verify_freeze


def allocated(root):
    seen = set()
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            st = path.stat()
            key = (st.st_dev, st.st_ino)
            if key not in seen:
                seen.add(key)
                total += st.st_blocks * 512
    return total


def space_check(runtime, plan, remaining=0):
    free = shutil.disk_usage(runtime).free
    if free - remaining < plan["storage"]["minimum_free_reserve_bytes"]:
        raise ValueError("The fixed 1 GiB reserve would be breached.")
    used = allocated(runtime)
    if used + remaining > plan["storage"]["maximum_new_allocated_bytes"]:
        raise ValueError("The owned stage allocation allowance would be exceeded.")
    return {"free_bytes": free, "owned_allocated_bytes": used}


def download(item, destination, report, plan, runtime):
    part = destination.with_name(destination.name + ".partial")
    if destination.exists() or part.exists():
        raise ValueError("Refusing to repeat or overwrite an artifact download.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    space_check(runtime, plan, item["bytes"])
    record = {"filename": item["filename"], "url": item["url"], "expected_bytes": item["bytes"],
              "expected_sha256": item["sha256"], "attempts": 1, "complete": False, "received_bytes": 0,
              "destination": str(destination)}
    report["downloads"].append(record)
    save(HERE / "acquisition.json", report)
    digest = hashlib.sha256()
    started = time.monotonic()
    checkpoint = 0
    with urllib.request.urlopen(item["url"], timeout=60) as response, part.open("xb") as stream:
        record["status"] = response.status
        record["effective_host"] = urllib.parse.urlsplit(response.url).hostname
        while block := response.read(4 * 1024 * 1024):
            record["received_bytes"] += len(block)
            if record["received_bytes"] > item["bytes"]:
                raise ValueError("Artifact exceeds the fixed published size.")
            stream.write(block)
            digest.update(block)
            if record["received_bytes"] - checkpoint >= 64 * 1024 * 1024:
                record["elapsed_seconds"] = round(time.monotonic() - started, 3)
                record["space"] = space_check(runtime, plan)
                save(HERE / "acquisition.json", report)
                emit("download_progress", filename=item["filename"], bytes=record["received_bytes"])
                checkpoint = record["received_bytes"]
        stream.flush()
        os.fsync(stream.fileno())
    record["sha256"] = digest.hexdigest()
    if record["received_bytes"] != item["bytes"] or record["sha256"] != item["sha256"]:
        raise ValueError("Artifact size/hash verification failed.")
    part.replace(destination)
    record["saved_sha256"] = sha(destination)
    if record["saved_sha256"] != item["sha256"]:
        raise ValueError("Saved artifact differs from the verified stream.")
    record["complete"] = True
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    record["space"] = space_check(runtime, plan)
    save(HERE / "acquisition.json", report)


def main():
    plan = read_plan()
    verify_freeze("acquisition-freeze")
    runtime = Path(plan["runtime"]["owned_root"])
    if runtime.exists() or (HERE / "acquisition.json").exists():
        raise ValueError("Refusing to repeat the one owned acquisition stage.")
    if shutil.disk_usage(runtime.parent).free < plan["storage"]["minimum_free_before_start_bytes"]:
        raise ValueError("Insufficient space before the one download stage.")
    runtime.mkdir()
    (runtime / "private").mkdir(mode=0o700)
    (runtime / "tmp").mkdir()
    output = HERE / "acquisition.json"
    report = {"schema_version": 1, "started_at": utc(), "plan_sha256": PLAN_SHA256,
              "complete": False, "downloads": [], "initial_space": space_check(runtime, plan),
              "model_imports": 0, "detector_calls": 0, "translation_calls": 0,
              "cache_deletions": 0, "existing_environments_modified": False}
    save(output, report)
    started = time.monotonic()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("Bounded acquisition deadline.")))
    signal.alarm(plan["limits"]["download_stage_seconds"])
    try:
        payloads = [plan["model"], plan["backbone_tokenizer_payload"]]
        for item in payloads:
            download(item, runtime / "blobs" / ("sha256-" + item["sha256"]), report, plan, runtime)
        for item in plan["runtime"]["new_wheels"]:
            download(item, runtime / "wheels" / item["filename"], report, plan, runtime)
        wheel_paths = [runtime / "wheels" / item["filename"] for item in plan["runtime"]["new_wheels"]]
        expanded = sum(sum(entry.file_size for entry in zipfile.ZipFile(path).infolist()) for path in wheel_paths)
        report["wheel_uncompressed_bytes"] = expanded
        space_check(runtime, plan, expanded + 8 * 1024 * 1024)
        command = [plan["runtime"]["python"], "-m", "pip", "install", "--no-index", "--no-deps",
                   "--no-compile", "--target", plan["runtime"]["owned_package_target"], *map(str, wheel_paths)]
        log = runtime / "private/install.log"
        environment = os.environ.copy()
        environment.update({"PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_CACHE_DIR": "1",
                            "PYTHONNOUSERSITE": "1", "TMPDIR": str(runtime / "tmp")})
        environment.pop("PYTHONPATH", None)
        with log.open("xb") as stream:
            completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=environment,
                                       timeout=plan["limits"]["dependency_install_seconds"], check=False)
        report["installation_exit_code"] = completed.returncode
        if completed.returncode != 0:
            raise ValueError("Pinned isolated dependency installation failed; private log retained.")
        model = runtime / "model"
        model.mkdir()
        for item in payloads:
            os.link(runtime / "blobs" / ("sha256-" + item["sha256"]), model / item["filename"])
        for item in plan["source_support_files"]:
            shutil.copyfile(RESEARCH / item["evidence_name"], model / item["runtime_name"])
        report["layout"] = {}
        for path in sorted(model.iterdir()):
            st = path.stat()
            report["layout"][path.name] = {"bytes": st.st_size, "sha256": sha(path), "inode": st.st_ino,
                                         "device": st.st_dev, "allocated_bytes": st.st_blocks * 512,
                                         "hardlinks": st.st_nlink}
        report["final_space"] = space_check(runtime, plan)
        report["complete"] = True
    except BaseException as error:
        # Do not echo download exceptions containing signed URLs or proxy details.
        report["error"] = {"type": type(error).__name__, "message": "Acquisition/setup failed; private traceback retained."}
        import traceback
        (runtime / "private/acquisition-error.txt").write_text(traceback.format_exc())
    finally:
        signal.alarm(0)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["finished_at"] = utc()
        save(output, report)
    emit("acquisition_complete", complete=report["complete"], elapsed_seconds=report["elapsed_seconds"], report=str(output))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
