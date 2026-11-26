"""Optional public-model CPU speaker diarization prototype.

This module returns anonymous acoustic turns, not a person's identity. It does
not assign text to turns or invent word timestamps. Scores are cosine similarity
heuristics, not calibrated probabilities; overlapping speakers are unsupported.
"""
from __future__ import annotations

from array import array
from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import importlib.metadata
import math
import os
from pathlib import Path
import time
from typing import Any

# Set before ONNX Runtime's first import: its newer cross-platform builds can
# create a telemetry uploader during initialization, before an API opt-out.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"


SAMPLE_RATE = 16000
MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
MODEL_REVISION = "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"


class DiarizationError(Exception):
    """Readable optional-feature failure; callers should retain the transcript."""


@dataclass(frozen=True)
class DiarizationConfig:
    window_seconds: float = 2.5
    hop_seconds: float = 1.25
    minimum_window_seconds: float = 1.0
    cluster_distance: float = 0.65
    minimum_similarity: float = 0.50
    minimum_margin: float = 0.08
    minimum_cluster_windows: int = 2
    max_audio_seconds: float = 7200.0
    max_windows: int = 8000
    max_cluster_windows: int = 400
    max_speakers: int = 12
    embedding_batch_size: int = 8
    cpu_threads: int = 2

    def validate(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise DiarizationError(f"Invalid speaker setting: {name}.")
        if not 0.5 <= self.minimum_window_seconds <= self.window_seconds <= 5:
            raise DiarizationError("Speaker windows must be between 0.5 and 5 seconds.")
        if not 0.25 <= self.hop_seconds <= self.window_seconds:
            raise DiarizationError("Speaker window hop is outside its supported range.")
        if not 0 < self.cluster_distance < 1 or not 0 <= self.minimum_similarity <= 1 or not 0 <= self.minimum_margin <= 1:
            raise DiarizationError("Speaker similarity settings must be bounded fractions.")
        limits = {"minimum_cluster_windows": (2, 20), "max_windows": (2, 8000),
                  "max_cluster_windows": (2, 400), "max_speakers": (1, 12),
                  "embedding_batch_size": (1, 16), "cpu_threads": (1, 8)}
        for name, (low, high) in limits.items():
            value = getattr(self, name)
            if not isinstance(value, int) or not low <= value <= high:
                raise DiarizationError(f"Speaker setting {name} must be an integer from {low} to {high}.")
        if not 0 < self.max_audio_seconds <= 7200:
            raise DiarizationError("Speaker audio limit must be positive and at most two hours.")


def decode_mono(audio_path: Path, max_seconds: float):
    """Decode bounded 16 kHz float audio without retaining a list of frames."""
    import av
    import numpy as np

    samples = array("f")
    limit = int(max_seconds * SAMPLE_RATE)
    try:
        with av.open(str(audio_path)) as container:
            if not container.streams.audio:
                raise DiarizationError("The recording contains no audio stream.")
            if container.duration is not None and container.duration / av.time_base > max_seconds:
                raise DiarizationError("The recording exceeds the speaker-analysis duration limit.")
            resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)

            def append(frame):
                values = frame.to_ndarray().reshape(-1)
                if len(samples) + len(values) > limit:
                    raise DiarizationError("The recording exceeds the speaker-analysis duration limit.")
                if not np.isfinite(values).all():
                    raise DiarizationError("The recording contains invalid audio samples.")
                samples.frombytes(values.astype("float32", copy=False).tobytes())

            for frame in container.decode(audio=0):
                for resampled in resampler.resample(frame):
                    append(resampled)
            for frame in resampler.resample(None):
                append(frame)
    except DiarizationError:
        raise
    except Exception as exc:
        raise DiarizationError("Cannot decode this recording for speaker analysis.") from exc
    if not samples:
        raise DiarizationError("The recording contains no decoded audio.")
    return np.frombuffer(samples, dtype="float32")


def speech_regions(audio):
    """Reuse the bundled public Silero ONNX VAD, without a separate download."""
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    regions = get_speech_timestamps(audio, VadOptions(
        threshold=0.5, min_speech_duration_ms=250,
        min_silence_duration_ms=200, speech_pad_ms=30))
    if len(regions) > 10000:
        raise DiarizationError("Too many speech regions for bounded speaker analysis.")
    return regions


