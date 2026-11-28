"""One hosted, source-bound actual speaker pipeline; preparation is not inference.

Reuse the previously reviewed download/owned-process primitives. Never change
application settings, substitute a model, retry recognition, or expose references
to the recognizer. Local validation uses only the standard library.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_speaker_shared_qa", Path(__file__).with_name("qa_qwen3_asr_candidate.py"))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
require, sha, write_json = common.require, common.sha256, common.write_json
DEFAULT_PLAN = ROOT / "docs/asr-speaker-timing-integration-2026-11-28/hosted-plan.json"


def validate(plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    require(plan["protocol"] == "single_original_two_reader_speaker_pipeline_v1", "Wrong protocol")
    require(plan["attempts"] == 1 and plan["model_execution_hosted_only"] is True, "Wrong execution scope")
    for item in plan["source_files"]:
        source = common.repo_file(item["path"])
        require(sha(source) == item["sha256"], "Frozen source changed: " + item["path"])
    require(plan["fixture"]["sha256"] == "dc977c1cb0af1a30946eeb0c59218039987412462d2e8c5a2d23990b559f087f",
            "Original two-reader fixture changed")
    require(plan["fixture"]["filename"] == "two_speakers_returning.wav", "Unexpected fixture output path")
    require(len(plan["fixture"]["sources"]) == 4 and len(plan["fixture"]["reference_intervals"]) == 4,
            "Incomplete fixture construction")
    require(set(plan["models"]) == {"recognizer", "speaker"} and
            plan["models"]["recognizer"]["repo"] == "Systran/faster-whisper-small" and
            plan["models"]["speaker"]["repo"] == "speechbrain/spkrec-ecapa-voxceleb" and
            plan["models"]["recognizer"]["revision"] == "536b0662742c02347bc0e980a01041f333bce120" and
            plan["models"]["speaker"]["revision"] == "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286",
            "Model identity changed")
    require(plan["rss_limit_bytes"] == 6 * 1024 ** 3 and plan["total_worker_seconds"] == 600 and
            plan["maximum_cpus"] == 4, "Resource contract changed")
    return plan


def download_checked(url, target, digest, maximum_bytes, expected_bytes=None):
    """One anonymous HTTPS transfer; retain any partial failure without retry."""
    import hashlib
    common.public_url_without_query(url)
    require(not target.exists() and not target.with_suffix(target.suffix + ".partial").exists(), "Download already attempted")
    partial = target.with_suffix(target.suffix + ".partial")
    started, size, actual = time.monotonic(), 0, hashlib.sha256()
    with urllib.request.urlopen(url, timeout=30) as response, partial.open("xb") as output:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            require(size <= maximum_bytes and time.monotonic() - started <= 240, "Download resource limit")
            output.write(chunk)
            actual.update(chunk)
    require(actual.hexdigest() == digest and (expected_bytes is None or size == expected_bytes), "Downloaded identity mismatch")
    partial.replace(target)
    return {"url_without_query": common.public_url_without_query(url), "bytes": size, "sha256": digest}


def model_path(plan, work, family):
    if family == "recognizer":
        return work / "hf/hub/models--Systran--faster-whisper-small/snapshots" / plan["models"][family]["revision"]
    return work / "speaker-cache"


def construct_fixture(sources, full_clips, target):
    """Exact historical two-reader construction, independently testable offline."""
    import hashlib
    import wave
    import numpy as np
    from smoke_real_speakers import write_wav
    require(len(sources) == len(full_clips) == 4, "Four original source clips required")
    pieces, references, offset = [np.zeros(8000, dtype=np.float32)], [], 8000
    for source, full in zip(sources, full_clips):
        require(full.dtype == np.float32 and full.ndim == 1 and 64000 <= len(full) <= 30 * 16000 and
                bool(np.isfinite(full).all()), "Invalid complete fixture source")
        clip = full[:8 * 16000]
        references.append({"start": offset / 16000, "end": (offset + len(clip)) / 16000,
                           "speaker": source["speaker_id"], "short": False})
        pieces.extend([clip, np.zeros(9600, dtype=np.float32)])
        offset += len(clip) + 9600
    joined = np.concatenate(pieces)
    write_wav(target, joined)
    with wave.open(str(target), "rb") as wav:
        require((wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) ==
                (1, 2, 16000, len(joined)), "Wrong complete WAV format")
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    return {"sha256": sha(target), "sample_count": len(joined), "reference_intervals": references,
            "decoded_pcm_sha256": hashlib.sha256(pcm.tobytes()).hexdigest()}


def prepare(plan, work, evidence):
    common.require_hosted()
    inputs = evidence / "inputs"
    inputs.mkdir(exist_ok=False)
    report = {"complete": False, "model_constructed": False, "sources": [], "models": {}}
    write_json(evidence / "preparation.json", report)
    try:
        from importlib.metadata import version
        report["runtime_packages"] = {name: version(name) for name in plan["runtime_packages"]}
        require(report["runtime_packages"] == plan["runtime_packages"], "Installed native runtime differs from plan")
        metadata = {}
        for source in plan["fixture"]["sources"]:
            url = source["rows_api_url"]
            require(urllib.parse.urlsplit(url).hostname == "datasets-server.huggingface.co", "Unexpected dataset metadata host")
            if url not in metadata:
                with urllib.request.urlopen(url, timeout=30) as response:
                    raw = response.read(2 * 1024 * 1024 + 1)
                require(len(raw) <= 2 * 1024 * 1024, "Oversized dataset metadata")
                metadata[url] = {row["row_idx"]: row["row"] for row in json.loads(raw)["rows"]}
            row = metadata[url][source["row_index"]]
            require(row["id"] == source["id"] and str(row["speaker_id"]) == source["speaker_id"], "Dataset source identity changed")
            media_url = row["audio"][0]["src"]
            require(common.public_url_without_query(media_url) == source["asset_url_without_query"], "Dataset asset revision changed")
            target = inputs / common.safe_filename(source["id"] + ".flac")
            item = download_checked(media_url, target, source["sha256"], 20 * 1024 ** 2)
            report["sources"].append({"id": source["id"], **item})
            write_json(evidence / "preparation.json", report)
        # Recreate the already exposed historical fixture, not a new ASR crop.
        # The complete constructed WAV goes into the ordinary application.
        sys.path.insert(0, str(ROOT))
        from diarization import decode_mono
        target = inputs / plan["fixture"]["filename"]
        clips = [decode_mono(inputs / (source["id"] + ".flac"), 30) for source in plan["fixture"]["sources"]]
        constructed = construct_fixture(plan["fixture"]["sources"], clips, target)
        del clips
        require(all(constructed[key] == plan["fixture"][key] for key in ("sha256", "sample_count", "reference_intervals")),
                "Recovered original fixture differs")
        report["fixture"] = {"path": str(target), **constructed, "references_for_evaluation_only": True}
        for family, model in plan["models"].items():
            folder = model_path(plan, work, family)
            folder.mkdir(parents=True, exist_ok=False)
            files = {}
            report["models"][family] = files
            for name, identity in model["files"].items():
                name = common.safe_filename(name)
                url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{name}"
                files[name] = download_checked(url, folder / name, identity["sha256"],
                                               identity["maximum_bytes"], identity.get("bytes"))
                write_json(evidence / "preparation.json", report)
            if family == "speaker":
                # SpeechBrain can resolve either its existing local savedir or
                # its declared HF cache. Both contain the same pinned bytes.
                snapshot = folder / "hub/models--speechbrain--spkrec-ecapa-voxceleb/snapshots" / model["revision"]
                snapshot.mkdir(parents=True)
                for name in model["files"]:
                    (snapshot / name).hardlink_to(folder / name)
        refs = work / "hf/hub/models--Systran--faster-whisper-small/refs"
        refs.mkdir()
        (refs / "main").write_text(plan["models"]["recognizer"]["revision"], encoding="utf-8")
        report["complete"] = True
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        write_json(evidence / "preparation.json", report)


def completed_contract(plan, report):
    """Check final recorded limits as well as the controller's sampled limits."""
    require(report.get("complete") is True, "Actual app pipeline did not complete")
    require(report["audio"]["sha256"] == plan["fixture"]["sha256"], "Actual upload differs from original fixture")
    for field, limit in (("elapsed_seconds", plan["total_worker_seconds"]), ("peak_process_rss_bytes", plan["rss_limit_bytes"])):
        value = report.get(field)
        require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= limit,
                "Recorded worker resource limit: " + field)
    for phase in report["phases"]:
        limit = plan["phase_seconds"].get(phase["name"], plan["total_worker_seconds"])
        elapsed = phase.get("elapsed_seconds")
        require(isinstance(elapsed, (int, float)) and math.isfinite(elapsed) and 0 <= elapsed <= limit, "Recorded phase deadline")
    expected = {"language": None, "beam_size": 5, "vad_filter": False, "no_speech_threshold": 0.6,
                "condition_on_previous_text": False, "word_timestamps": False}
    require(len(report["actual_transcribe_calls"]) == 1 and report["actual_transcribe_calls"][0]["options"] == expected,
            "Recognition policy or attempt count changed")
    require(report["upload_form"] == {"consent": "true", "speakers": "true", "target_language": "none", "summary": "false"},
            "Unexpected enhancement or source-guidance request")
    require(len(report["model_initializations"]) == 1 and report["model_initializations"][0]["cpu_threads"] == 4 and
            report["model_initializations"][0]["num_workers"] == 1 and
            report["model_initializations"][0]["actual_device"] == "cpu" and
            report["model_initializations"][0]["actual_compute_type"] in {"int8", "int8_float32"}, "Unexpected native model runtime")
    model = plan["models"]["recognizer"]
    resolutions = report["model_resolutions"]
    require(len(resolutions) == 1 and resolutions[0]["revision_directory"] == model["revision"], "Unpinned recognizer resolution")
    require(resolutions[0]["files"] == {name: {"bytes": row["bytes"], "sha256": row["sha256"]}
                                      for name, row in model["files"].items()}, "Actual recognizer files differ")
    acoustic = report["acoustic_analysis_calls"]
    require(len(acoustic) == 1 and acoustic[0]["completed"], "Missing actual acoustic turns")
    speaker = acoustic[0]["result"]["model"]
    require(speaker["revision"] == plan["models"]["speaker"]["revision"] and
            speaker["sha256"] == {name: item["sha256"] for name, item in plan["models"]["speaker"]["files"].items()},
            "Unpinned speaker model")


