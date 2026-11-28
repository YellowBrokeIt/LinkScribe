"""Install the actual candidate source archive in a fresh Linux directory.

This optional acceptance check uses only the standard library itself. The
archive's unchanged start_linux.sh creates a new venv and installs the real app
dependencies. This is source-distribution evidence, not a standalone installer,
speech accuracy, or optional-model quality check.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import signal
import socket
import stat
import subprocess
import tempfile
import time
import urllib.request
import zipfile


ARCHIVE_NAME = "LinkScribe-candidate-source.zip"
BASE_URL = "http://127.0.0.1:8765"
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_BYTES = 300 * 1024 * 1024


def extract_candidate(artifact_dir: Path, destination: Path,
                      expected_commit: str, repository: str) -> dict:
    """Validate provenance and every member before writing any archive content."""
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise ValueError("Expected commit must be a full Git SHA.")
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Candidate manifest must be an object.")
    for key, expected in (("repository", repository), ("commit", expected_commit),
                          ("artifact", ARCHIVE_NAME)):
        if manifest.get(key) != expected:
            raise ValueError(f"Candidate manifest {key} does not match the expected source.")
    archive = artifact_dir / ARCHIVE_NAME
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Candidate archive exceeds the verification size limit.")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if manifest.get("sha256") != digest:
        raise ValueError("Candidate archive SHA-256 does not match its manifest.")
    if any(destination.iterdir()):
        raise ValueError("Candidate extraction requires an empty destination.")
    with zipfile.ZipFile(archive) as bundle:
        if bundle.comment != expected_commit.encode("ascii"):
            raise ValueError("Git archive commit comment does not match the expected source.")
        members = bundle.infolist()
        if not members or len(members) > 2000:
            raise ValueError("Candidate archive has an invalid member count.")
        if sum(item.file_size for item in members) > MAX_EXTRACTED_BYTES:
            raise ValueError("Candidate archive exceeds the extraction size limit.")
        names: set[str] = set()
        files: set[str] = set()
        for item in members:
            name = item.filename
            path = PurePosixPath(name)
            mode = item.external_attr >> 16
            if (not name or "\\" in name or "\x00" in name or path.is_absolute()
                    or ".." in path.parts or not path.parts
                    or path.parts[0] != "LinkScribe"
                    or path.as_posix() != name.rstrip("/")
                    or name.rstrip("/") in names
                    or item.flag_bits & 1
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError(f"Unsafe or unsupported candidate archive member: {name!r}")
            names.add(name.rstrip("/"))
            if not item.is_dir():
                files.add(name)
        required = {"LinkScribe/start_linux.sh", "LinkScribe/requirements.txt",
                    "LinkScribe/app.py", "LinkScribe/static/index.html"}
        if not required.issubset(files):
            raise ValueError("Candidate archive is missing required application files.")
        if any(parent.as_posix() in files
               for name in names for parent in PurePosixPath(name).parents):
            raise ValueError("Candidate archive contains conflicting file paths.")
        for item in members:
            target = destination.joinpath(*PurePosixPath(item.filename).parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, target.open("xb") as sink:
                    shutil.copyfileobj(source, sink)
                target.chmod(0o755 if item.external_attr >> 16 & 0o111 else 0o644)
    return {"repository": repository, "commit": expected_commit,
            "artifact": ARCHIVE_NAME, "sha256": digest, "members": len(members),
            "uncompressed_bytes": sum(item.file_size for item in members)}


def stop_launcher(process: subprocess.Popen) -> None:
    # The launcher and pip subprocesses are our own isolated process group.
    # Never stop a pre-existing service on the application port.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def run(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running", "checks": [],
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "scope": "Fresh Linux source-archive install and startup; no model inference.",
    }
    report_file = output / "installation.json"

    def checkpoint():
        report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    checkpoint()
    try:
        with tempfile.TemporaryDirectory(prefix="linkscribe-candidate-install-") as temporary:
            extraction = Path(temporary)
            report["source"] = extract_candidate(args.artifact_dir.resolve(), extraction,
                                                  args.expected_commit, args.repository)
            report["checks"].append("archive provenance and safe extraction")
            checkpoint()
            root = extraction / "LinkScribe"
            if (root / ".venv").exists() or (root / "data").exists() or (root / ".git").exists():
                raise ValueError("Candidate archive must not include a venv, runtime data, or Git checkout.")
            # Failing here protects unrelated local work and prevents a stale
            # already-running application from satisfying these checks.
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 8765))
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            environment = os.environ.copy()
            for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PIP_TARGET", "PIP_PREFIX", "PIP_USER"):
                environment.pop(key, None)
            environment["PYTHONNOUSERSITE"] = "1"
            environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
            environment["PIP_NO_INPUT"] = "1"
            with (output / "launcher.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(["bash", "start_linux.sh"], cwd=root,
                                           env=environment, stdout=log, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                try:
                    deadline = time.monotonic() + args.startup_timeout
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise RuntimeError(f"Actual launcher exited with code {process.returncode}; see launcher.log.")
                        try:
                            with opener.open(BASE_URL + "/health", timeout=2) as response:
                                health = json.load(response)
                            break
                        except OSError:
                            time.sleep(0.5)
                    else:
                        raise TimeoutError("Fresh installation/startup timed out; see launcher.log.")
                    if health.get("status") != "ok" or health.get("service") != "LinkScribe" or "js_runtime" not in health:
                        raise AssertionError(f"Unexpected health response: {health!r}")
                    report["health"] = health
                    report["checks"].append("actual start_linux.sh, fresh venv and /health")
                    with opener.open(BASE_URL + "/api/diagnostics", timeout=15) as response:
                        diagnostics = json.load(response)
                    if diagnostics.get("app") != "LinkScribe" or "libraries" not in diagnostics:
                        raise AssertionError("Setup diagnostics did not identify the installed application.")
                    report["checks"].append("setup diagnostics")
                    with opener.open(BASE_URL + "/", timeout=5) as response:
                        homepage = response.read().decode("utf-8")
                    if "<title>LinkScribe" not in homepage:
                        raise AssertionError("Installed application homepage did not load.")
                    report["checks"].append("packaged static homepage")
                    with opener.open(BASE_URL + "/api/library", timeout=5) as response:
                        saved = json.load(response)
                    if saved != {"items": []}:
                        raise AssertionError("Freshly installed candidate does not have an empty library.")
                    report["checks"].append("fresh SQLite library")
                    subprocess.run([str(root / ".venv/bin/python"), "-m", "pip", "check"],
                                   cwd=root, env=environment, check=True, timeout=60,
                                   stdout=log, stderr=subprocess.STDOUT)
                    if process.poll() is not None:
                        raise RuntimeError("The launcher stopped before verification completed.")
                    report["checks"].append("installed dependency consistency")
                    report["status"] = "passed"
                finally:
                    stop_launcher(process)
    except Exception as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    checkpoint()
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--startup-timeout", type=int, default=480)
    options = parser.parse_args()
    if not 1 <= options.startup_timeout <= 900:
        parser.error("--startup-timeout must be between 1 and 900 seconds")
    raise SystemExit(run(options))
