"""Small evidence helpers for the single source-only detector screen."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent / "name-span-protection-research-2026-11-28"
PLAN_SHA256 = "1a56796eb75a709c9231354ff17ca7b9f23be9988e3ddbc30ba0492433b2b9d5"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def emit(event, **data):
    print("PERSON_EVENT " + json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def read_plan():
    path = RESEARCH / "detector-screen-plan.json"
    if sha(path) != PLAN_SHA256:
        raise ValueError("The frozen detector plan changed.")
    plan = json.loads(path.read_text())
    for name, identity in plan["bound_research_files"].items():
        file = RESEARCH / name
        if file.stat().st_size != identity["bytes"] or sha(file) != identity["sha256"]:
            raise ValueError("Frozen research/source changed: " + name)
    return plan


def verify_freeze(name):
    path = HERE / (name + ".json")
    if sha(path) != (HERE / (name + ".sha256")).read_text().strip():
        raise ValueError("Phase freeze changed: " + name)
    freeze = json.loads(path.read_text())
    if freeze["plan_sha256"] != PLAN_SHA256 or freeze["independent_protocol_approved"] is not True:
        raise ValueError("The exact plan lacks an independent protocol approval.")
    for path, expected in freeze["files_sha256"].items():
        if sha(path) != expected:
            raise ValueError("Frozen phase input changed: " + path)
    return freeze


def model_files(plan):
    runtime = Path(plan["runtime"]["owned_root"])
    directory = runtime / "model"
    identities = {
        "model.safetensors": plan["model"]["sha256"],
        "spm.model": plan["backbone_tokenizer_payload"]["sha256"],
        **{item["runtime_name"]: item["sha256"] for item in plan["source_support_files"]},
    }
    if sorted(p.name for p in directory.iterdir()) != sorted(identities):
        raise ValueError("Unexpected or missing local model file.")
    for name, expected in identities.items():
        if sha(directory / name) != expected:
            raise ValueError("The pinned local model file changed: " + name)
    return directory, identities
