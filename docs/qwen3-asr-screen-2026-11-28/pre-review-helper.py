"""Hosted-only, pinned native Qwen3-ASR development screen; no production imports.

The default action validates declarations without importing any ML package.
Heavy downloads/model execution require the explicit GitHub Actions environment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def safe_filename(name):
    require(isinstance(name, str) and name and "\\" not in name, "invalid filename")
    value = PurePosixPath(name)
    require(not value.is_absolute() and len(value.parts) == 1 and value.name not in {".", ".."},
            "filename must be a single relative component")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) is not None, "unsafe filename")
    return name


def repo_file(relative):
    require(isinstance(relative, str) and not Path(relative).is_absolute(), "repository path must be relative")
    path = (ROOT / relative).resolve()
    require(path.is_relative_to(ROOT.resolve()), "repository path escape")
    return path


def public_url_without_query(url):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password,
            "only anonymous HTTPS sources are allowed")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def cpu_selection(available, maximum=4):
    selected = sorted(set(available))[:maximum]
    require(selected and maximum == 4, "one to four available CPUs are required")
    return selected


def validate_generation(prefix, sequence, streamed, eos_ids, maximum):
    require(all(type(x) is int and x >= 0 for x in prefix + sequence + streamed), "invalid token IDs")
    suffix = sequence[len(prefix):]
    return {
        "nonempty_input_prefix": bool(prefix),
        "input_prefix_unchanged": sequence[:len(prefix)] == prefix,
        "streamed_sequence_matches_returned": streamed == sequence,
        "nonempty_generated_suffix": bool(suffix),
        "within_declared_token_bound": 0 < len(suffix) <= maximum,
        "ended_with_native_eos": bool(suffix) and suffix[-1] in eos_ids,
        "no_tokens_after_eos": not any(token in eos_ids for token in suffix[:-1]),
    }


def raw_asr_body(text):
    """Split only the native format marker; never repair repetitions or words."""
    marker = "<asr_text>"
    return text.split(marker, 1)[1] if marker in text else text


def mel_contract(sample_count):
    require(sample_count > 8000 and sample_count % 160 == 0, "unexpected fixed short-clip framing")
    valid = sample_count // 160
    padded = ((valid + 99) // 100) * 100
    remainder = valid % 100
    after_first = (remainder - 1) // 2 + 1
    after_second = (after_first - 1) // 2 + 1
    tokens = (after_second - 1) // 2 + 1 + (valid // 100) * 13
    return {"valid_frames": valid, "padded_frames": padded, "audio_placeholder_tokens": tokens}


def validate_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    require(plan["model_id"] == "Qwen/Qwen3-ASR-0.6B-hf", "wrong native checkpoint")
    require(plan["model_revision"] == "7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c", "wrong checkpoint revision")
    require(plan["runtime_versions"]["torch"] == "2.15.0+cpu" and
            plan["runtime_versions"]["transformers"] == "5.13.0", "wrong CPU/native runtime pins")
    require(plan["dtype"] == "float32" and plan["trust_remote_code"] is False, "wrong loading policy")
    require(plan["source_language_argument"] is None and plan["target_language_argument"] is None,
            "language guidance is forbidden")
    require(plan["attempts_per_case"] == plan["model_initializations"] == 1, "one attempt protocol required")
    require(plan["rss_limit_bytes"] == 6 * 1024**3, "declared 6 GiB process-group limit required")
    require(plan["generation"] == {"max_new_tokens": 512, "do_sample": False, "num_beams": 1,
                                   "eos_token_id": [151643, 151645], "pad_token_id": 151645},
            "native greedy completion policy changed")
    require(len(plan["cases"]) == 8 and len({x["id"] for x in plan["cases"]}) == 8, "fixed eight cases required")
    for item in plan["source_files"]:
        source = repo_file(item["path"])
        require(source.is_file() and source.stat().st_size == item["bytes"] and sha256(source) == item["sha256"],
                "frozen source changed: " + item["path"])
    fixture_data = json.loads(repo_file(plan["original_fixtures_path"]).read_text(encoding="utf-8"))
    original = {x["id"]: x for x in fixture_data["cases"]}
    arrays = {x["id"]: x for x in json.loads(repo_file(plan["original_arrays_path"]).read_text(encoding="utf-8"))["cases"]}
    require([x["id"] for x in plan["cases"]] == list(original), "original eight cases/order changed")
    for item in plan["cases"]:
        safe_filename(item["id"])
        previous = original[item["id"]]
        array = arrays[item["id"]]
        require(item["audio_sha256"] == previous["audio_sha256"] and
                item["sample_count"] == previous["provenance"]["dataset_num_samples"] and
                item["sample_rate_hz"] == previous["provenance"]["dataset_sample_rate"] == 16000,
                "original recording identity changed")
        require(item["pcm_sha256"] == array["pcm_sha256"] and
                item["sample_count"] == array["sample_count"] and array["dtype"] == "<f4" and
                array["full_untrimmed_recording"] is True and array["vad_applied"] is False,
                "original complete PCM identity changed")
        mel_contract(item["sample_count"])
    files = json.loads(repo_file(plan["model_files_path"]).read_text(encoding="utf-8"))
    require(files["repo_id"] == plan["model_id"] and files["revision"] == plan["model_revision"], "model inventory mismatch")
    for item in files["files"]:
        safe_filename(item["filename"])
        require(item["immutable_url"].startswith("https://huggingface.co/" + plan["model_id"] + "/resolve/" +
                                                plan["model_revision"] + "/"), "non-pinned model URL")
        require(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None, "invalid SHA256")
    return plan


def require_hosted():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and sys.platform == "linux",
            "large downloads and inference are restricted to the authorized Linux GitHub Actions screen")


def download_pinned(url, destination, expected_bytes, expected_sha, seconds):
    public_url_without_query(url)
    destination = Path(destination)
    require(not destination.exists() and not destination.is_symlink(), "download target already exists")
    temporary = destination.with_suffix(destination.suffix + ".partial")
    require(not temporary.exists(), "partial download already exists; no automatic retry")
    started = time.monotonic()
    digest = hashlib.sha256()
    count = 0
    with urllib.request.urlopen(url, timeout=30) as response, temporary.open("xb") as output:
        while True:
            data = response.read(1024 * 1024)
            if not data:
                break
            count += len(data)
            require(count <= expected_bytes, "download exceeds pinned byte size")
            require(time.monotonic() - started <= seconds, "download wall time limit")
            output.write(data)
            digest.update(data)
    require(count == expected_bytes and digest.hexdigest() == expected_sha, "download identity mismatch")
    temporary.replace(destination)
    return {"url_without_query": public_url_without_query(url), "bytes": count,
            "sha256": digest.hexdigest(), "elapsed_seconds": time.monotonic() - started}


def decode_complete_wav(path):
    """Same signed-16-bit conversion as the prior complete application arrays."""
    import av
    import numpy as np
    output = io.BytesIO()
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    with av.open(str(path), mode="r", metadata_errors="ignore") as container:
        require(len(container.streams.audio) == 1, "one audio stream required")
        for frame in container.decode(audio=0):
            frame.pts = None
            for converted in resampler.resample(frame):
                output.write(converted.to_ndarray().tobytes())
        for converted in resampler.resample(None):
            output.write(converted.to_ndarray().tobytes())
    return np.frombuffer(output.getbuffer(), dtype=np.int16).astype(np.float32) / 32768.0


def prepare_inputs(plan, evidence, local_audio=None):
    import numpy as np
    inputs = evidence / "inputs"
    inputs.mkdir(exist_ok=False)
    report = {"started_at": now(), "complete": False, "speech_model_initialized": False,
              "source": "verified retained local WAVs" if local_audio else "fresh public original dataset rows",
              "cases": []}
    write_json(evidence / "input-preparation.json", report)
    fixtures = {x["id"]: x for x in json.loads(repo_file(plan["original_fixtures_path"]).read_text(encoding="utf-8"))["cases"]}
    try:
        for item in plan["cases"]:
            fixture = fixtures[item["id"]]
            row = {"id": item["id"], "attempt": 1}
            report["cases"].append(row)
            target = inputs / (item["id"] + ".wav")
            if local_audio:
                source = local_audio / (item["id"] + ".wav")
                require(source.stat().st_size == fixture["audio_bytes"] and sha256(source) == item["audio_sha256"],
                        "local original WAV identity differs")
                shutil.copyfile(source, target)
            else:
                url = fixture["provenance"]["rows_api_url"]
                require(urllib.parse.urlsplit(url).hostname == "datasets-server.huggingface.co", "unexpected dataset host")
                with urllib.request.urlopen(url, timeout=30) as response:
                    raw = response.read(2 * 1024 * 1024 + 1)
                require(len(raw) <= 2 * 1024 * 1024, "oversized source metadata")
                rows = json.loads(raw)["rows"]
                require(len(rows) == 1 and rows[0]["row_idx"] == fixture["provenance"]["row_index"], "dataset row mismatch")
                source = rows[0]["row"]
                require(source["id"] == fixture["provenance"]["sentence_id"] and
                        source["num_samples"] == item["sample_count"] and
                        source["raw_transcription"] == fixture["reference"], "dataset source identity changed")
                audio_url = source["audio"][0]["src"]
                require(public_url_without_query(audio_url) == fixture["provenance"]["viewer_asset_url_without_query"],
                        "dataset asset path changed")
                row["download"] = download_pinned(audio_url, target, fixture["audio_bytes"], item["audio_sha256"], 60)
            waveform = decode_complete_wav(target)
            require(waveform.dtype.str == "<f4" and waveform.shape == (item["sample_count"],), "full decoded array mismatch")
            require(hashlib.sha256(waveform.tobytes()).hexdigest() == item["pcm_sha256"], "decoded PCM differs from prior full array")
            array_file = inputs / (item["id"] + ".npy")
            np.save(array_file, waveform, allow_pickle=False)
            row.update({"original_audio_sha256": sha256(target), "sample_count": waveform.size,
                        "sample_rate_hz": 16000, "dtype": waveform.dtype.str,
                        "pcm_sha256": item["pcm_sha256"], "array_sha256": sha256(array_file),
                        "status": "pass", "full_untrimmed_recording": True})
            write_json(evidence / "input-preparation.json", report)
        report["complete"] = True
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["finished_at"] = now()
        write_json(evidence / "input-preparation.json", report)


def download_model(plan, work, evidence):
    require_hosted()
    folder = work / "model"
    folder.mkdir(exist_ok=False)
    report = {"started_at": now(), "complete": False, "model_initialized": False,
              "model_id": plan["model_id"], "revision": plan["model_revision"], "files": []}
    write_json(evidence / "model-download.json", report)
    try:
        for item in json.loads(repo_file(plan["model_files_path"]).read_text(encoding="utf-8"))["files"]:
            row = {"filename": item["filename"], "attempt": 1, "status": "started"}
            report["files"].append(row)
            write_json(evidence / "model-download.json", report)
            row.update(download_pinned(item["immutable_url"], folder / safe_filename(item["filename"]),
                                       item["bytes"], item["sha256"], plan["per_file_download_seconds"]))
            row["status"] = "verified"
        report["complete"] = True
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["finished_at"] = now()
        write_json(evidence / "model-download.json", report)


def verify_model(plan, folder):
    for item in json.loads(repo_file(plan["model_files_path"]).read_text(encoding="utf-8"))["files"]:
        path = folder / item["filename"]
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == item["bytes"] and
                sha256(path) == item["sha256"], "model file identity differs: " + item["filename"])


def group_rss(pgid):
    total = 0
    page = os.sysconf("SC_PAGE_SIZE")
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == pgid:
                total += int((path / "statm").read_text().split()[1]) * page
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return total


def terminate_owned(process):
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def worker(plan, plan_path, work, evidence, expected_plan_sha):
    require_hosted()
    require(sha256(plan_path) == expected_plan_sha, "worker plan identity changed")
    import importlib.metadata
    import resource
    cpu_ids = cpu_selection(os.sched_getaffinity(0))
    os.sched_setaffinity(0, set(cpu_ids))
    report = {"started_at": now(), "complete": False, "structural_pass": False,
              "semantic_quality": "unreviewed", "plan_sha256": expected_plan_sha,
              "helper_sha256": sha256(__file__), "commit": os.environ.get("GITHUB_SHA"),
              "model_initialized": False, "model_initializations": 0, "cases": [],
              "runtime_versions": {}, "python_network_attempts": [], "cpu_affinity": cpu_ids,
              "source_language_argument": None, "target_language_argument": None,
              "references_supplied_to_decoder": False, "app_integration": False,
              "fresh_validation": False, "timestamps_produced": False}
    output = evidence / "recognizer-report.json"
    progress_path = evidence / "progress.json"
    started = time.monotonic()

    def progress(stage, case_id=None):
        write_json(progress_path, {"stage": stage, "case_id": case_id,
                                   "started_monotonic": time.monotonic(), "at": now(), "pid": os.getpid()})

    def deny_network(event, arguments):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            report["python_network_attempts"].append({"event": event, "at": now()})
            raise RuntimeError("network disabled during offline model initialization and recognition")

    sys.addaudithook(deny_network)
    write_json(output, report)
    try:
        progress("initialization")
        for name, expected in plan["runtime_versions"].items():
            actual = importlib.metadata.version(name)
            report["runtime_versions"][name] = actual
            require(actual == expected, "runtime pin differs: " + name)
        verify_model(plan, work / "model")
        import numpy as np
        import torch
        from transformers import Qwen3ASRForConditionalGeneration, Qwen3ASRProcessor
        from transformers.generation.streamers import BaseStreamer

        require(torch.version.cuda is None and not torch.cuda.is_available(), "CPU-only PyTorch required")
        torch.set_num_threads(len(cpu_ids))
        torch.set_num_interop_threads(1)
        torch.set_float32_matmul_precision("highest")
        torch.manual_seed(plan["qa_seed"])
        np.random.seed(plan["qa_seed"])
        report["actual_torch"] = {"version": torch.__version__, "cuda_version": torch.version.cuda,
                                  "intra_threads": torch.get_num_threads(), "inter_threads": torch.get_num_interop_threads(),
                                  "float32_matmul_precision": torch.get_float32_matmul_precision()}
        processor = Qwen3ASRProcessor.from_pretrained(str(work / "model"), local_files_only=True, trust_remote_code=False)
        report["model_initialization_attempted"] = True
        write_json(output, report)
        model = Qwen3ASRForConditionalGeneration.from_pretrained(
            str(work / "model"), local_files_only=True, trust_remote_code=False,
            use_safetensors=True, dtype=torch.float32, attn_implementation="eager")
        report["model_initialized"] = True
        report["model_initializations"] = 1
        model.eval()
        require(type(model).__name__ == "Qwen3ASRForConditionalGeneration", "unexpected native model class")
        require(all(p.device.type == "cpu" and (not p.is_floating_point() or p.dtype == torch.float32)
                    for p in model.parameters()), "non-CPU or non-FP32 model parameter")
        effective = model.generation_config.to_dict()
        report["publisher_generation_config"] = effective
        require(effective["eos_token_id"] == plan["generation"]["eos_token_id"] and
                effective["pad_token_id"] == plan["generation"]["pad_token_id"] and
                effective["max_new_tokens"] == plan["generation"]["max_new_tokens"] and
                effective.get("do_sample", False) is False, "publisher generation config changed")
        report.update({"model_initialized": True, "model_initializations": 1,
                       "initialization_seconds": time.monotonic() - started,
                       "model_class": type(model).__name__, "processor_class": type(processor).__name__,
                       "model_config": model.config.to_dict(), "publisher_generation_config": effective,
                       "declared_generation_policy": plan["generation"],
                       "tokenizer_pad_token_id": processor.tokenizer.pad_token_id,
                       "tokenizer_pad_token": processor.tokenizer.pad_token,
                       "feature_extractor_config": processor.feature_extractor.to_dict()})
        require(report["initialization_seconds"] <= plan["startup_seconds"], "recorded initialization time exceeded cap")
        report["native_runtime_source_files"] = {}
        for component in (type(model), type(processor), type(processor.feature_extractor)):
            module_path = Path(sys.modules[component.__module__].__file__)
            report["native_runtime_source_files"][component.__module__] = {
                "filename": module_path.name, "sha256": sha256(module_path)}
        current = {}
        extractor_class = type(processor.feature_extractor)
        original_extractor_call = extractor_class.__call__

        def observe_features(instance, raw_speech, *args, **kwargs):
            arrays = [raw_speech] if isinstance(raw_speech, np.ndarray) and raw_speech.ndim == 1 else list(raw_speech)
            require(len(arrays) == 1, "batch must contain one complete recording")
            array = np.asarray(arrays[0])
            require(array.dtype.str == "<f4" and array.shape == (current["sample_count"],), "frontend waveform changed")
            actual_hash = hashlib.sha256(array.tobytes()).hexdigest()
            require(actual_hash == current["pcm_sha256"], "frontend did not receive exact complete PCM")
            require(kwargs.get("sampling_rate") == 16000 and kwargs.get("truncation") is False and
                    kwargs.get("padding") is True and kwargs.get("return_attention_mask") is True and
                    kwargs.get("n_window") == 50, "native frontend options differ")
            value = original_extractor_call(instance, raw_speech, *args, **kwargs)
            require(hashlib.sha256(array.tobytes()).hexdigest() == actual_hash, "frontend modified source PCM")
            mask = value["attention_mask"].detach().cpu().numpy()
            features = value["input_features"].detach().cpu().numpy()
            contract = mel_contract(current["sample_count"])
            expected_mask = np.zeros((1, contract["padded_frames"]), dtype=mask.dtype)
            expected_mask[:, :contract["valid_frames"]] = 1
            require(features.shape == (1, 128, contract["padded_frames"]) and features.dtype.str == "<f4" and
                    np.isfinite(features).all() and np.array_equal(mask, expected_mask), "full mel/mask contract differs")
            current["feature_extractor_calls"] = current.get("feature_extractor_calls", 0) + 1
            current["features"] = {"full_input_pcm_sha256": actual_hash, "shape": list(features.shape),
                                   "dtype": features.dtype.str, "sha256": hashlib.sha256(features.tobytes()).hexdigest(),
                                   "mask": mask.tolist(), "mask_dtype": mask.dtype.str, **contract,
                                   "actual_options": {k: kwargs[k] for k in ["sampling_rate", "truncation", "padding",
                                                                            "return_attention_mask", "n_window"]}}
            return value

        extractor_class.__call__ = observe_features

        def observe_forward(module, arguments, kwargs):
            features = kwargs.get("input_features")
            if features is not None:
                array = features.detach().cpu().numpy()
                mask = kwargs["input_features_mask"].detach().cpu().numpy()
                require(hashlib.sha256(array.tobytes()).hexdigest() == current["features"]["sha256"] and
                        mask.tolist() == current["features"]["mask"], "model received altered audio features or mask")
                current["audio_encoder_input_calls"] = current.get("audio_encoder_input_calls", 0) + 1

        forward_hook = model.model.audio_tower.register_forward_pre_hook(observe_forward, with_kwargs=True)

        class RawTokenStreamer(BaseStreamer):
            def __init__(self, path):
                self.path = path
                self.tokens = []
                self.ended = False
            def put(self, value):
                ids = value.detach().cpu().reshape(-1).tolist()
                self.tokens.extend(ids)
                write_json(self.path, {"case_id": current["id"], "token_ids_including_prompt": self.tokens,
                                       "streamer_end_called": False, "updated_at": now()})
            def end(self):
                self.ended = True
                write_json(self.path, {"case_id": current["id"], "token_ids_including_prompt": self.tokens,
                                       "streamer_end_called": True, "updated_at": now()})

        try:
            for item in plan["cases"]:
                case_start = time.monotonic()
                current = {"id": item["id"], "attempt": 1, "sample_count": item["sample_count"],
                           "pcm_sha256": item["pcm_sha256"], "started_at": now(), "checks": {}}
                report["cases"].append(current)
                progress("recognition", item["id"])
                write_json(output, report)
                waveform = np.load(evidence / "inputs" / (item["id"] + ".npy"), allow_pickle=False)
                require(waveform.shape == (item["sample_count"],) and waveform.dtype.str == "<f4" and
                        hashlib.sha256(waveform.tobytes()).hexdigest() == item["pcm_sha256"], "complete input identity differs")
                inputs = processor.apply_transcription_request(audio=waveform, language=None)
                require(current["feature_extractor_calls"] == 1, "expected one complete frontend call")
                require(all(value.device.type == "cpu" for value in inputs.values() if hasattr(value, "device")),
                        "processor tensors must remain on CPU")
                prefix = inputs["input_ids"][0].tolist()
                placeholders = prefix.count(model.config.audio_token_id)
                require(placeholders == current["features"]["audio_placeholder_tokens"], "audio token/feature count mismatch")
                current["model_inputs"] = {"input_ids": prefix, "attention_mask": inputs["attention_mask"].tolist(),
                                            "audio_placeholder_count": placeholders,
                                            "rendered_native_prompt": processor.tokenizer.decode(prefix, skip_special_tokens=False,
                                                                                                 clean_up_tokenization_spaces=False)}
                streamer = RawTokenStreamer(evidence / "token-progress" / (item["id"] + ".json"))
                with torch.inference_mode(), torch.autocast("cpu", enabled=False):
                    generated = model.generate(**inputs, do_sample=False, num_beams=1,
                                               max_new_tokens=plan["generation"]["max_new_tokens"],
                                               return_dict_in_generate=True, streamer=streamer)
                sequence = generated.sequences[0].detach().cpu().tolist()
                suffix = sequence[len(prefix):]
                current["completion_checks"] = validate_generation(prefix, sequence, streamer.tokens,
                                                                    plan["generation"]["eos_token_id"],
                                                                    plan["generation"]["max_new_tokens"])
                current["raw_sequence_ids"] = sequence
                current["raw_generated_ids"] = suffix
                current["raw_generated_tokens"] = processor.tokenizer.convert_ids_to_tokens(suffix)
                current["raw_decoded_with_special_tokens"] = processor.tokenizer.decode(
                    suffix, skip_special_tokens=False, clean_up_tokenization_spaces=False)
                without_eos = suffix[:-1] if suffix and suffix[-1] in plan["generation"]["eos_token_id"] else suffix
                raw_text = processor.tokenizer.decode(without_eos, skip_special_tokens=False, clean_up_tokenization_spaces=False)
                current["raw_decoded_without_terminal_eos"] = raw_text
                current["raw_transcript_without_repetition_repair"] = raw_asr_body(raw_text)
                current["native_parsed_result"] = processor.decode(suffix, return_format="parsed", clean_up_tokenization_spaces=False)
                current["native_parser_rewrites_raw_transcript"] = (
                    current["native_parsed_result"]["transcription"] != raw_asr_body(raw_text).strip())
                current["checks"] = {**current["completion_checks"], "streamer_end_called": streamer.ended,
                                      "native_asr_marker_present_once": raw_text.count("<asr_text>") == 1,
                                      "nonempty_raw_transcript": bool(raw_asr_body(raw_text).strip()),
                                      "full_input_unchanged": hashlib.sha256(waveform.tobytes()).hexdigest() == item["pcm_sha256"],
                                      "one_complete_frontend_call": current["feature_extractor_calls"] == 1,
                                      "one_bound_audio_encoder_call": current.get("audio_encoder_input_calls", 0) == 1}
                current["structural_status"] = "pass" if all(current["checks"].values()) else "fail"
                current["elapsed_seconds"] = time.monotonic() - case_start
                current["recorded_process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
                current["finished_at"] = now()
                write_json(output, report)
                require(current["recorded_process_peak_rss_bytes"] <= plan["rss_limit_bytes"], "recorded RSS exceeded cap")
                require(current["elapsed_seconds"] <= plan["per_case_seconds"], "recorded case time exceeded cap")
        finally:
            extractor_class.__call__ = original_extractor_call
            forward_hook.remove()
        validate_plan(plan_path)
        verify_model(plan, work / "model")
        report["pinned_sources_and_model_files_unchanged"] = True
        report["complete"] = len(report["cases"]) == 8
        report["structural_pass"] = report["complete"] and all(x.get("structural_status") == "pass" for x in report["cases"])
        progress("complete")
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        report["finished_at"] = now()
        report["elapsed_seconds"] = time.monotonic() - started
        report["recorded_process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        report["recorded_limits_pass"] = (report["elapsed_seconds"] <= plan["total_worker_seconds"] and
                                          report["recorded_process_peak_rss_bytes"] <= plan["rss_limit_bytes"])
        report["structural_pass"] = report["structural_pass"] and report["recorded_limits_pass"]
        write_json(output, report)
    return 0 if report["structural_pass"] else 1


def execute(plan, plan_path, work, evidence):
    require_hosted()
    require(json.loads((evidence / "input-preparation.json").read_text())["complete"], "inputs not fully prepared")
    require(json.loads((evidence / "model-download.json").read_text())["complete"], "model files not fully verified")
    marker = evidence / "execution-requested.json"
    with marker.open("x") as output:
        json.dump({"started_at": now(), "plan_sha256": sha256(plan_path), "one_attempt_only": True}, output)
    cpu_ids = cpu_selection(os.sched_getaffinity(0))
    env = {key: value for key, value in os.environ.items() if key in {
        "PATH", "LANG", "LC_ALL", "TZ", "TMPDIR", "TEMP", "TMP", "VIRTUAL_ENV", "SYSTEMROOT", "HOME",
        "GITHUB_ACTIONS", "GITHUB_SHA", "CI"}}
    env.update(plan["worker_environment"])
    env["OMP_NUM_THREADS"] = env["MKL_NUM_THREADS"] = str(len(cpu_ids))
    env["HF_HOME"] = str(work / "offline-hf-cache")
    command = [sys.executable, str(Path(__file__).resolve()), "--action", "worker", "--plan", str(plan_path.resolve()),
               "--work", str(work.resolve()), "--evidence", str(evidence.resolve()), "--expected-plan-sha", sha256(plan_path)]
    started = time.monotonic()
    summary = {"started_at": now(), "plan_sha256": sha256(plan_path), "command": command,
               "cpu_affinity": cpu_ids, "sampled_group_peak_rss_bytes": 0, "stop_reason": None}
    with (evidence / "worker.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        summary["owned_process_group_id"] = process.pid
        code = None
        try:
            while process.poll() is None:
                elapsed = time.monotonic() - started
                summary["sampled_group_peak_rss_bytes"] = max(summary["sampled_group_peak_rss_bytes"], group_rss(process.pid))
                reason = None
                if summary["sampled_group_peak_rss_bytes"] > plan["rss_limit_bytes"]:
                    reason = "owned_process_group_rss_limit"
                if elapsed > plan["total_worker_seconds"]:
                    reason = "total_worker_time_limit"
                progress_path = evidence / "progress.json"
                if progress_path.exists():
                    progress = json.loads(progress_path.read_text())
                    summary["last_observed_progress"] = progress
                    if progress["stage"] == "initialization" and elapsed > plan["startup_seconds"]:
                        reason = "startup_time_limit"
                    if progress["stage"] == "recognition" and time.monotonic() - progress["started_monotonic"] > plan["per_case_seconds"]:
                        reason = "case_time_limit"
                elif elapsed > plan["startup_seconds"]:
                    reason = "worker_start_time_limit"
                if reason:
                    summary["stop_reason"] = reason
                    terminate_owned(process)
                    break
                time.sleep(0.1)
            code = process.wait(timeout=5)
        except Exception as error:
            summary["stop_reason"] = "controller_error"
            summary["controller_failure"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            terminate_owned(process)
            code = process.poll()
    summary.update({"finished_at": now(), "elapsed_seconds": time.monotonic() - started, "returncode": code,
                    "owned_worker_exited": process.poll() is not None})
    if summary["elapsed_seconds"] > plan["total_worker_seconds"] and summary["stop_reason"] is None:
        summary["stop_reason"] = "recorded_total_time_exceeded"
    write_json(evidence / "execution.json", summary)
    return 0 if code == 0 and summary["stop_reason"] is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=["validate", "prepare-inputs", "download-model", "execute", "worker"], default="validate")
    parser.add_argument("--plan", type=Path, default=ROOT / "docs/qwen3-asr-screen-2026-11-28/plan.json")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--local-audio", type=Path, help="Preparation-only reuse of exact original WAVs; never changes required hashes")
    parser.add_argument("--expected-plan-sha", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.evidence:
        args.evidence.mkdir(parents=True, exist_ok=True)
    try:
        plan = validate_plan(args.plan)
        if args.action == "validate":
            result = {"validated_at": now(), "plan_sha256": sha256(args.plan), "helper_sha256": sha256(__file__),
                      "model_initialized": False, "inference_performed": False, "python": sys.version,
                      "platform": platform.platform(), "github_sha": os.environ.get("GITHUB_SHA")}
            if args.evidence:
                write_json(args.evidence / "preflight.json", result)
            print(json.dumps(result))
            return 0
        require(args.work is not None and args.evidence is not None, "work/evidence directories required")
        args.work.mkdir(parents=True, exist_ok=True)
        require(args.work.resolve() != args.evidence.resolve() and
                not args.work.resolve().is_relative_to(args.evidence.resolve()), "weights/work must remain outside uploaded evidence")
        if args.action == "prepare-inputs":
            prepare_inputs(plan, args.evidence, args.local_audio)
        elif args.action == "download-model":
            download_model(plan, args.work, args.evidence)
        elif args.action == "execute":
            return execute(plan, args.plan, args.work, args.evidence)
        else:
            return worker(plan, args.plan, args.work, args.evidence, args.expected_plan_sha)
        return 0
    except Exception as error:
        result = {"failed_at": now(), "action": args.action, "error_type": type(error).__name__, "error": str(error),
                  "model_initialization_not_claimed_by_controller": True}
        if args.evidence:
            write_json(args.evidence / (args.action + "-failure.json"), result)
        print(json.dumps(result), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
