"""Archive completed evidence only; never execute candidate/native artifacts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
OWNED = WORKSPACE / "linkscribe-grammar-validator-runtime"
V2 = ROOT / "docs/krikri-marker-grammar-controller-v2-2026-11-28"
CONTINUATION = ROOT / "docs/krikri-marker-grammar-build-continuation-2026-11-28"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    archive = HERE / "complete-execution-evidence.zip"
    if archive.exists() or (HERE / "archive-members.json").exists():
        raise ValueError("Do not overwrite a retained execution snapshot.")
    required_plans = [(V2, "edc16c0a14699c38bb7cd1916f5118d6778958cd708f0fbca920720ebc0d8c00"),
                      (CONTINUATION, "d2a00e31038f43cebb643980826767c8322fd84883cfa327b7511a7ad2701652")]
    for directory, expected in required_plans:
        if sha(directory / "plan.json") != expected:
            raise ValueError("A frozen executed plan changed.")
        for path, digest in read(directory / "plan.json")["source_sha256"].items():
            if sha(ROOT / path) != digest:
                raise ValueError("A frozen execution input changed: " + path)
    native = read(CONTINUATION / "native_prepare.json")
    validated = read(CONTINUATION / "validate.json")
    if (native.get("complete") is not True or validated.get("complete") is not True
            or native.get("owned_daemon_stopped") is not True
            or native.get("unload_response", {}).get("done_reason") != "unload"
            or native.get("resident_after_unload", {}).get("models") != []
            or validated.get("candidate_probe_count") != 285
            or validated.get("all_candidate_expectations_match") is not True):
        raise ValueError("The native/validator stage is not complete and unloaded.")

    # The daemon inherited only the reviewed controller environment. Verify the
    # recorded startup map has no nonempty proxy/credential field before copying
    # the original log. Preserve its exact bytes; do not silently redact evidence.
    log = Path(native["private_daemon_log"]["path"])
    if sha(log) != native["private_daemon_log"]["sha256"]:
        raise ValueError("Private daemon log changed.")
    text = log.read_text()
    config_lines = [line for line in text.splitlines() if "server config" in line or "env=" in line]
    if len(config_lines) != 1 or "map[" not in config_lines[0]:
        raise ValueError("Startup environment record is not the reviewed single map.")
    payload = config_lines[0].split("map[", 1)[1]
    fields = list(re.finditer(r"(?<!\S)([A-Z][A-Z0-9_]*):", payload))
    sensitive_fields = []
    for index, match in enumerate(fields):
        if re.search(r"PROXY|TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|ACCESS_KEY|CREDENTIAL", match.group(1)):
            value = payload[match.end():fields[index + 1].start() if index + 1 < len(fields) else len(payload)].strip().rstrip(']"')
            sensitive_fields.append({"key": match.group(1), "nonempty": bool(value)})
    credential_pattern = re.compile(r"(?i)(bearer\s+[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{16,}|https?://[^\s:/]+:[^\s@]+@)")
    if any(row["nonempty"] for row in sensitive_fields) or credential_pattern.search(text):
        raise ValueError("Private log requires an explicit publication decision; do not copy secrets.")
    privacy = {"scope": "Actual reviewed startup environment map and credential-like pattern check; no environment values reproduced here.",
               "log_sha256": sha(log), "sensitive_field_presence": sensitive_fields,
               "credential_like_match": False, "raw_log_preserved_exactly": True,
               "redactions_or_omitted_owned_files": 0}

    origins = [("owned-runtime", OWNED), ("controllers/v2", V2),
               ("controllers/continuation", CONTINUATION),
               ("reviews/actual-build-sanity", WORKSPACE / "grammar-continuation-build-result-independent-review-2026-11-28"),
               ("reviews/actual-native-validation", WORKSPACE / "grammar-native-prepare-independent-review-2026-11-28")]
    entries = []
    omitted_bytecode = []
    for prefix, source in origins:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                if prefix == "owned-runtime":
                    raise ValueError("Unexpected bytecode in the complete owned execution tree.")
                omitted_bytecode.append(str(path)); continue
            info = path.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError("Evidence tree contains a symlink or special file: " + str(path))
            member = str(PurePosixPath(prefix) / relative.as_posix())
            if PurePosixPath(member).is_absolute() or ".." in PurePosixPath(member).parts:
                raise ValueError("Unsafe archive member name.")
            is_dir = path.is_dir()
            entries.append({"member": member + ("/" if is_dir else ""),
                "kind": "directory" if is_dir else "file", "source_path": str(path),
                "bytes": 0 if is_dir else info.st_size,
                "sha256": None if is_dir else sha(path), "mode": stat.S_IMODE(info.st_mode)})
    if len({row["member"] for row in entries}) != len(entries):
        raise ValueError("Duplicate archive member.")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for row in entries:
            path = Path(row["source_path"])
            if row["kind"] == "file":
                content = path.read_bytes()
                if len(content) != row["bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
                    raise ValueError("Source changed while snapshotting: " + str(path))
                if row["member"].startswith("owned-runtime/") and path.suffix not in {".so", ".bin"} and credential_pattern.search(content.decode("utf-8", errors="ignore")):
                    raise ValueError("Possible credential-like raw evidence requires review before publication.")
                info = zipfile.ZipInfo.from_file(path, arcname=row["member"])
                info.compress_type = zipfile.ZIP_DEFLATED
                zipped.writestr(info, content, compresslevel=6)
            else:
                zipped.write(path, row["member"])
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None or zipped.namelist() != [row["member"] for row in entries]:
            raise ValueError("Archive CRC or exact member inventory failed.")
        for row in entries:
            info = zipped.getinfo(row["member"])
            raw = zipped.read(row["member"])
            if len(raw) != row["bytes"] or (row["kind"] == "file" and hashlib.sha256(raw).hexdigest() != row["sha256"]):
                raise ValueError("Archive member differs: " + row["member"])
            row["zip_crc32"] = f"{info.CRC:08x}"
            if row["kind"] == "file" and sha(Path(row["source_path"])) != row["sha256"]:
                raise ValueError("Live source changed before snapshot verification completed.")

    phases = []
    readable = HERE / "phase-reports"; readable.mkdir()
    for label, directory, names in [("v2", V2, ["acquire", "build"]),
                                    ("continuation", CONTINUATION, ["build", "native_prepare", "validate"])]:
        for phase in names:
            report = read(directory / (phase + ".json"))
            resources = read(directory / (phase + "-resources.json"))
            if (resources["phase_report_sha256"] != sha(directory / (phase + ".json"))
                    or resources["samples_sha256"] != sha(directory / resources["samples_file"])
                    or not resources["owned_processes_stopped"]):
                raise ValueError("Phase report/sample/cleanup binding differs.")
            for suffix in [".json", "-resources.json"]:
                shutil.copyfile(directory / (phase + suffix), readable / (label + "-" + phase + suffix))
            phases.append({"stage": label, "phase": phase, "passed": resources["passed"],
                "report_sha256": sha(directory / (phase + ".json")),
                "resources_sha256": sha(directory / (phase + "-resources.json")),
                "samples_sha256": resources["samples_sha256"], "samples": resources["sample_count"],
                "elapsed_seconds": resources["elapsed_seconds"], "peak_rss_mib": resources["peak_rss_mib"],
                "peak_pss_mib": resources["peak_pss_mib"],
                "active_aggregate_seconds": resources["active_aggregate_seconds"],
                "owned_cleanup": resources["owned_processes_stopped"], "error": report.get("error")})
    inventory = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "archive": {"path": archive.name, "bytes": archive.stat().st_size, "sha256": sha(archive)},
        "scope": "Complete owned execution tree, exact v2 and continuation records/sources, and completed actual-build independent review. No generation experiment.",
        "source_roots": [{"archive_prefix": prefix, "path": str(source)} for prefix, source in origins],
        "member_count": len(entries), "file_count": sum(row["kind"] == "file" for row in entries),
        "uncompressed_file_bytes": sum(row["bytes"] for row in entries),
        "non_owned_bytecode_excluded": omitted_bytecode, "members": entries,
        "complete_owned_tree_preserved": True, "full_crc_inventory_and_sha_roundtrip_verified": True}
    save_new(HERE / "archive-members.json", inventory)
    save_new(HERE / "privacy-review.json", privacy)
    save_new(HERE / "phase-summary.json", {"schema_version": 1, "phases": phases,
        "candidate_probes": 285, "all_candidate_probes_matched": True,
        "unsupported_sentinel_gate_rejects": validated["sentinel"]["enforcement_gate_rejects"],
        "generation_calls": 0, "semantic_quality_not_evaluated": True})
    print({"archive_sha256": sha(archive), "archive_bytes": archive.stat().st_size,
           "inventory_sha256": sha(HERE / "archive-members.json"), "files": inventory["file_count"],
           "member_count": len(entries), "uncompressed_bytes": inventory["uncompressed_file_bytes"]})


if __name__ == "__main__":
    main()
