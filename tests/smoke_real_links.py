"""Opt-in public-provider acceptance through the real local application.

Run from the repository root (the default is the 52-second licensed trailer)::

    PYTHONPATH=. python tests/smoke_real_links.py --output qa-real-links
    LINKSCRIBE_USE_SYSTEM_CERTS=1 PYTHONPATH=. python tests/smoke_real_links.py \
        --fixture youtube_sintel_trailer --fixture vimeo_sintel_trailer \
        --fixture dailymotion_tears_of_steel --output qa-real-links

The real HTTP API, queue, downloader, local Whisper, SQLite, and exporters run
unchanged. Observer wrappers record acquisition, decoding, and recognition evidence;
they call the original functions and never supply media, captions, or text.
The isolated server process is stopped and started again to check durable
library downloads and completed batch history. No account, cookies, alternate
proxy, or restricted-source workaround is configured here. Network/auth errors
are recorded as failures, never provider passes. This is not an ASR accuracy
benchmark and does not establish unrestricted access to a whole provider.

Fixtures are Blender CC BY 3.0 content; the evidence records attribution and
the original licence pages. Transcripts are machine-generated derivatives.
"""
from __future__ import annotations

import argparse
from array import array
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import inspect
import io
import json
import math
import os
from pathlib import Path
import random
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
TAIL_WINDOWS_SECONDS = ((424, 434), (502, 522), (553, 571))
NONSPEECH_SECONDS = 32
SOURCE_FILES = ("app.py", "sources.py", "runtime_check.py", "library.py", "batch_store.py",
                "enhancements.py", "tests/smoke_real_links.py")
FIXTURES = {
    "youtube_sintel_trailer": {
        "url": "https://www.youtube.com/watch?v=HOfdboHvshg", "provider": "youtube",
        "title_contains": "Sintel", "public_title": '"Sintel" Trailer, Durian Open Movie Project',
        "uploader": "Blender", "license": "CC BY 3.0",
        "license_evidence": "https://durian.blender.org/sharing/",
        "publication_evidence": "https://durian.blender.org/news/sintel-teaser/",
        "attribution": "© copyright Blender Foundation | www.sintel.org",
    },
    "youtube_tears_of_steel_teaser": {
        "url": "https://www.youtube.com/watch?v=WwHux5QZfC8", "provider": "youtube",
        "title_contains": "Tears of Steel", "public_title": "Tears of Steel - Teaser",
        "uploader": "MangoOpenMovie", "license": "CC BY 3.0",
        "license_evidence": "https://mango.blender.org/about/",
        "publication_evidence": "https://mango.blender.org/production/tears-of-steel-teaser/",
        "attribution": "(CC) Blender Foundation | mango.blender.org",
    },
    "vimeo_sintel_trailer": {
        "url": "https://vimeo.com/11721242", "provider": "vimeo",
        "title_contains": "Sintel", "public_title": "Sintel trailer!", "uploader": "Dykam",
        "license": "CC BY 3.0", "license_evidence": "https://durian.blender.org/sharing/",
        "publication_evidence": "https://vimeo.com/11721242",
        "attribution": "© copyright Blender Foundation | www.sintel.org",
        "note": "Uploader identifies this as a reupload of the licensed original trailer.",
    },
    "vimeo_sintel_rerendered": {
        "url": "https://vimeo.com/19934655", "provider": "vimeo",
        "title_contains": "Sintel", "public_title": "Sintel re-rendered", "uploader": "Teddl",
        "license": "CC BY 3.0", "license_evidence": "https://durian.blender.org/sharing/",
        "publication_evidence": "https://vimeo.com/19934655",
        "attribution": "© copyright Blender Foundation | www.sintel.org",
        "note": "Full film; the re-render's public description states the original licence.",
    },
    "dailymotion_tears_of_steel": {
        "url": "https://www.dailymotion.com/video/xbvubxi", "provider": "dailymotion",
        "title_contains": "Tears of Steel", "public_title": "فيلم 🎬 Tears of Steel | معركة المستقبل بدأت",
        "uploader": "MixTube", "license": "CC BY 3.0",
        "license_evidence": "https://mango.blender.org/about/",
        "publication_evidence": "https://www.dailymotion.com/video/xbvubxi",
        "attribution": "(CC) Blender Foundation | mango.blender.org",
        "note": "Repost with an Arabic title; the public description names the film and licence.",
    },
}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_hashes():
    return {name: digest(ROOT / name) for name in SOURCE_FILES}


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def exception_chain(error):
    chain, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        item = {"type": type(error).__name__, "message": str(error)}
        response = getattr(error, "response", None)
        if response is not None:
            item["http_status"] = getattr(response, "status", None)
            headers = getattr(response, "headers", {})
            item["response_headers"] = {key: headers.get(key) for key in (
                "Content-Type", "Server", "Date", "X-Mitmproxy-Blocked-Reason", "X-Proxy-Error", "X-Squid-Error")}
            url = urllib.parse.urlsplit(getattr(response, "url", "") or "")
            item["response_origin"] = f"{url.scheme}://{url.netloc}" if url.netloc else ""
            try:
                item["response_body_prefix"] = response.read(2048).decode("utf-8", errors="replace")
            except Exception as read_error:
                item["response_body_unavailable"] = type(read_error).__name__
        chain.append(item)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return chain