def make_windows(regions, config: DiarizationConfig):
    windows = []
    short_regions = []
    size = round(config.window_seconds * SAMPLE_RATE)
    hop = round(config.hop_seconds * SAMPLE_RATE)
    minimum = round(config.minimum_window_seconds * SAMPLE_RATE)
    previous_end = 0
    for region_index, region in enumerate(regions):
        start, end = region["start"], region["end"]
        if (not isinstance(start, int) or not isinstance(end, int) or
                start < previous_end or end <= start):
            raise DiarizationError("Voice activity detector returned invalid or overlapping regions.")
        previous_end = end
        if end - start < minimum:
            short_regions.append(region_index)
            continue
        starts = list(range(start, max(start + 1, end - size + 1), hop))
        last_start = max(start, end - size)
        # Near-identical tail windows are not independent cluster support.
        if last_start - starts[-1] >= hop / 2:
            starts.append(last_start)
        for begin in starts:
            windows.append({"start": begin, "end": min(begin + size, end), "region": region_index})
        if len(windows) > config.max_windows:
            raise DiarizationError("Too many speaker windows; try a shorter recording.")
    return windows, short_regions


@lru_cache(maxsize=1)
def _encoder(cache_dir: str):
    from speechbrain.inference.speaker import EncoderClassifier
    from speechbrain.utils.fetching import FetchConfig, LocalStrategy

    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    return EncoderClassifier.from_hparams(
        source=MODEL_ID, savedir=str(root), run_opts={"device": "cpu"},
        local_strategy=LocalStrategy.COPY,
        fetch_config=FetchConfig(token=False, revision=MODEL_REVISION,
                                 huggingface_cache_dir=str(root / "hub")))


def embed_windows(audio, windows, config, cache_dir):
    import numpy as np
    import torch

    encoder = _encoder(str(cache_dir))
    previous_threads = torch.get_num_threads()
    result = []
    try:
        torch.set_num_threads(config.cpu_threads)
        with torch.inference_mode():
            for offset in range(0, len(windows), config.embedding_batch_size):
                batch = windows[offset:offset + config.embedding_batch_size]
                lengths = [item["end"] - item["start"] for item in batch]
                width = max(lengths)
                waveforms = torch.zeros((len(batch), width), dtype=torch.float32)
                for index, item in enumerate(batch):
                    waveforms[index, :lengths[index]] = torch.from_numpy(audio[item["start"]:item["end"]])
                vectors = encoder.encode_batch(waveforms, torch.tensor(lengths) / width)
                result.append(vectors.detach().cpu().numpy().reshape(len(batch), -1))
    finally:
        torch.set_num_threads(previous_threads)
    embeddings = np.concatenate(result, axis=0)
    norms = np.linalg.norm(embeddings, axis=1)
    if not np.isfinite(embeddings).all() or (norms <= 1e-12).any():
        raise DiarizationError("The speaker model returned invalid embeddings.")
    return embeddings / norms[:, None]


