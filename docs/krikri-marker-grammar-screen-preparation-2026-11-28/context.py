"""Source-only bindings for the conditional original-six grammar screen."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / "docs/krikri-source-spelling-screen-2026-11-28"
GRAMMAR = ROOT / "docs/krikri-marker-grammar-preparation-2026-11-28"
NATIVE = ROOT / "docs/krikri-marker-grammar-build-continuation-2026-11-28"
PRIVATE = Path("/workspace/scratch/94360995dd61/linkscribe-krikri-runtime/marker-grammar-screen")

# Reuse the closed source-spelling runtime helpers; importing them does not load
# a model, tokenize or make a request. Their original file bindings are retained.
_spec = importlib.util.spec_from_file_location("grammar_screen_prior_context", PRIOR / "context.py")
_prior = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_prior)
common = _prior.common
cache_identity = _prior.cache_identity
native_preflight = _prior.native_preflight
stop_daemon = _prior.stop_daemon
# These modules keep their original file paths and therefore their original
# source-only normalizer/projection dependencies. No local copies are substituted.
sys.path.append(str(PRIOR))
sys.path.insert(0, str(HERE))


def read_plan():
    _prior.read_plan()
    path = HERE / "plan.json"
    if common.sha(path) != (HERE / "plan.sha256").read_text(encoding="utf-8").strip():
        raise ValueError("The separately frozen grammar-screen plan changed.")
    plan = json.loads(path.read_text(encoding="utf-8"))
    for relative, expected in plan["source_sha256"].items():
        if common.sha(ROOT / relative) != expected:
            raise ValueError("Frozen grammar-screen source changed: " + relative)
    previous = json.loads((PRIOR / "plan.json").read_text(encoding="utf-8"))
    for key in ("model", "runtime", "python_runtime", "native_setup", "limits", "evaluation"):
        if plan[key] != previous[key]:
            raise ValueError("The grammar-only screen changed the original " + key + ".")
    return plan


def storage_reserve():
    available = shutil.disk_usage(HERE).free
    if available < 1024 ** 3:
        raise ValueError("The unchanged 1 GiB free disk reserve is unavailable.")
    return available


def utc():
    return datetime.now(timezone.utc).isoformat()