def evidence_value(value):
    """Represent Python metadata, including explicit non-finite option values."""
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {str(key): evidence_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [evidence_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_float": repr(value)}
    return value


def array_evidence(audio):
    """Describe actual decoded samples without changing or retaining the array."""
    import numpy as np
    if not isinstance(audio, np.ndarray):
        return None
    raw = memoryview(audio).cast("B") if audio.flags.c_contiguous else audio.tobytes()
    return {"array_identity": hex(id(audio)), "shape": list(audio.shape), "dtype": audio.dtype.str,
            "sample_count": int(audio.size), "nonzero_sample_count": int(np.count_nonzero(audio)),
            "pcm_sha256": hashlib.sha256(raw).hexdigest()}


def observe_audio_decode(module, event, on_decoded=None):
    """Measure the actual production decoder's return value without replacing it."""
    original = module.decode_audio
    signature = inspect.signature(original)

    def observed_decode(input_file, *args, **kwargs):
        arguments = signature.bind(input_file, *args, **kwargs)
        arguments.apply_defaults()
        audio = original(input_file, *args, **kwargs)
        rate = arguments.arguments["sampling_rate"]
        channels = audio if isinstance(audio, tuple) else (audio,)
        counts = [len(channel) for channel in channels]
        event("audio_decoded",
              job_id=Path(input_file).parent.name if isinstance(input_file, (str, os.PathLike)) else None,
              sampling_rate_hz=rate, channel_sample_counts=counts,
              decoded_arrays=[array_evidence(channel) for channel in channels],
              decoded_duration_seconds=max(counts, default=0) / rate)
        if on_decoded is not None:
            on_decoded(input_file, audio, rate)
        return audio

    module.decode_audio = observed_decode


def observe_speech_selection(module, event, current_job):
    """Observe the actual VAD and collected arrays without changing either."""
    original_vad, original_collect = module.get_speech_timestamps, module.collect_chunks
    vad_signature, collect_signature = inspect.signature(original_vad), inspect.signature(original_collect)

    def observed_vad(audio, *args, **kwargs):
        arguments = vad_signature.bind(audio, *args, **kwargs)
        arguments.apply_defaults()
        result = original_vad(audio, *args, **kwargs)
        rate = arguments.arguments["sampling_rate"]
        intervals = [{"start_sample": int(chunk["start"]), "end_sample": int(chunk["end"])}
                     for chunk in result]
        event("vad_speech_intervals", job_id=current_job(), sampling_rate_hz=rate,
              input_sample_count=len(audio), intervals=intervals,
              kept_sample_count=sum(item["end_sample"] - item["start_sample"] for item in intervals),
              last_kept_end_seconds=max((item["end_sample"] for item in intervals), default=0) / rate,
              vad_options=evidence_value(arguments.arguments.get("vad_options")),
              additional_options=evidence_value(arguments.arguments.get("kwargs", {})))
        return result

    def observed_collect(audio, chunks, *args, **kwargs):
        arguments = collect_signature.bind(audio, chunks, *args, **kwargs)
        arguments.apply_defaults()
        result = original_collect(audio, chunks, *args, **kwargs)
        counts = [len(chunk) for chunk in result[0]]
        rate = arguments.arguments["sampling_rate"]
        event("post_vad_audio", job_id=current_job(), sampling_rate_hz=rate,
              collected_chunk_sample_counts=counts, sample_count=sum(counts),
              duration_seconds=sum(counts) / rate,
              maximum_chunk_duration=evidence_value(arguments.arguments.get("max_duration")))
        return result

    module.get_speech_timestamps, module.collect_chunks = observed_vad, observed_collect


def observe_transcribe(module, event, current_job):
    """Retain real normal-call options/info, preserving the returned generator."""
    original = module.WhisperModel.transcribe
    signature = inspect.signature(original)

    def observed(self, audio, *args, **kwargs):
        job_id = current_job()
        if job_id is None:
            return original(self, audio, *args, **kwargs)
        arguments = signature.bind(self, audio, *args, **kwargs)
        arguments.apply_defaults()
        options = {key: value for key, value in arguments.arguments.items() if key not in {"self", "audio"}}
        event("transcribe_request", job_id=job_id, explicit_kwargs=evidence_value(kwargs),
              resolved_options=evidence_value(options), audio_array=array_evidence(audio))
        result = original(self, audio, *args, **kwargs)
        event("transcribe_info", job_id=job_id, info=evidence_value(result[1]))
        return result

    module.WhisperModel.transcribe = observed


def observe_segment_creation(module, event, current_job):
    """Observe real Segment construction without wrapping its yielding generator.

    Faster Whisper constructs these dataclasses at its normal generator yield.
    With VAD disabled, their text/times must match the normal saved segments.
    Scores remain raw diagnostic evidence and never change acceptance or text.
    """
    original = module.Segment.__init__

    def observed(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        job_id = current_job()
        if job_id is not None:
            event("asr_segment_created", job_id=job_id, segment=evidence_value(self))
        return result

    module.Segment.__init__ = observed


def transcription_evidence(events):
    """Require observations consistent with what normal ASR actually requested."""
    decoded = [item for item in events if item["kind"] == "audio_decoded"]
    requests = [item for item in events if item["kind"] == "transcribe_request"]
    infos = [item for item in events if item["kind"] == "transcribe_info"]
    vad = [item for item in events if item["kind"] == "vad_speech_intervals"]
    collected = [item for item in events if item["kind"] == "post_vad_audio"]
    assert len(decoded) == len(requests) == len(infos) == 1, "Missing or repeated normal ASR observation."
    duration, rate = decoded[0]["decoded_duration_seconds"], decoded[0]["sampling_rate_hz"]
    arrays = decoded[0]["decoded_arrays"]
    assert len(arrays) == 1 and arrays[0] is not None, "Normal ASR must use its decoded mono array."
    assert arrays[0] == requests[0]["audio_array"], "Normal ASR did not receive the identical complete decoded array."
    assert arrays[0]["shape"] == [arrays[0]["sample_count"]]
    assert arrays[0]["sample_count"] == decoded[0]["channel_sample_counts"][0]
    options, info = requests[0]["resolved_options"], infos[0]["info"]
    assert duration > 0 and abs(info["duration"] - duration) <= 1 / rate
    assert options["clip_timestamps"] == "0", "The normal full recording must not be clipped."
    requested_vad = options["vad_filter"]
    if requested_vad is False:
        assert not vad and not collected, "VAD ran despite normal ASR explicitly disabling it."
        assert info["vad_options"] is None
        assert abs(info["duration_after_vad"] - duration) <= 1 / rate, "ASR lost audio despite VAD being off."
    else:
        assert requested_vad is True and len(vad) == len(collected) == 1, "Requested VAD evidence is missing."
        assert vad[0]["kept_sample_count"] == collected[0]["sample_count"]
        assert abs(info["duration_after_vad"] - collected[0]["duration_seconds"]) <= 1 / rate
    return {"decoded_duration_seconds": duration, "normal_vad_filter": requested_vad,
            "decoded_array": arrays[0], "same_decoded_array_passed_to_asr": True,
            "normal_explicit_transcribe_kwargs": requests[0]["explicit_kwargs"],
            "normal_transcribe_info": info,
            "raw_segment_constructions": [item["segment"] for item in events if item["kind"] == "asr_segment_created"],
            "last_vad_kept_end_seconds": vad[0]["last_kept_end_seconds"] if vad else None,
            "post_vad_duration_seconds": info["duration_after_vad"]}


def nonspeech_evidence(events, kind):
    """Separate proven zero-PCM rejection from actual nonzero-noise inference."""
    if kind == "white_noise":
        evidence = transcription_evidence(events)
        assert evidence["normal_vad_filter"] is False
        assert evidence["decoded_array"]["nonzero_sample_count"] > 0
        return {"processing_path": "actual_nonzero_audio_inference", **evidence}
    assert kind == "silence"
    decoded = [item for item in events if item["kind"] == "audio_decoded"]
    assert len(decoded) == 1, "Digital silence must be decoded exactly once."
    item = decoded[0]
    arrays = item["decoded_arrays"]
    assert len(arrays) == 1 and arrays[0] is not None
    assert arrays[0]["nonzero_sample_count"] == 0
    assert arrays[0]["shape"] == [arrays[0]["sample_count"]]
    assert arrays[0]["sample_count"] == item["channel_sample_counts"][0]
    assert not any(event["kind"] in {"transcribe_request", "transcribe_info", "vad_speech_intervals",
                                   "post_vad_audio", "asr_segment_created", "recognition_done"}
                   for event in events), "Digital silence unexpectedly reached model inference."
    return {"processing_path": "exact_digital_silence_rejected_before_inference",
            "decoded_duration_seconds": item["decoded_duration_seconds"],
            "decoded_array": arrays[0], "inference_attempted": False}


def generated_nonspeech(kind):
    """Deterministic owned PCM fixtures; no text or recording is synthesized."""
    rate, count = 16000, 16000 * NONSPEECH_SECONDS
    if kind == "silence":
        samples = array("h", [0]) * count
        recipe = "Signed 16-bit PCM zeros"
    elif kind == "white_noise":
        generator = random.Random(20261126)
        samples = array("h", (generator.randint(-3276, 3276) for _ in range(count)))
        recipe = "Python random.Random(20261126); one randint(-3276,3276) per signed 16-bit PCM sample"
    else:
        raise ValueError("Unknown owned no-speech fixture.")
    if sys.byteorder != "little":
        samples.byteswap()
    pcm = samples.tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm)
    payload = buffer.getvalue()
    return payload, {"kind": kind, "expected_speech": "none_by_construction", "recipe": recipe,
        "duration_seconds": NONSPEECH_SECONDS, "sampling_rate_hz": rate, "channels": 1,
        "sample_count": count, "pcm_format": "signed_16_bit_little_endian",
        "pcm_sha256": hashlib.sha256(pcm).hexdigest(), "wav_sha256": hashlib.sha256(payload).hexdigest(),
        "wav_bytes": len(payload), "attribution": "Owned generated QA data; no external recording or reference text."}


def prepare_tail_windows(audio, rate):
    """Copy only 48 seconds of predetermined licensed-fixture diagnostic audio."""
    windows = []
    for start, end in TAIL_WINDOWS_SECONDS:
        first, last = min(len(audio), int(start * rate)), min(len(audio), int(end * rate))
        samples = audio[first:last].copy()
        windows.append({"requested_start_seconds": start, "requested_end_seconds": end,
            "start_sample": first, "end_sample": last, "sampling_rate_hz": rate,
            "sample_count": len(samples), "duration_seconds": len(samples) / rate,
            "pcm_dtype": samples.dtype.str,
            "pcm_sha256": hashlib.sha256(memoryview(samples).cast("B")).hexdigest(), "audio": samples})
    return windows


def run_tail_diagnostic(engine, windows, report_path, metadata, saved_fingerprint):
    """Separate VAD-off inference after cleanup; never replace the saved transcript."""
    settings = {"language": "en", "beam_size": 5, "vad_filter": False,
                "condition_on_previous_text": False, "word_timestamps": False}
    before = saved_fingerprint()
    report = {"schema_version": 1, "started_at": now(), "complete": False,
        "execution_status": "running", "semantic_quality": "unreviewed", **metadata,
        "purpose": "Post-hoc bounded tail diagnosis, not a replacement app transcript or benchmark.",
        "comparison_limits": "Cropping, explicit English, and VAD off differ from the normal auto-language full recording; this is not a controlled model-quality comparison.",
        "audio_storage": "Only bounded PCM copies in memory; no audio file persisted by the diagnostic.",
        "request_settings": settings, "normal_record_sha256_before": before,
        "cases": [{key: value for key, value in window.items() if key != "audio"} | {"status": "pending"}
                  for window in windows]}
    write_json(report_path, report)
    for window, item in zip(windows, report["cases"]):
        item["status"] = "running"
        write_json(report_path, report)
        started = time.monotonic()
        try:
            if window["sample_count"] <= 0:
                raise ValueError("The normal decoder did not return samples for this fixed diagnostic window.")
            segments, info = engine.transcribe(window["audio"], **settings)
            item["raw_info"] = evidence_value(info)
            item["raw_segments"] = []
            for segment in segments:
                item["raw_segments"].append(evidence_value(segment))
                write_json(report_path, report)
            item["status"] = "completed"
        except Exception as error:
            item.update(status="error", errors=exception_chain(error), traceback=traceback.format_exc())
        item["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(report_path, report)
    after = saved_fingerprint()
    report.update(complete=True, finished_at=now(), normal_record_sha256_after=after,
                  normal_record_unchanged=before == after,
                  execution_status="completed" if before == after and all(
                      item["status"] == "completed" for item in report["cases"]) else "error")
    write_json(report_path, report)
    return report


def serve(data_root, events_path, diagnose_tail=False):
    """Isolated app; optional diagnosis runs after the normal worker has finished."""
    sys.path.insert(0, str(ROOT))
    import app
    import av
    import library
    import uvicorn

    app.DATA_DIR = data_root / "jobs"
    app.DATA_DIR.mkdir(parents=True, exist_ok=True)
    library.DB_FILE = data_root / "library.sqlite3"
    os.environ["LINKSCRIBE_DEVICE"] = "cpu"

    def event(kind, **details):
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "pid": os.getpid(), "kind": kind, **details},
                                    ensure_ascii=True, allow_nan=False) + "\n")

    versions = {}
    for package in ("yt-dlp", "curl-cffi", "faster-whisper", "ctranslate2", "av", "certifi"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    event("server_start", versions=versions, system_certificates=os.getenv("LINKSCRIBE_USE_SYSTEM_CERTS") == "1",
          device="cpu", source_sha256=source_hashes(), tail_diagnostic_requested=diagnose_tail)

    context = threading.local()
    retained_tails = {}

    def retain_tail(input_file, audio, rate):
        if not diagnose_tail or not isinstance(input_file, (str, os.PathLike)):
            return
        job_id = Path(input_file).parent.name
        job = app.jobs.get(job_id)
        if (job is None or job.batch_id
                or job.source != FIXTURES["dailymotion_tears_of_steel"]["url"]):
            return
        retained_tails[job_id] = {"windows": prepare_tail_windows(audio, rate),
            "audio_sha256": digest(input_file), "decoded_duration_seconds": len(audio) / rate,
            "model": getattr(context, "model", None), "requested_language": getattr(context, "language", None)}

    # Observe the app's explicit decode and the model's fallback decode alias.
    # The normal app passes the identical array; no second decode is allowed.
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    whisper_module = importlib.import_module("faster_whisper.transcribe")
    audio_module = importlib.import_module("faster_whisper.audio")
    observe_audio_decode(audio_module, event, retain_tail)
    observe_audio_decode(whisper_module, event, retain_tail)
    observe_speech_selection(whisper_module, event, lambda: getattr(context, "job_id", None))
    observe_transcribe(whisper_module, event, lambda: getattr(context, "job_id", None))
    observe_segment_creation(whisper_module, event, lambda: getattr(context, "job_id", None))

    download = app._download_source_audio
    recognize = app._recognize
    guarded_worker = app._guarded_worker

    def observed_download(job_id, source):
        started = time.monotonic()
        event("acquisition_start", job_id=job_id, provider=source.provider, url=source.url)
        try:
            path, title = download(job_id, source)
        except Exception as error:
            event("acquisition_failed", job_id=job_id, errors=exception_chain(error),
                  elapsed_seconds=round(time.monotonic() - started, 3))
            raise
        details = {"bytes": path.stat().st_size, "sha256": digest(path)}
        try:
            with av.open(str(path)) as media:
                details["duration_seconds"] = media.duration / av.time_base if media.duration is not None else None
                details["audio_streams"] = len(media.streams.audio)
        except Exception as error:
            # Keep the original production recognizer responsible for whether
            # this file can be decoded; observation must not replace its path.
            details.update(audio_streams=0, media_inspection_errors=exception_chain(error))
        event("acquisition_done", job_id=job_id, title=title, **details,
              elapsed_seconds=round(time.monotonic() - started, 3))
        return path, title

    def observed_recognize(path, language, model):
        started = time.monotonic()
        job_id = Path(path).parent.name
        event("recognition_start", job_id=job_id, model=model, requested_language=language,
              audio_sha256=digest(path))
        context.job_id, context.model, context.language = job_id, model, language
        try:
            segments, detected_language = recognize(path, language, model)
            event("recognition_done", job_id=job_id, model=model, language=detected_language,
                  segment_count=len(segments), elapsed_seconds=round(time.monotonic() - started, 3))
            return segments, detected_language
        except Exception as error:
            event("recognition_failed", job_id=job_id, errors=exception_chain(error),
                  elapsed_seconds=round(time.monotonic() - started, 3))
            raise
        finally:
            context.job_id = None

    def observed_worker(job_id, worker, *args):
        try:
            # This original call saves the normal result and removes its media.
            guarded_worker(job_id, worker, *args)
            pending = retained_tails.pop(job_id, None)
            if pending is None or app.jobs[job_id].status != "done":
                return
            report_path = events_path.parent / ("tail-diagnostic-" + job_id + ".json")
            try:
                clean = not list(app.jobs[job_id].workdir.glob("audio.*"))
                if not clean:
                    raise AssertionError("Normal media cleanup must complete before tail diagnosis.")

                def saved_fingerprint():
                    record = library.get(job_id)
                    if record is None:
                        raise AssertionError("Normal saved result must exist before tail diagnosis.")
                    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=True,
                                                    allow_nan=False).encode("utf-8")).hexdigest()

                metadata = {"job_id": job_id, "fixture": "dailymotion_tears_of_steel",
                    "license_provenance": FIXTURES["dailymotion_tears_of_steel"],
                    "model": pending["model"], "normal_requested_language": pending["requested_language"],
                    "input_audio_sha256": pending["audio_sha256"],
                    "normal_decoded_duration_seconds": pending["decoded_duration_seconds"],
                    "normal_input_cleaned_before_diagnostic": clean, "source_sha256": source_hashes()}
                result = run_tail_diagnostic(app._whisper_model(pending["model"]), pending["windows"],
                                             report_path, metadata, saved_fingerprint)
                event("tail_diagnostic_finished", job_id=job_id, report=report_path.name,
                      execution_status=result["execution_status"], normal_record_unchanged=result["normal_record_unchanged"])
            except Exception as error:
                # Diagnostics must never replace a saved result or its status.
                partial = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
                partial.update(complete=False, execution_status="error", job_id=job_id,
                               errors=exception_chain(error), traceback=traceback.format_exc())
                for item in partial.get("cases", []):
                    if item["status"] in {"pending", "running"}:
                        item["status"] = "incomplete"
                write_json(report_path, partial)
                event("tail_diagnostic_failed", job_id=job_id, report=report_path.name, errors=exception_chain(error))
        finally:
            retained_tails.pop(job_id, None)

    app._download_source_audio = observed_download
    app._recognize = observed_recognize
    app._guarded_worker = observed_worker
    uvicorn.run(app.app, host="127.0.0.1", port=8765, log_level="warning")


