"""Freeze bounded inputs before the candidate inference comparison."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import math
import shutil
import struct
import wave

import numpy as np
from faster_whisper.audio import decode_audio

ROOT = Path(__file__).resolve().parent
ASR = ROOT.parent / "asr-qa"


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def float_wav(path, audio):
    data = audio.astype("<f4").tobytes()
    fmt = struct.pack("<HHIIHH", 3, 1, 16000, 64000, 4, 32)
    body = b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def main():
    target = ROOT / "fixtures"
    target.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location("provider_fixture", ROOT / "base/tests/smoke_real_links.py")
    provider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider)
    cases = []
    for kind in ("silence", "white_noise"):
        payload, evidence = provider.generated_nonspeech(kind)
        path = target / f"{kind}.wav"
        path.write_bytes(payload)
        cases.append({"id": kind, "expected": "no_speech", "audio_file": path.name,
                      "audio_sha256": sha(path), "provenance": evidence})
    # A second, different negative fixed before any candidate output is seen.
    count = 16 * 16000
    samples = np.array([round(3276 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(count)], dtype="<i2")
    path = target / "owned_440hz_tone.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
        output.writeframes(samples.tobytes())
    cases.append({"id": "owned_440hz_tone", "expected": "no_speech", "audio_file": path.name,
                  "audio_sha256": sha(path), "provenance": {"ownership": "owned generated data",
                  "recipe": "16 seconds; signed int16 round(3276*sin(2*pi*440*i/16000)); 16 kHz mono",
                  "expected_speech": "none_by_construction"}})
    source = json.loads((ASR / "fixtures.json").read_text())
    selected = ["fleurs-el_gr-validation-2-1528", "fleurs-en_us-validation-0-1548"]
    for identifier in selected:
        original = next(c for c in source["cases"] if c["id"] == identifier)
        source_path = ASR / original["audio_file"]
        assert sha(source_path) == original["audio_sha256"]
        path = target / (identifier + ".wav")
        shutil.copyfile(source_path, path)
        cases.append({"id": identifier, "expected": "speech", "language": original["language"],
                      "audio_file": path.name, "audio_sha256": sha(path), "reference": original["reference"],
                      "provenance": {"dataset": source["dataset"], "source": original["provenance"], "transform": "none"}})
        quiet_path = target / (identifier + "-quiet-minus20db.wav")
        audio = decode_audio(str(source_path), sampling_rate=16000)
        quiet = audio * np.float32(0.1)
        float_wav(quiet_path, quiet)
        cases.append({"id": identifier + "-quiet-minus20db", "expected": "speech", "language": original["language"],
                      "audio_file": quiet_path.name, "audio_sha256": sha(quiet_path), "reference": original["reference"],
                      "provenance": {"dataset": source["dataset"], "source": original["provenance"],
                      "source_sha256": original["audio_sha256"],
                      "transform": "Complete decoded float32 16 kHz mono multiplied by float32 0.1 (-20 dB amplitude), rewrapped as IEEE float32 WAV; no trimming or normalization.",
                      "sample_count": len(quiet), "nonzero_sample_count": int(np.count_nonzero(quiet)),
                      "pcm_sha256": hashlib.sha256(quiet.astype("<f4").tobytes()).hexdigest()}})
    manifest = {"schema_version": 1, "evaluation_role": "bounded_development_regression_not_fresh_accuracy_benchmark",
                "selection": "Known hosted noise, exact-zero regression, one predeclared new owned tone, and first Greek/English cases from the existing development manifest with fixed -20 dB counterparts.",
                "asr_options": "Actual default app Small/auto; no reference, prompt or hotwords supplied; normal fallback retained.",
                "qa_random_seed": 1729,
                "seed_scope": "CTranslate2 RNG reset to 1729 on the recognition worker immediately before each complete app recognition call in both processes; this is a declared QA reproducibility setting, not a production option change or bitwise determinism guarantee.",
                "tail_fixture_limit": "Earlier hosted tail excerpts existed only in RAM and were deliberately not persisted; no cached local film/tail recording is available. Full-film hosted verification remains required.",
                "cases": cases}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps({"manifest": str(target / "manifest.json"), "sha256": sha(target / "manifest.json"), "cases": len(cases)}))


if __name__ == "__main__":
    main()
