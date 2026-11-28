"""Decode complete known WAVs using the unchanged LinkScribe audio decoder.

This invokes audio decoding only; no speech model or ONNX session is constructed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import inspect
from importlib.metadata import version
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    import numpy as np
    from faster_whisper.audio import decode_audio
    target = args.workspace / "arrays"
    if target.exists():
        raise ValueError("Preserve already prepared input arrays.")
    target.mkdir()
    source_file = Path(inspect.getfile(decode_audio))
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "model_initialized": False,
              "inference_performed": False, "source_fixture_manifest_sha256": sha(args.fixtures),
              "decoder": {"module": "faster_whisper.audio.decode_audio", "source_file": str(source_file),
                          "source_sha256": sha(source_file), "requested_sample_rate": 16000,
                          "runtime_versions": {n: version(n) for n in ["faster-whisper", "av", "numpy"]},
                          "scope": "Same full-audio PCM conversion used by prior application recognitions; no Whisper model or transcript involved."},
              "cases": []}
    for case in json.loads(args.fixtures.read_text())["cases"]:
        audio_path = args.workspace / "audio" / (case["id"] + ".wav")
        if sha(audio_path) != case["audio_sha256"]:
            raise ValueError("Original WAV identity differs")
        audio = decode_audio(str(audio_path), sampling_rate=16000)
        if audio.shape != (case["provenance"]["dataset_num_samples"],) or audio.dtype.str != "<f4":
            raise ValueError("Unexpected complete decoded sample array")
        array_path = target / (case["id"] + ".npy")
        np.save(array_path, audio, allow_pickle=False)
        report["cases"].append({"id": case["id"], "original_audio_path": str(audio_path),
                               "original_audio_sha256": sha(audio_path), "array_path": str(array_path),
                               "array_sha256": sha(array_path), "dtype": audio.dtype.str,
                               "shape": list(audio.shape), "sample_rate_hz": 16000,
                               "sample_count": len(audio), "duration_seconds": len(audio) / 16000,
                               "pcm_sha256": hashlib.sha256(audio.tobytes()).hexdigest(),
                               "full_untrimmed_recording": True, "vad_applied": False})
    report["total_duration_seconds"] = sum(c["duration_seconds"] for c in report["cases"])
    report["complete"] = len(report["cases"]) == 8
    (args.workspace / "input-arrays.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"complete": report["complete"], "case_count": len(report["cases"]),
                      "total_duration_seconds": report["total_duration_seconds"], "inference_performed": False}))


if __name__ == "__main__":
    main()