def zip_members(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), "Duplicate export ZIP members."
        return {name: archive.read(name) for name in names}


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "provider-report.json").exists():
        raise ValueError("Choose a new output directory to preserve the previous evidence.")
    (output / "downloads").mkdir(exist_ok=True)
    (output / "records").mkdir(exist_ok=True)
    (output / "executed-smoke-real-links.py").write_bytes(Path(__file__).read_bytes())
    selected = args.fixture or ["youtube_sintel_trailer"]
    if len(selected) != len(set(selected)):
        raise ValueError("Do not repeat a fixture.")
    if args.diagnose_dailymotion_tail and "dailymotion_tears_of_steel" not in selected:
        raise ValueError("Tail diagnosis requires the explicitly licensed Dailymotion fixture.")
    report = {
        "schema_version": 1, "started_at": now(), "complete": False, "result": "running",
        "mode": "audio", "requested_model": args.model, "requested_language": args.language,
        "source_sha256_before": source_hashes(), "fixture_licenses": {key: FIXTURES[key] for key in selected},
        "provider_acquisition": "actual_yt_dlp", "speech_recognition": "actual_local_faster_whisper",
        "instrumentation": "observer_wrappers_only; originals called without replacement outputs",
        "asr_semantic_quality": "unreviewed", "subtitle_alignment_accuracy": "unreviewed",
        "system_certificates": os.getenv("LINKSCRIBE_USE_SYSTEM_CERTS") == "1",
        "fixtures": [{"fixture": key, "status": "pending"} for key in selected],
        "mixed_batch": {"status": "pending"}, "restart": {"status": "pending"},
        "tail_diagnostic": {"status": "pending" if args.diagnose_dailymotion_tail else "not_requested",
                            "included_in_normal_pipeline_output": False},
        "nonspeech": {"status": "pending" if args.check_nonspeech else "not_requested",
            "scope": "Two owned generated 32-second fixtures: exact-zero rejection before inference and actual nonzero-noise ASR; no general silence/music/noise guarantee.",
            "cases": [{"kind": kind, "status": "pending"} for kind in ("silence", "white_noise")]
                     if args.check_nonspeech else []},
    }
    checkpoint = lambda: write_json(output / "provider-report.json", report)
    checkpoint()
    events_path = output / "events.jsonl"
    server = None
    scratch = tempfile.TemporaryDirectory(prefix="linkscr-real-links-")
    data_root = Path(scratch.name)
    log = (output / "server.log").open("w", encoding="utf-8")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    successful_records = {}
    export_payloads = {}
    batch_archive = None
    batch_id = None

    def request(path, data=None, as_json=True):
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        headers = {"Origin": BASE_URL}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        with opener.open(urllib.request.Request(BASE_URL + path, data=body, headers=headers), timeout=30) as response:
            raw = response.read()
        return json.loads(raw) if as_json else raw

    def upload_owned_wav(name, payload):
        boundary = "linkscribe-owned-qa-" + hashlib.sha256(payload).hexdigest()[:24]
        assert boundary.encode("ascii") not in payload
        parts = []
        for key, value in {"consent": "true", "model": args.model, "language": args.language}.items():
            parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n").encode("ascii"))
        parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                      "Content-Type: audio/wav\r\n\r\n").encode("ascii") + payload + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("ascii"))
        headers = {"Origin": BASE_URL, "Content-Type": "multipart/form-data; boundary=" + boundary}
        with opener.open(urllib.request.Request(BASE_URL + "/api/upload", data=b"".join(parts), headers=headers),
                         timeout=30) as response:
            return json.loads(response.read())

    def start_server():
        nonlocal server
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 8765))
        command = [args.server_python or sys.executable, str(Path(__file__).resolve()),
                   "--serve", str(data_root), "--events", str(events_path)]
        if args.diagnose_dailymotion_tail:
            command.append("--diagnose-dailymotion-tail")
        server = subprocess.Popen(command, cwd=data_root, stdout=log, stderr=subprocess.STDOUT,
                                  env={**os.environ, "PYTHONPATH": os.pathsep.join(
                                      [str(ROOT), os.environ.get("PYTHONPATH", "")])})
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("Isolated app exited during startup; see server.log.")
            try:
                request("/health")
                return server.pid
            except OSError:
                time.sleep(0.2)
        raise TimeoutError("Isolated app did not become ready.")

    def stop_server():
        nonlocal server
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
            server = None

    def events_for(identifier):
        if not events_path.exists():
            return []
        return [item for line in events_path.read_text(encoding="utf-8").splitlines()
                if (item := json.loads(line)).get("job_id") == identifier]

    def poll(path, item, timeout):
        deadline = time.monotonic() + timeout
        previous = None
        item["poll_count"] = 0
        item["transitions"] = []
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("Server exited during a real job.")
            state = request(path)
            item["poll_count"] += 1
            signature = (state["status"], state.get("stage"), state.get("completed"))
            if signature != previous:
                item["transitions"].append({"at": now(), **state})
                previous = signature
                checkpoint()
            if state["status"] in {"done", "error"}:
                return state
            time.sleep(0.5)
        raise TimeoutError(f"Real job exceeded {timeout} seconds; no simulated success was substituted.")

    def verify_saved(identifier, expected_url, expected_title):
        record = request("/api/library/" + identifier)
        assert record["source"] == expected_url and record["method"] == "local_audio_ai", record
        assert expected_title.casefold() in record["title"].casefold(), record["title"]
        segments = record["segments"]
        assert segments and all(isinstance(s["text"], str) and s["text"].strip() for s in segments)
        assert all(math.isfinite(s["start"]) and math.isfinite(s["end"]) and 0 <= s["start"] <= s["end"] for s in segments)
        assert all(a["start"] <= b["start"] for a, b in zip(segments, segments[1:]))
        with sqlite3.connect(f"file:{data_root / 'library.sqlite3'}?mode=ro", uri=True) as connection:
            row = connection.execute("SELECT source,title,segments FROM transcripts WHERE id=?", (identifier,)).fetchone()
        assert row and row[0] == record["source"] and row[1] == record["title"] and json.loads(row[2]) == segments
        write_json(output / "records" / (identifier + ".json"), record)
        payloads = {}
        for code in ("txt", "srt", "vtt", "json", "zip"):
            job_data = request(f"/api/jobs/{identifier}/download/{code}", as_json=False)
            library_data = request(f"/api/library/{identifier}/download/{code}", as_json=False)
            if code == "zip":
                assert zip_members(job_data) == zip_members(library_data)
            else:
                assert job_data == library_data, f"Job and library {code} differ."
            payloads[code] = library_data
            (output / "downloads" / (identifier + "." + code)).write_bytes(library_data)
        exported = json.loads(payloads["json"])
        for key in ("source", "title", "language", "method", "segments"):
            assert exported[key] == record[key], key
        if record.get("processing_metadata"):
            assert exported.get("processing_metadata") == record["processing_metadata"]
        for code in ("txt", "srt", "vtt"):
            text, cursor = payloads[code].decode("utf-8"), 0
            for segment in segments:
                spoken = segment["text"].strip().replace("\r", " ").replace("\n", " ")
                position = text.find(spoken, cursor)
                assert position >= cursor, f"Saved words missing or reordered in {code}."
                cursor = position + len(spoken)
        assert payloads["vtt"].startswith(b"WEBVTT\n")
        assert payloads["srt"].count(b" --> ") == len(segments)
        assert payloads["vtt"].count(b" --> ") == len(segments)
        members = zip_members(payloads["zip"])
        for code in ("txt", "srt", "vtt", "json"):
            assert members["transcript." + code] == payloads[code]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and list((data_root / "jobs" / identifier).glob("audio.*")):
            time.sleep(0.1)
        assert not list((data_root / "jobs" / identifier).glob("audio.*")), "Downloaded audio was not cleaned."
        evidence = events_for(identifier)
        assert any(e["kind"] == "acquisition_done" and e["audio_streams"] > 0 for e in evidence), evidence
        observations = transcription_evidence(evidence)
        assert any(e["kind"] == "recognition_done" and e["segment_count"] == len(segments) for e in evidence), evidence
        constructed = [{"start": round(float(segment["start"]), 3),
                        "end": round(float(segment["end"]), 3), "text": segment["text"].strip()}
                       for segment in observations["raw_segment_constructions"] if segment["text"].strip()]
        assert constructed == [{key: segment[key] for key in ("start", "end", "text")} for segment in segments], \
            "Raw model segment constructions do not match the normal saved text/times."
        successful_records[identifier] = record
        export_payloads[identifier] = payloads
        return {"id": identifier, "title": record["title"], "language": record["language"],
                "segment_count": len(segments), "events": evidence,
                **observations,
                "last_segment_end_seconds": max(s["end"] for s in segments),
                "maximum_segment_duration_seconds": max(s["end"] - s["start"] for s in segments),
                "exports": {code: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                            for code, data in payloads.items()},
                "sqlite_matches_saved_segments": True, "input_audio_cleaned": True,
                "raw_segment_constructions_match_saved_text_and_times": True,
                "export_text_order_preserved": True, "subtitle_time_accuracy": "not_evaluated"}

    try:
        report["initial_server_pid"] = start_server()
        for item in report["fixtures"]:
            fixture = FIXTURES[item["fixture"]]
            item.update(status="running", started_at=now(), url=fixture["url"])
            checkpoint()
            started = time.monotonic()
            try:
                posted = request("/api/link", {"url": fixture["url"], "mode": "audio",
                    "language": args.language, "model": args.model, "consent": "true"})
                item["job_id"] = posted["id"]
                final = poll("/api/jobs/" + posted["id"], item, args.timeout)
                item["final_job"] = final
                if final["status"] != "done":
                    raise RuntimeError(final.get("error") or "Actual provider job failed.")
                item["verification"] = verify_saved(posted["id"], fixture["url"], fixture["title_contains"])
                item["status"] = "pass"
            except TimeoutError:
                item["status"] = "incomplete"
                raise
            except Exception as error:
                item.update(status="fail", errors=exception_chain(error), traceback=traceback.format_exc())
            finally:
                if "job_id" in item:
                    item["events"] = events_for(item["job_id"])
                item["elapsed_seconds"] = round(time.monotonic() - started, 3)
                checkpoint()
                print(item["fixture"] + ": " + item["status"].upper(), flush=True)

        if args.diagnose_dailymotion_tail:
            item = next(item for item in report["fixtures"] if item["fixture"] == "dailymotion_tears_of_steel")
            if item["status"] != "pass":
                report["tail_diagnostic"].update(status="not_exercised", reason="The normal licensed fixture did not complete.")
            else:
                path = output / ("tail-diagnostic-" + item["job_id"] + ".json")
                deadline = time.monotonic() + 300
                while True:
                    diagnostic = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                    if diagnostic.get("complete") or diagnostic.get("execution_status") == "error":
                        break
                    if server.poll() is not None or time.monotonic() >= deadline:
                        report["tail_diagnostic"]["status"] = "incomplete"
                        raise TimeoutError("Bounded tail diagnostic did not finish; normal saved result was not replaced.")
                    time.sleep(0.25)
                report["tail_diagnostic"].update(status=diagnostic["execution_status"], report=path.name,
                    normal_record_unchanged=diagnostic.get("normal_record_unchanged"),
                    semantic_quality="unreviewed")
            checkpoint()

        passed = next((item for item in report["fixtures"] if item["status"] == "pass"), None)
        failed = next((item for item in report["fixtures"] if item["status"] == "fail" and item.get("final_job", {}).get("status") == "error"), None)
        batch = report["mixed_batch"]
        if passed and failed:
            batch.update(status="running", fixtures=[passed["fixture"], failed["fixture"]])
            checkpoint()
            fixtures = [FIXTURES[name] for name in batch["fixtures"]]
            try:
                posted = request("/api/batch", {"urls": "\n".join(f["url"] for f in fixtures), "mode": "audio",
                    "language": args.language, "model": args.model, "consent": "true"})
                batch_id = posted["id"]
                batch["id"] = batch_id
                final = poll("/api/batches/" + batch_id, batch, args.timeout * 2)
                batch["final_batch"] = final
                assert final["status"] == "done" and final["completed"] == 2 and final["failed"] == 1, final
                good, bad = final["jobs"]
                assert good["status"] == "done" and bad["status"] == "error", final
                batch["successful_job"] = verify_saved(good["id"], fixtures[0]["url"], fixtures[0]["title_contains"])
                batch_archive = request(f"/api/batches/{batch_id}/download", as_json=False)
                (output / "downloads" / "mixed-batch.zip").write_bytes(batch_archive)
                manifest = json.loads(zip_members(batch_archive)["batch-report.json"])
                assert manifest["failed"] == 1 and len(manifest["items"]) == 2, manifest
                batch.update(status="pass", manifest=manifest)
            except TimeoutError:
                batch["status"] = "incomplete"
                raise
            except Exception as error:
                batch.update(status="fail", errors=exception_chain(error), traceback=traceback.format_exc())
        else:
            batch.update(status="not_exercised", reason="Requires one actual successful and one actually failing licensed fixture.")
        checkpoint()

        if args.check_nonspeech:
            report["nonspeech"]["status"] = "running"
            for item in report["nonspeech"]["cases"]:
                item.update(status="running", started_at=now())
                checkpoint()
                started = time.monotonic()
                try:
                    payload, provenance = generated_nonspeech(item["kind"])
                    item["input"] = provenance
                    posted = upload_owned_wav("owned-" + item["kind"] + ".wav", payload)
                    item["job_id"] = posted["id"]
                    final = poll("/api/jobs/" + posted["id"], item, min(args.timeout, 180))
                    item["final_job"] = final
                    evidence = events_for(posted["id"])
                    starts = [event for event in evidence if event["kind"] == "recognition_start"]
                    assert len(starts) == 1 and starts[0]["audio_sha256"] == provenance["wav_sha256"], "Recognizer did not receive the exact owned no-speech WAV."
                    assert starts[0]["model"] == args.model
                    if final["status"] == "done":
                        record = request("/api/library/" + posted["id"])
                        write_json(output / "records" / ("nonspeech-" + posted["id"] + ".json"), record)
                        item["hallucinated_saved_record"] = "records/nonspeech-" + posted["id"] + ".json"
                    item["recognition_evidence"] = nonspeech_evidence(evidence, item["kind"])
                    assert abs(item["recognition_evidence"]["decoded_duration_seconds"] - NONSPEECH_SECONDS) <= 1 / 16000
                    if final["status"] == "done":
                        raise AssertionError("Actual ASR saved words from owned audio with no speech; raw normal output retained.")
                    assert final["error"] == "No spoken words were detected in this recording.", final
                    try:
                        request("/api/library/" + posted["id"])
                    except urllib.error.HTTPError as error:
                        assert error.code == 404, error.code
                    else:
                        raise AssertionError("No-speech input unexpectedly has a library record.")
                    with sqlite3.connect(f"file:{data_root / 'library.sqlite3'}?mode=ro", uri=True) as connection:
                        assert connection.execute("SELECT COUNT(*) FROM transcripts WHERE id=?", (posted["id"],)).fetchone()[0] == 0
                    deadline = time.monotonic() + 5
                    directory = data_root / "jobs" / posted["id"]
                    while time.monotonic() < deadline and list(directory.glob("input.*")):
                        time.sleep(0.1)
                    assert not list(directory.glob("input.*")), "Owned no-speech upload was not cleaned."
                    assert not list(directory.glob("transcript.*")), "No-speech input unexpectedly has transcript exports."
                    item.update(status="pass", library_record_absent=True, input_audio_cleaned=True)
                except TimeoutError:
                    item["status"] = "incomplete"
                    raise
                except Exception as error:
                    item.update(status="fail", errors=exception_chain(error), traceback=traceback.format_exc())
                finally:
                    if "job_id" in item:
                        item["events"] = events_for(item["job_id"])
                    item["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    checkpoint()
                    print("nonspeech_" + item["kind"] + ": " + item["status"].upper(), flush=True)
            report["nonspeech"]["status"] = "pass" if all(item["status"] == "pass"
                for item in report["nonspeech"]["cases"]) else "fail"
            checkpoint()

        restart = report["restart"]
        restart["status"] = "running"
        stop_server()
        report["restarted_server_pid"] = start_server()
        assert report["initial_server_pid"] != report["restarted_server_pid"]
        verified = []
        for identifier, record in successful_records.items():
            assert request("/api/library/" + identifier) == record
            for code, before in export_payloads[identifier].items():
                after = request(f"/api/library/{identifier}/download/{code}", as_json=False)
                assert (zip_members(after) == zip_members(before)) if code == "zip" else (after == before)
            verified.append(identifier)
        if batch_id is not None and batch_archive is not None:
            restored = request("/api/batches/" + batch_id)
            assert restored["status"] == "done" and restored["failed"] == 1, restored
            assert zip_members(request(f"/api/batches/{batch_id}/download", as_json=False)) == zip_members(batch_archive)
            restart["completed_batch_history_and_exports_preserved"] = True
        restart.update(status="pass" if verified else "not_exercised", verified_record_ids=verified)
        report["complete"] = True
    except BaseException as error:
        report["fatal"] = {"errors": exception_chain(error), "traceback": traceback.format_exc()}
        for item in report["fixtures"]:
            if item["status"] in {"pending", "running"}:
                item["status"] = "incomplete"
        for key in ("mixed_batch", "restart", "tail_diagnostic", "nonspeech"):
            if report[key]["status"] in {"pending", "running"}:
                report[key]["status"] = "incomplete"
        for item in report["nonspeech"]["cases"]:
            if item["status"] in {"pending", "running"}:
                item["status"] = "incomplete"
    finally:
        stop_server()
        for path in output.glob("tail-diagnostic-*.json"):
            partial = json.loads(path.read_text(encoding="utf-8"))
            if not partial.get("complete") and partial.get("execution_status") == "running":
                partial.update(execution_status="incomplete", interrupted_at=now())
                for item in partial.get("cases", []):
                    if item["status"] in {"pending", "running"}:
                        item["status"] = "incomplete"
                write_json(path, partial)
        log.close()
        if (data_root / "library.sqlite3").exists():
            with sqlite3.connect(data_root / "library.sqlite3") as source, sqlite3.connect(output / "library.sqlite3") as target:
                source.backup(target)
        scratch.cleanup()
        report["source_sha256_after"] = source_hashes()
        report["source_files_unchanged"] = report["source_sha256_before"] == report["source_sha256_after"]
        report["finished_at"] = now()
        report["all_selected_providers_passed"] = all(item["status"] == "pass" for item in report["fixtures"])
        passed = (report["complete"] and report["all_selected_providers_passed"] and report["source_files_unchanged"]
                  and report["restart"]["status"] == "pass" and report["mixed_batch"]["status"] != "fail"
                  and report["tail_diagnostic"]["status"] in {"not_requested", "not_exercised", "completed"}
                  and report["nonspeech"]["status"] in {"not_requested", "pass"})
        if args.require_mixed_batch:
            passed = passed and report["mixed_batch"]["status"] == "pass"
        report["result"] = "pass" if passed else "fail"
        checkpoint()
    print(json.dumps({"result": report["result"], "complete": report["complete"],
                      "report": str(output / "provider-report.json")}), flush=True)
    return 0 if report["result"] == "pass" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="append", choices=sorted(FIXTURES))
    parser.add_argument("--model", choices=("tiny", "base", "small", "large-v3-turbo"), default="tiny")
    parser.add_argument("--language", choices=("auto", "en", "el"), default="auto")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", type=Path, default=Path("qa-real-links"))
    parser.add_argument("--server-python", help="Python executable containing the app's installed dependencies")
    parser.add_argument("--require-mixed-batch", action="store_true")
    parser.add_argument("--diagnose-dailymotion-tail", action="store_true",
                        help="Separately diagnose three bounded licensed tail excerpts after normal saving/cleanup")
    parser.add_argument("--check-nonspeech", action="store_true",
                        help="Exercise real ASR on owned silence/noise; any saved words fail the no-speech gate")
    parser.add_argument("--serve", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--events", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        if not args.events:
            parser.error("Private --serve entry requires --events")
        serve(args.serve, args.events, args.diagnose_dailymotion_tail)
        return 0
    if not 30 <= args.timeout <= 3600:
        parser.error("--timeout must be between 30 and 3600 seconds per source")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
