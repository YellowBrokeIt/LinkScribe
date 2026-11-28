"""Frozen paths, receipts and disk policy; no native side effects on import."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE_PLAN = ROOT / "docs/krikri-marker-grammar-native-plan-2026-11-28"
GRAMMAR_PREP = ROOT / "docs/krikri-marker-grammar-preparation-2026-11-28"
PRIOR = ROOT / "docs/krikri-source-spelling-screen-2026-11-28"
OWNED = Path("/workspace/scratch/94360995dd61/linkscribe-grammar-validator-runtime")
PHASES = ("build", "native_prepare", "validate")
PHASE_KEYS = {"acquire": "acquire", "build": "build-and-sanity", "native_prepare": "native-prepare",
              "validate": "validate-emitted-grammars"}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            result.update(block)
    return result.hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON property: " + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Invalid JSON constant: " + value)
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def read(path):
    return strict_json(Path(path).read_bytes())


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


common = SimpleNamespace(save=save, sha=sha)


def event(name, **fields):
    print("GEMMA_EVENT " + json.dumps({"event": name, **fields}, ensure_ascii=False, allow_nan=False), flush=True)


def record(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def verify_files(bindings):
    for relative, expected in bindings.items():
        path = ROOT / relative
        if path.is_symlink() or sha(path) != expected:
            raise ValueError("Frozen source changed: " + relative)


def read_plan():
    if sha(HERE / "plan.json") != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("Controller preparation plan changed.")
    plan = read(HERE / "plan.json")
    verify_files(plan["source_sha256"])
    native = read(NATIVE_PLAN / "plan.json")
    verify_files(native["source_sha256"])
    if (plan["native_plan_sha256"] != sha(NATIVE_PLAN / "plan.json")
            or native["owned_build_root"] != str(OWNED)):
        raise ValueError("The reviewed tiny native setup plan differs.")
    return plan, native


def verify_tools(extra=()):
    metadata = read(NATIVE_PLAN / "retained-binary-metadata.json")
    for item in [*metadata["files"], *extra]:
        path = Path(item["path"])
        if (str(path.resolve()) != item["resolved"] or path.stat().st_size != item["bytes"]
                or sha(path) != item["sha256"]):
            raise ValueError("A retained compiler or native/system library changed: " + item["path"])
    return metadata


def source_objects(capsule, inventory):
    if (capsule.get("revision") != inventory["revision"]
            or capsule.get("repository") != inventory["repository"]
            or not isinstance(capsule.get("files"), list)
            or [row.get("path") for row in capsule["files"]] != [row["path"] for row in inventory["files"]]):
        raise ValueError("Official source capsule does not match the exact ordered allowlist.")
    output = []
    for row, expected in zip(capsule["files"], inventory["files"]):
        path = PurePosixPath(row["path"])
        if path.is_absolute() or any(part in {"..", "."} for part in path.parts):
            raise ValueError("Source acquisition path is not a safe relative file.")
        body = row["content"].encode("utf-8")
        git = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
        if (len(body) != expected["bytes"] or git != expected["git_blob_sha1"]
                or row["bytes"] != len(body) or row["git_blob_sha1"] != git):
            raise ValueError("Official source content differs from its pinned Git object: " + str(path))
        output.append({"path": str(path), "body": body, "bytes": len(body), "git_blob_sha1": git,
                       "sha256": hashlib.sha256(body).hexdigest(), "source_url": row["source_url"]})
    if len(output) != inventory["file_count"] or sum(row["bytes"] for row in output) != inventory["total_bytes"]:
        raise ValueError("Official source file or byte total differs.")
    return output


def storage_policy(owned=OWNED, reserve_bytes=1024**3, maximum_tree_bytes=64*1024**2,
                   maximum_file_bytes=16*1024**2):
    """Sample the owned tree; per-process RLIMIT_FSIZE also bounds writes."""
    owned = Path(owned)
    free = shutil.disk_usage(owned.parent).free
    total, count, largest = 0, 0, 0
    violation = "disk_free_reserve" if free < reserve_bytes else None
    if owned.is_symlink():
        violation = "owned_tree_symlink"
    elif owned.exists():
        for directory, dirs, files in os.walk(owned, followlinks=False):
            for name in dirs + files:
                path = Path(directory) / name
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    continue  # A compiler temporary may disappear during a sample.
                if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                    violation = "nonregular_owned_tree_entry"
                if stat.S_ISREG(info.st_mode):
                    count += 1; total += info.st_size; largest = max(largest, info.st_size)
                    if info.st_size > maximum_file_bytes:
                        violation = "owned_file_size_limit"
        if total > maximum_tree_bytes:
            violation = "owned_tree_size_limit"
    return {"free_bytes": free, "reserve_bytes": reserve_bytes, "tree_bytes": total,
            "file_count": count, "largest_file_bytes": largest,
            "maximum_tree_bytes": maximum_tree_bytes, "maximum_file_bytes": maximum_file_bytes,
            "violation": violation, "sampling_scope": "Owned build tree; free disk includes unrelated filesystem users."}


def require_storage():
    value = storage_policy()
    if value["violation"]:
        raise ValueError("Storage policy failed: " + value["violation"])
    return value


def phase_limits(native, phase, completed_elapsed, phase_elapsed=0.0):
    specification = next(row for row in native["phases"] if row["name"] == PHASE_KEYS[phase])
    remaining = native["aggregate_seconds"] - completed_elapsed
    phase_remaining = specification["seconds"] - phase_elapsed
    if remaining <= 0 or phase_remaining <= 0:
        raise ValueError("Aggregate active-phase time budget exhausted.")
    return {"rss_bytes": specification["rss_mib"] * 1024**2,
            "total_seconds": min(phase_remaining, remaining),
            "initialization_seconds": specification.get("initialization_seconds", specification["seconds"]),
            "case_seconds": 2 if phase == "validate" else specification["seconds"]}
