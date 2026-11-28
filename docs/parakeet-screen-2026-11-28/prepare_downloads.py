"""Download fixed public Parakeet files and recover eight known development clips.

Preparation only: this file never imports an ASR runtime or initializes a model.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import urllib.error
import urllib.request


MODEL_ID = "istupakov/parakeet-tdt-0.6b-v3-onnx"
REVISION = "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"
MODEL_FILES = {
    "encoder-model.int8.onnx": (652183999, "6139d2fa7e1b086097b277c7149725edbab89cc7c7ae64b23c741be4055aff09"),
    "decoder_joint-model.int8.onnx": (18202004, "eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70"),
    "nemo128.onnx": (139764, "a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f"),
}
SMALL_MODEL_FILES = {
    "config.json": (97, "02a773005666393de591dfd55230b778da1653d8"),
    "vocab.txt": (93939, "fc43e1c723e262df60b70e1919614417162d1fe2"),
    "README.md": (1207, "73e4a765c1f5604589c5345bdf47ad12cf9a70ac"),
}


def identity(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return {"bytes": path.stat().st_size, "sha256": h.hexdigest()}


def download(url, path, expected_bytes, expected_sha256=None, expected_git_blob=None):
    if path.exists():
        result = identity(path)
        if result["bytes"] != expected_bytes or (expected_sha256 and result["sha256"] != expected_sha256):
            raise ValueError("Existing file identity differs: " + path.name)
        result["method"] = "existing_exact_file"
    else:
        partial = path.with_suffix(path.suffix + ".partial")
        if partial.exists():
            raise ValueError("Preserve interrupted download for inspection: " + partial.name)
        with urllib.request.urlopen(url, timeout=45) as response, partial.open("xb") as stream:
            received = 0
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                received += len(chunk)
                if received > expected_bytes:
                    raise ValueError("Download exceeds declared size: " + path.name)
                stream.write(chunk)
        result = identity(partial)
        if result["bytes"] != expected_bytes or (expected_sha256 and result["sha256"] != expected_sha256):
            raise ValueError("Downloaded file identity differs: " + path.name)
        partial.rename(path)
        result["method"] = "ordinary_public_https_download"
    if expected_git_blob:
        data = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob != expected_git_blob:
            raise ValueError("Pinned Git blob differs: " + path.name)
        result["git_blob_sha1"] = blob
    result["url"] = url.split("?")[0]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    log = args.output / "preparation-downloads.json"
    if log.exists():
        raise ValueError("Preserve prior preparation evidence; choose a new output directory.")
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "model_id": MODEL_ID,
              "revision": REVISION, "model_initialized": False, "inference_performed": False,
              "fixture_manifest_sha256": identity(args.fixtures)["sha256"],
              "model_files": {}, "audio_files": {}, "complete": False}
    try:
        model_dir = args.output / "model"
        audio_dir = args.output / "audio"
        model_dir.mkdir(exist_ok=True)
        audio_dir.mkdir(exist_ok=True)
        for name, (size, digest) in MODEL_FILES.items():
            url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}"
            report["model_files"][name] = download(url, model_dir / name, size, digest)
            log.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({"downloaded": name, **report["model_files"][name]}), flush=True)
        for name, (size, blob) in SMALL_MODEL_FILES.items():
            url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}"
            report["model_files"][name] = download(url, model_dir / name, size, expected_git_blob=blob)
        fixtures = json.loads(args.fixtures.read_text())
        if len(fixtures["cases"]) != 8:
            raise ValueError("Expected exactly the eight previously exposed development clips.")
        for case in fixtures["cases"]:
            target = audio_dir / (case["id"] + ".wav")
            cache = Path("/tmp/linkscribe-asr-vimeo-quality/regression-inputs") / target.name
            if not target.exists() and cache.exists() and identity(cache)["sha256"] == case["audio_sha256"]:
                shutil.copy2(cache, target)
            result = download(case["provenance"]["viewer_asset_url_without_query"], target,
                              case["audio_bytes"], case["audio_sha256"])
            report["audio_files"][case["id"]] = result
            log.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({"recovered": case["id"], **result}), flush=True)
        report["complete"] = True
    except Exception as exc:
        # Do not expose temporary signed redirect URLs in ordinary logs.
        report["failure"] = {"type": type(exc).__name__, "message": str(exc).split("?")[0]}
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        log.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
