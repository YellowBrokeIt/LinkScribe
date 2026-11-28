"""Frozen baseline reuse and new instruction-only experiment bindings."""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "docs/krikri-screen-2026-11-28"
sys.path.insert(0, str(BASE))
import staging as baseline
from native_verify import cache_identity, native_preflight

common = baseline.common
PRIVATE = Path("/workspace/scratch/94360995dd61/linkscribe-krikri-runtime/name-preservation")


def read_plan():
    baseline.read_plan()
    path = HERE / "plan.json"
    if common.sha(path) != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("The pre-preparation instruction-only plan changed.")
    plan = json.loads(path.read_text())
    for rel, expected in plan["source_sha256"].items():
        if common.sha(ROOT / rel) != expected:
            raise ValueError("Frozen source changed: " + rel)
    manifest = json.loads((BASE / "evidence-manifest.json").read_text())
    for row in manifest["files"]:
        if (BASE / row["path"]).stat().st_size != row["bytes"] or common.sha(BASE / row["path"]) != row["sha256"]:
            raise ValueError("Retained failed baseline changed: " + row["path"])
    if plan["model"] != json.loads((BASE / "plan.json").read_text())["model"]:
        raise ValueError("The proposed instruction-only experiment changes the model.")
    return plan
