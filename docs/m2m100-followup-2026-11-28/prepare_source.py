#!/usr/bin/env python3
"""Fetch only the pinned publisher's M2M100 files and verify their identities."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

HERE = Path(__file__).resolve().parent
MODEL = "facebook/m2m100_418M"
REVISION = "55c2e61bbf05dfb8d7abccdc3fae6fc8512fd636"
WEIGHT_BYTES = 1935796948
WEIGHT_SHA = "d907ea45e4e4b9db163382a6674f6218b3c59566fe06d77f4055c208b4e87ed1"
FILES = {"README.md", "config.json", "generation_config.json", "pytorch_model.bin",
         "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer_config.json", "vocab.json"}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    temporary = Path(path).with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def fetch_small(url, limit=1024 * 1024):
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Remote metadata exceeds the declared bound.")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    source = runtime / "source"
    source.mkdir(parents=True, exist_ok=True)
    output = HERE / "source-provenance.json"
    if output.exists() or any(source.iterdir()):
        raise ValueError("Refusing to overwrite source files or setup evidence.")
    if shutil.disk_usage(runtime).free < 5 * 1024**3:
        raise ValueError("At least 5 GiB free workspace storage is required for this preparation.")
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "model": MODEL, "revision": REVISION, "inference_calls": 0, "files": {}}
    save(output, report)
    started = time.monotonic()
    try:
        metadata_url = f"https://huggingface.co/api/models/{MODEL}/revision/{REVISION}?blobs=true"
        metadata = json.loads(fetch_small(metadata_url))
        if metadata.get("sha") != REVISION or metadata.get("cardData", {}).get("license") != "mit":
            raise ValueError("Official revision or model-card license changed.")
        entries = {item["rfilename"]: item for item in metadata["siblings"] if item["rfilename"] in FILES}
        if set(entries) != FILES:
            raise ValueError("The official repository is missing a declared source file.")
        weight = entries["pytorch_model.bin"]
        if weight.get("size") != WEIGHT_BYTES or weight.get("lfs", {}).get("sha256") != WEIGHT_SHA:
            raise ValueError("The official checkpoint does not match the predeclared size and full hash.")
        report.update({"metadata_url": metadata_url, "model_license": "MIT",
                       "declared_files": entries})
        save(output, report)
        for name in sorted(FILES, key=lambda item: item == "pytorch_model.bin"):
            entry = entries[name]
            url = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}"
            partial = source / (name + ".partial")
            count = 0
            last_progress = 0
            file_started = time.monotonic()
            digest = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=60) as response, partial.open("xb") as destination:
                while block := response.read(4 * 1024 * 1024):
                    count += len(block)
                    if (count > entry["size"] or time.monotonic() - file_started > 600
                            or time.monotonic() - started > 900):
                        raise ValueError("Model download exceeded its frozen byte or time limit.")
                    destination.write(block)
                    digest.update(block)
                    if name == "pytorch_model.bin" and count - last_progress >= 256 * 1024**2:
                        print(json.dumps({"download_file": name, "verified_received_bytes": count}), flush=True)
                        last_progress = count
            if count != entry["size"]:
                raise ValueError("Downloaded source size does not match official metadata.")
            actual_sha = digest.hexdigest()
            if "lfs" in entry:
                if actual_sha != entry["lfs"]["sha256"]:
                    raise ValueError("Downloaded source SHA256 does not match the official LFS identity.")
            else:
                git_blob = hashlib.sha1(f"blob {count}\0".encode() + partial.read_bytes()).hexdigest()
                if git_blob != entry["blobId"]:
                    raise ValueError("Downloaded small file does not match the pinned Git blob.")
            partial.rename(source / name)
            report["files"][name] = {"bytes": count, "sha256": actual_sha, "url": url,
                                      "elapsed_seconds": round(time.monotonic() - file_started, 3)}
            save(output, report)
        license_url = "https://raw.githubusercontent.com/facebookresearch/fairseq/main/LICENSE"
        license_data = fetch_small(license_url, 16384)
        if not license_data.startswith(b"MIT License") or b"Facebook" not in license_data:
            raise ValueError("The originating publisher license text was not the expected MIT license.")
        (source / "LICENSE").write_bytes(license_data)
        report["license_text"] = {"url": license_url, "sha256": sha(source / "LICENSE"),
                                  "bytes": len(license_data),
                                  "scope": "Originating Fairseq MIT license; the pinned model card independently declares MIT."}
        report["complete"] = True
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        save(output, report)
    print(json.dumps({"source_setup_complete": report["complete"], "inference_calls": 0,
                      "files_verified": len(report["files"]), "error_type": report.get("error", {}).get("type")}), flush=True)
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