def execute(plan, plan_path, work, evidence, *, test_command=None):
    common.require_hosted()
    preparation = json.loads((evidence / "preparation.json").read_text(encoding="utf-8"))
    require(preparation["complete"], "Preparation incomplete")
    for family, model in plan["models"].items():
        for name, item in model["files"].items():
            require(sha(model_path(plan, work, family) / name) == item["sha256"], "Prepared model changed")
    audio = evidence / "inputs" / plan["fixture"]["filename"]
    require(sha(audio) == plan["fixture"]["sha256"], "Prepared fixture changed")
    with (evidence / "execution-requested.json").open("x", encoding="utf-8") as marker:
        json.dump({"plan_sha256": sha(plan_path), "attempt": 1, "started_at": common.now()}, marker)
    cpus = common.cpu_selection(os.sched_getaffinity(0))
    env = {key: value for key, value in os.environ.items() if key in {
        "PATH", "LANG", "LC_ALL", "TZ", "TMPDIR", "TEMP", "TMP", "VIRTUAL_ENV", "HOME", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_ACTIONS"}}
    env.update(plan["worker_environment"])
    env.update(HF_HOME=str(work / "hf"), LINKSCRIBE_SPEAKER_CACHE=str(work / "speaker-cache"),
               OMP_NUM_THREADS=str(len(cpus)), MKL_NUM_THREADS=str(len(cpus)))
    output = evidence / "speaker-app-report.json"
    command = test_command or [sys.executable, str(ROOT / "tests/smoke_real_speaker_app.py"), "--audio", str(audio),
                               "--output", str(output), "--timeout", "600"]
    started = time.monotonic()
    result = {"plan_sha256": sha(plan_path), "github_sha": os.getenv("GITHUB_SHA"), "command": command,
              "cpu_affinity": cpus, "sampled_group_peak_rss_bytes": 0, "sample_count": 0, "stop_reason": None}
    with (evidence / "worker.log").open("w", encoding="utf-8") as log, (evidence / "resource-samples.jsonl").open("w", encoding="utf-8") as samples:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True,
                                   preexec_fn=lambda: os.sched_setaffinity(0, cpus))
        result["owned_process_group_id"] = process.pid
        try:
            while True:
                elapsed, rss = time.monotonic() - started, common.group_rss(process.pid)
                samples.write(json.dumps({"elapsed_seconds": elapsed, "rss_bytes": rss}) + "\n")
                samples.flush()
                result["sample_count"] += 1
                result["sampled_group_peak_rss_bytes"] = max(rss, result["sampled_group_peak_rss_bytes"])
                if process.poll() is not None:
                    break
                reason = None
                if rss > plan["rss_limit_bytes"]: reason = "owned_group_rss_limit"
                if elapsed > plan["total_worker_seconds"]: reason = "worker_total_time_limit"
                if output.exists():
                    phase = json.loads(output.read_text(encoding="utf-8"))["phase"]
                    if time.monotonic() - phase["started_monotonic"] > plan["phase_seconds"].get(phase["name"], 600):
                        reason = "phase_deadline:" + phase["name"]
                elif elapsed > plan["phase_seconds"]["initialization"]:
                    reason = "worker_startup_deadline"
                if reason:
                    result["stop_reason"] = reason
                    break
                time.sleep(0.1)
        except Exception as exc:
            result["stop_reason"] = "controller_error"
            result["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            result["cleanup"] = common.terminate_owned(process)
    result.update(returncode=process.poll(), elapsed_seconds=time.monotonic() - started,
                  resource_samples_sha256=sha(evidence / "resource-samples.jsonl"))
    try:
        require(result["stop_reason"] is None and result["returncode"] == 0, "Worker stopped or failed")
        require(result["elapsed_seconds"] <= plan["total_worker_seconds"] and
                result["sampled_group_peak_rss_bytes"] <= plan["rss_limit_bytes"], "Recorded controller limit")
        require(result["cleanup"]["leader_exited"] and not result["cleanup"]["live_group_members_after_cleanup"], "Owned process remains")
        report = json.loads(output.read_text(encoding="utf-8"))
        completed_contract(plan, report)
        require(report["actual_transcribe_calls"][0]["waveform"]["sample_count"] == plan["fixture"]["sample_count"] and
                report["actual_transcribe_calls"][0]["waveform"]["sha256"] == preparation["fixture"]["decoded_pcm_sha256"],
                "Actual full PCM differs from independently decoded prepared WAV")
        require(sha(plan_path) == result["plan_sha256"], "Plan changed during execution")
        for item in plan["source_files"]:
            require(sha(common.repo_file(item["path"])) == item["sha256"], "Source changed during execution")
        # Original controlled-voice annotations are evaluated only after the
        # owned model process has exited. This is not natural-meeting accuracy.
        from smoke_real_speakers import score
        case = {"id": "two_speakers_returning", "kind": "clean", "expected_speakers": 2,
                "reference_intervals": plan["fixture"]["reference_intervals"]}
        result["controlled_fixture_acoustic_assessment"] = score(case, report["acoustic_analysis_calls"][0]["result"])
        result["pipeline_contract_pass"] = True
        result["controlled_fixture_acoustic_pass"] = result["controlled_fixture_acoustic_assessment"]["status"] == "passed"
        result["broader_speaker_or_word_timing_accuracy_approved"] = False
        require(result["controlled_fixture_acoustic_pass"], "Original controlled acoustic criterion failed")
        result["passed"] = True
    except Exception as exc:
        result["passed"] = False
        result["final_failure"] = {"type": type(exc).__name__, "message": str(exc)}
    write_json(evidence / "execution.json", result)
    return 0 if result["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("validate", "prepare", "execute"), default="validate")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    try:
        plan = validate(args.plan)
        if args.action == "validate":
            write_json(args.evidence / "preflight.json", {"plan_sha256": sha(args.plan), "valid": True,
                "model_constructed": False, "inference_performed": False, "github_sha": os.getenv("GITHUB_SHA")})
            return 0
        require(args.work is not None, "Separate work directory required")
        args.work.mkdir(parents=True, exist_ok=True)
        require(not args.work.resolve().is_relative_to(args.evidence.resolve()), "Model files must stay outside uploaded evidence")
        if args.action == "prepare":
            prepare(plan, args.work, args.evidence)
            return 0
        return execute(plan, args.plan, args.work, args.evidence)
    except Exception as exc:
        write_json(args.evidence / (args.action + "-failure.json"), {"action": args.action,
            "type": type(exc).__name__, "message": str(exc), "model_execution_not_claimed": True})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