def cluster_windows(embeddings, config):
    """Automatic average-link cosine clustering with a capped training matrix."""
    import numpy as np
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist

    embeddings = np.asarray(embeddings)
    if (embeddings.ndim != 2 or embeddings.shape[1] < 1 or
            not np.isfinite(embeddings).all() or
            (np.linalg.norm(embeddings, axis=1) <= 1e-12).any()):
        raise DiarizationError("The speaker model returned invalid embeddings.")
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    count = len(embeddings)
    selected = np.unique(np.linspace(0, count - 1, min(count, config.max_cluster_windows), dtype=int))
    if len(selected) < config.minimum_cluster_windows:
        return [{"speaker": None, "similarity": None, "margin": None,
                 "reason": "insufficient_speaker_evidence"} for _ in embeddings], 0
    reference = embeddings[selected]
    distances = np.clip(pdist(reference, metric="cosine"), 0, 2)
    labels = fcluster(linkage(distances, method="average"), t=config.cluster_distance, criterion="distance")
    accepted = []
    supported_reference = set()
    for label in sorted(set(labels)):
        members = np.flatnonzero(labels == label)
        if len(members) >= config.minimum_cluster_windows:
            centroid = reference[members].mean(axis=0)
            # A fringe/mixed window must not pull its own cluster center toward
            # itself enough to turn an ambiguous match into a confident label.
            if len(members) >= 3:
                ranked = np.argsort(-(reference[members] @ centroid), kind="stable")
                core = members[ranked[:max(2, int(len(members) * 0.75))]]
                centroid = reference[core].mean(axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 1e-12:
                accepted.append((int(selected[members].min()), centroid / norm))
                supported_reference.update(int(item) for item in selected[members])
    accepted.sort(key=lambda item: item[0])
    if len(accepted) > config.max_speakers:
        raise DiarizationError("Speaker evidence exceeds the supported cluster limit; no forced merge was made.")
    if not accepted:
        return [{"speaker": None, "similarity": None, "margin": None,
                 "reason": "insufficient_speaker_evidence"} for _ in embeddings], 0
    scores = embeddings @ np.stack([item[1] for item in accepted]).T
    decisions = []
    used = set()
    rejected_reference = set(selected) - supported_reference
    for index, row in enumerate(scores):
        ranked = np.argsort(-row, kind="stable")
        best = int(ranked[0])
        score = float(np.clip(row[best], -1, 1))
        margin = float(row[best] - row[ranked[1]]) if len(ranked) > 1 else None
        reason = ("insufficient_speaker_evidence" if index in rejected_reference else
                  "weak_voice_match" if score < config.minimum_similarity else
                  "mixed_or_ambiguous_voice" if margin is not None and margin < config.minimum_margin else None)
        speaker = None if reason else f"Speaker {best + 1}"
        if speaker:
            used.add(speaker)
        decisions.append({"speaker": speaker, "similarity": round(score, 4),
                          "margin": round(margin, 4) if margin is not None else None, "reason": reason})
    return decisions, len(used)


def make_turns(regions, windows, decisions):
    """Window-center boundaries are acoustic estimates, never word timestamps."""
    turns = []
    by_region = {}
    for window, decision in zip(windows, decisions):
        by_region.setdefault(window["region"], []).append((window, decision))
    for index, region in enumerate(regions):
        members = by_region.get(index, [])
        if not members:
            turns.append({"start": region["start"] / SAMPLE_RATE, "end": region["end"] / SAMPLE_RATE,
                          "speaker": None, "similarity": None, "margin": None,
                          "reason": "speech_too_short"})
            continue
        centers = [(window["start"] + window["end"]) / 2 for window, _decision in members]
        boundaries = [region["start"]] + [(a + b) / 2 for a, b in zip(centers, centers[1:])] + [region["end"]]
        for position, (_window, decision) in enumerate(members):
            turn = {"start": round(boundaries[position] / SAMPLE_RATE, 4),
                    "end": round(boundaries[position + 1] / SAMPLE_RATE, 4), **decision}
            if (turns and turns[-1]["end"] == turn["start"] and
                    turns[-1]["speaker"] == turn["speaker"] and turns[-1]["reason"] == turn["reason"]):
                turns[-1]["end"] = turn["end"]
                for key in ("similarity", "margin"):
                    if turn[key] is not None:
                        turns[-1][key] = min(turns[-1][key], turn[key])
            else:
                turns.append(turn)
    return turns


def diarize_audio(audio_path: str | Path, *, config: DiarizationConfig | None = None,
                  cache_dir: str | Path | None = None) -> dict[str, Any]:
    """Run public CPU models and return bounded anonymous turns and uncertainty."""
    config = config or DiarizationConfig()
    config.validate()
    audio_path = Path(audio_path)
    cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache/linkscribe/speaker-ecapa"
    started = time.monotonic()
    try:
        audio = decode_mono(audio_path, config.max_audio_seconds)
        regions = speech_regions(audio)
        if any(region["end"] > len(audio) for region in regions):
            raise DiarizationError("Voice activity timestamps extend past the recording.")
        windows, short_regions = make_windows(regions, config)
        if windows:
            embeddings = embed_windows(audio, windows, config, cache_dir)
            decisions, count = cluster_windows(embeddings, config)
        else:
            decisions, count = [], 0
        turns = make_turns(regions, windows, decisions)
    except DiarizationError:
        raise
    except (ImportError, ModuleNotFoundError) as exc:
        raise DiarizationError("Install requirements-speakers-free.txt for the optional CPU speaker backend.") from exc
    except Exception as exc:
        raise DiarizationError("Public speaker analysis failed; check model downloads and installed audio dependencies.") from exc
    warnings = []
    if not regions:
        warnings.append("No speech was detected.")
    if short_regions:
        warnings.append("Short speech regions were left unassigned.")
    if any(turn["speaker"] is None for turn in turns):
        warnings.append("Some speech lacked sufficient evidence for a speaker label.")
    if len(windows) > config.max_cluster_windows:
        warnings.append("Clustering used a bounded temporal sample; rare speakers may remain unassigned.")
    versions = {}
    for name in ("speechbrain", "torch", "torchaudio", "faster-whisper", "onnxruntime", "av", "scipy"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    fingerprints = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in cache_dir.glob("*") if path.is_file() and path.suffix in {".ckpt", ".yaml"}}
    return {"schema_version": 1, "backend": "speechbrain-ecapa-silero-cpu", "speaker_count": count,
            "turns": turns, "warnings": warnings, "overlapping_speech_supported": False,
            "score_interpretation": "Cosine similarity and margin are heuristics, not calibrated probabilities.",
            "timing_interpretation": "Acoustic window boundaries; use real word timestamps for transcript splitting.",
            "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "license": "Apache-2.0", "sha256": fingerprints},
            "versions": versions, "settings": asdict(config), "audio_seconds": round(len(audio) / SAMPLE_RATE, 4),
            "speech_seconds": round(sum(item["end"] - item["start"] for item in regions) / SAMPLE_RATE, 4),
            "window_count": len(windows), "elapsed_seconds": round(time.monotonic() - started, 3)}
