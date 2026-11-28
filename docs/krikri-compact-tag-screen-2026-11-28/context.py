"""Pinned native model reuse and isolated source-protection stage bindings."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "docs/krikri-screen-2026-11-28"
sys.path.insert(0, str(BASE))
import staging as baseline
from native_verify import cache_identity, native_preflight

common = baseline.common
PRIVATE = Path("/workspace/scratch/94360995dd61/linkscribe-krikri-runtime/compact-tag-screen")


def read_plan():
    baseline.read_plan()
    path = HERE / "plan.json"
    if common.sha(path) != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("The pre-output source-protection plan changed.")
    plan = json.loads(path.read_text())
    for rel, expected in plan["source_sha256"].items():
        if common.sha(ROOT / rel) != expected:
            raise ValueError("Frozen source changed: " + rel)
    for directory in plan["immutable_prior_directories"]:
        base = ROOT / directory
        manifest = json.loads((base / "evidence-manifest.json").read_text())
        for row in manifest["files"]:
            path = base / row["path"]
            if path.stat().st_size != row["bytes"] or common.sha(path) != row["sha256"]:
                raise ValueError("Prior immutable evidence changed: " + str(path))
    if plan["model"] != json.loads((BASE / "plan.json").read_text())["model"]:
        raise ValueError("This development stage changes the frozen model.")
    return plan


def storage_reserve():
    available = shutil.disk_usage(HERE).free
    if available < 1024 ** 3:
        raise ValueError("The required 1 GiB free disk reserve is unavailable.")
    return available


def stop_daemon(process):
    """Stop only this actual daemon/descendants; outer monitor owns its group."""
    try:
        parent = psutil.Process(process.pid)
        owned = [parent, *parent.children(recursive=True)]
    except psutil.NoSuchProcess:
        owned = []
    for item in reversed(owned):
        try:
            item.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owned, timeout=3)
    for item in alive:
        try:
            item.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(alive, timeout=3)
    process.wait(timeout=3)
    return not [p for p in alive if p.is_running() and p.status() != psutil.STATUS_ZOMBIE]


def utc():
    return datetime.now(timezone.utc).isoformat()
