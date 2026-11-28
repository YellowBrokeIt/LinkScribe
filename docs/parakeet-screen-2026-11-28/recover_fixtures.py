"""Recover the exact exposed fixtures using fresh public dataset-viewer URLs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report_path = args.output / "fixture-recovery.json"
    if report_path.exists():
        raise ValueError("Preserve the previous recovery report.")
    fixtures = json.loads(args.fixtures.read_text())
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "original_fixture_manifest_sha256": digest(args.fixtures), "cases": [],
              "scope": "Same eight previously exposed fixtures; fresh URLs only, original byte hashes mandatory.",
              "inference_performed": False}
    try:
        for case in fixtures["cases"]:
            path = args.output / "audio" / (case["id"] + ".wav")
            cache = Path("/tmp/linkscribe-asr-vimeo-quality/regression-inputs") / path.name
            item = {"id": case["id"], "expected_audio_sha256": case["audio_sha256"]}
            if not path.exists() and cache.exists() and digest(cache) == case["audio_sha256"]:
                shutil.copy2(cache, path)
            if path.exists():
                item["method"] = "retained_exact_file"
            else:
                api = case["provenance"]["rows_api_url"]
                with urllib.request.urlopen(api, timeout=30) as response:
                    payload = response.read()
                data = json.loads(payload)
                if len(data["rows"]) != 1:
                    raise ValueError("Unexpected row count")
                row = data["rows"][0]
                if row["row_idx"] != case["provenance"]["row_index"] or row["row"]["id"] != case["provenance"]["sentence_id"]:
                    raise ValueError("Source row identity changed")
                if row["row"]["num_samples"] != case["provenance"]["dataset_num_samples"]:
                    raise ValueError("Source sample count changed")
                candidates = [audio for audio in row["row"]["audio"] if audio["type"] == "audio/wav"]
                if len(candidates) != 1:
                    raise ValueError("Expected one WAV rendition")
                url = candidates[0]["src"]
                if url.split("?")[0] != case["provenance"]["viewer_asset_url_without_query"]:
                    raise ValueError("Source rendition path changed")
                item.update(method="same_public_rows_api_fresh_asset_url", rows_api_url=api,
                            rows_response_sha256=hashlib.sha256(payload).hexdigest(),
                            asset_url_without_query=url.split("?")[0],
                            source_raw_reference_matches=(row["row"]["raw_transcription"] == case["reference"]))
                partial = path.with_suffix(".wav.partial")
                with urllib.request.urlopen(url, timeout=30) as response:
                    audio = response.read(case["audio_bytes"] + 1)
                if len(audio) != case["audio_bytes"] or hashlib.sha256(audio).hexdigest() != case["audio_sha256"]:
                    partial.write_bytes(audio)
                    raise ValueError("Recovered audio differs from the frozen bytes")
                path.write_bytes(audio)
            if digest(path) != case["audio_sha256"] or path.stat().st_size != case["audio_bytes"]:
                raise ValueError("Retained audio differs from the frozen bytes")
            item.update(audio_bytes=path.stat().st_size, audio_sha256=digest(path), exact_original_bytes=True)
            report["cases"].append(item)
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps({"recovered": case["id"], "exact_original_bytes": True}), flush=True)
        report["complete"] = len(report["cases"]) == 8
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc).split("?")[0]}
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
