#!/usr/bin/env python3
"""Actual ASR + speakers + selected local translation + summary resource gate.

Start Ollama separately in the same process namespace and pass its daemon PID.
This script downloads no models and starts no service. It observes real calls,
retains outputs for review, and measures concurrent process-tree memory samples.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit

os.environ["ORT_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import smoke_real_speaker_app as app_smoke


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def installed_model(tags, model):
    canonical = model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"
    selected = next((item for item in tags["models"] if item.get("name") in {model, canonical}), None)
    if selected is None or not selected.get("digest"):
        raise ValueError(f"The configured model {model!r} is not installed with a digest in the local Ollama runtime.")
    return deepcopy(selected)


def memory_budget(value):
    number = float(value)
    if not math.isfinite(number) or not 1 <= number <= 1048576:
        raise argparse.ArgumentTypeError("Memory budget must be finite and between 1 and 1048576 MiB.")
    return number


def listening_endpoint(connections, url):
    endpoint = urlsplit(url)
    addresses = {"127.0.0.1", "0.0.0.0", "::"}
    if endpoint.hostname == "localhost":
        addresses.add("::1")
    if endpoint.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("The resource gate supports only the application's local Ollama endpoint.")
    matches = [{"address": item.laddr.ip, "port": item.laddr.port} for item in connections
               if item.status == "LISTEN" and item.laddr.port == (endpoint.port or 80)
               and item.laddr.ip in addresses]
    if not matches:
        raise ValueError("The supplied Ollama daemon is not listening on the configured local API endpoint.")
    return matches


def update_peaks(state, entries, elapsed):
    """Each peak is a sum at one instant; never add separate per-process peaks."""
    unique = {entry["pid"]: entry for entry in entries}
    sample = {"at_seconds": round(elapsed, 3), "processes": list(unique.values()),
              "rss_bytes": sum(entry["rss_bytes"] for entry in unique.values())}
    sample["pss_bytes"] = (sum(entry["pss_bytes"] for entry in unique.values())
                           if all(entry["pss_bytes"] is not None for entry in unique.values()) else None)
    state["sample_count"] += 1
    if state.get("peak_rss_sample") is None or sample["rss_bytes"] > state["peak_rss_sample"]["rss_bytes"]:
        state["peak_rss_sample"] = sample
    if sample["pss_bytes"] is None:
        state["pss_available_for_every_sample"] = False
    elif state.get("peak_pss_sample") is None or sample["pss_bytes"] > state["peak_pss_sample"]["pss_bytes"]:
        state["peak_pss_sample"] = sample


class ProcessMemory:
    def __init__(self, daemon_pid, interval=0.2):
        import psutil
        self.psutil = psutil
        self.self_process = psutil.Process(os.getpid())
        self.daemon = psutil.Process(daemon_pid)
        if daemon_pid <= 1 or daemon_pid == os.getpid() or "ollama" not in self.daemon.name().lower():
            raise ValueError("Provide the actual Ollama daemon PID in this process namespace.")
        command = self.daemon.cmdline()
        if len(command) < 2 or command[1] != "serve":
            raise ValueError("The supplied PID must be the 'ollama serve' daemon, not an inference runner.")
        self.daemon_created = self.daemon.create_time()
        self.started = time.monotonic()
        self.interval = interval
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.accept_samples = True
        self.state = {"sample_count": 0, "sample_interval_seconds": interval,
                      "pss_available_for_every_sample": True, "errors": [],
                      "endpoint_verified": False, "sampler_stopped": False,
                      "daemon_executable": command[0], "daemon_subcommand": command[1],
                      "scope": "This app process and descendants plus the supplied Ollama daemon and descendants, deduplicated by PID.",
                      "excluded": "OS, browser, unrelated processes, and filesystem cache outside the measured process residency; this is not whole-VM memory.",
                      "rss_interpretation": "Concurrent summed RSS is an upper bound that can double-count shared pages.",
                      "pss_interpretation": "Linux PSS apportions shared pages; it is reported only for complete samples.",
                      "sampling_limit": "Samples scan processes sequentially and may miss transient peaks between scans.",
                      "ollama_daemon_pid": daemon_pid, "app_pid": os.getpid()}
        self.sample()
        self.thread = threading.Thread(target=self._run, name="workflow-memory-sampler", daemon=True)

    def verify_endpoint(self, url):
        try:
            matches = listening_endpoint(self.daemon.net_connections(kind="tcp"), url)
            with self.lock:
                self.state.update({"endpoint_verified": True, "api_endpoint": url, "matching_listeners": matches})
        except Exception as exc:
            with self.lock:
                self.state["errors"].append(f"Could not establish API daemon identity: {type(exc).__name__}: {exc}")
            raise

    def sample(self):
        try:
            if not self.daemon.is_running() or self.daemon.create_time() != self.daemon_created:
                raise RuntimeError("The supplied Ollama daemon stopped or its PID was reused.")
            processes = {item.pid: item for root in (self.self_process, self.daemon)
                         for item in [root, *root.children(recursive=True)]}
            if len(processes) > 128:
                raise RuntimeError("Unexpectedly large process tree; memory accounting aborted.")
            entries = []
            for process in processes.values():
                try:
                    rss = process.memory_info().rss
                    try:
                        pss = getattr(process.memory_full_info(), "pss", None)
                    except self.psutil.AccessDenied:
                        pss = None
                    entries.append({"pid": process.pid, "name": process.name(),
                                    "rss_bytes": rss, "pss_bytes": pss})
                except self.psutil.NoSuchProcess:
                    continue  # An exited child no longer occupies resident memory.
            if self.self_process.pid not in {entry["pid"] for entry in entries} or self.daemon.pid not in {entry["pid"] for entry in entries}:
                raise RuntimeError("A required process was missing from the memory sample.")
            with self.lock:
                if self.accept_samples:
                    update_peaks(self.state, entries, time.monotonic() - self.started)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            with self.lock:
                if self.accept_samples and message not in self.state["errors"] and len(self.state["errors"]) < 20:
                    self.state["errors"].append(message)

    def _run(self):
        while not self.stopped.wait(self.interval):
            self.sample()

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopped.set()
        self.thread.join(timeout=2)
        if not self.thread.is_alive():
            self.sample()
        with self.lock:
            self.accept_samples = False
            self.state["sampler_stopped"] = not self.thread.is_alive()
            if not self.state["sampler_stopped"]:
                self.state["errors"].append("Memory sampler did not stop within two seconds; the final measurement is incomplete.")

    def snapshot(self):
        with self.lock:
            result = deepcopy(self.state)
        result["measurement_complete"] = (bool(result["sample_count"]) and not result["errors"]
                                          and result["endpoint_verified"] and result["sampler_stopped"])
        peak = result.get("peak_rss_sample")
        result["peak_combined_rss_mib"] = round(peak["rss_bytes"] / 1024 ** 2, 1) if peak else None
        peak = result.get("peak_pss_sample")
        result["peak_combined_pss_mib"] = (round(peak["pss_bytes"] / 1024 ** 2, 1)
                                            if peak and result["pss_available_for_every_sample"] else None)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--translation", choices=("el", "en"), default="el")
    parser.add_argument("--ollama-pid", type=int, default=os.getenv("LINKSCRIBE_QA_OLLAMA_PID"))
    parser.add_argument("--asr-provenance", type=Path, help="Existing verified Small-model manifest from ASR QA.")
    parser.add_argument("--memory-budget-mib", type=memory_budget, help="Optional concurrent RSS upper-bound budget.")
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "complete": False, "semantic_quality": "unreviewed",
              "created_utc": datetime.now(timezone.utc).isoformat(), "summary_required": True,
              "translation_target": args.translation, "actual_translation_calls": [],
              "actual_summary_calls": [], "ollama_requests": [], "memory_budget_mib": args.memory_budget_mib}
    names = ("ORT_DISABLE_TELEMETRY", "HF_HUB_DISABLE_TELEMETRY", "HF_HUB_OFFLINE", "LINKSCRIBE_DEVICE",
             "LINKSCRIBE_OLLAMA_THREADS", "LINKSCRIBE_TRANSLATION_THREADS", "OLLAMA_NUM_PARALLEL",
             "OLLAMA_MAX_LOADED_MODELS", "OLLAMA_CONTEXT_LENGTH", "OLLAMA_KEEP_ALIVE", "OLLAMA_NO_CLOUD")
    report["child_runtime_environment"] = {name: os.environ[name] for name in names if name in os.environ}
    started = time.monotonic()
    sampler = None
    originals = {}
    application = enhancements = None

    def checkpoint():
        if sampler is not None:
            report["memory"] = sampler.snapshot()
        app_smoke.save(args.output, report)

    checkpoint()
    try:
        if args.ollama_pid is None:
            raise ValueError("Supply --ollama-pid or LINKSCRIBE_QA_OLLAMA_PID from the local server wrapper.")
        if os.getenv("HF_HUB_OFFLINE") != "1":
            raise ValueError("Set HF_HUB_OFFLINE=1 after caching the ASR and speaker models; this gate must not download weights.")
        sampler = ProcessMemory(int(args.ollama_pid))
        sampler.start()
        import app as application
        import enhancements
        import marian_translation
        translation_backend = enhancements.translation_backend()
        if enhancements.speaker_backend() != "speechbrain":
            raise ValueError("This combined gate requires the speechbrain speaker backend.")
        report["translation_backend"] = translation_backend
        if translation_backend == "marian":
            pair = "en-el" if args.translation == "el" else "el-en"
            if not marian_translation.cache_status()["pairs_cached"].get(pair):
                raise ValueError(f"Prepare the {pair} Marian cache before this gate; no download was started.")
        names = ("app.py", "enhancements.py", "diarization.py", "marian_translation.py", "library.py",
                 "library_backup.py", "batch_store.py", "tests/smoke_full_local_workflow.py", "tests/smoke_real_speaker_app.py")
        report["source_sha256"] = {name: file_sha(ROOT / name) for name in names}
        if args.asr_provenance:
            if args.asr_provenance.stat().st_size > 65536:
                raise ValueError("ASR provenance manifest exceeds 64 KiB.")
            asr = json.loads(args.asr_provenance.read_text())
            for name, info in asr["files"].items():
                if Path(name).name != name:
                    raise ValueError("ASR provenance contains an invalid filename.")
                if file_sha(Path(asr["snapshot_directory"]) / name) != info["sha256"]:
                    raise ValueError("Cached ASR file does not match its supplied provenance.")
            report["asr_cache_provenance_supplied_and_files_verified"] = asr
        url, summary_model = enhancements.ollama_settings()
        sampler.verify_endpoint(url)
        tags = enhancements.local_ollama_json("/api/tags")
        version = enhancements.local_ollama_json("/api/version")
        report["ollama"] = {"url": url, "version": version,
                            "summary_model": installed_model(tags, summary_model)}
        expected_models = {"summary": summary_model}
        if translation_backend == "ollama":
            _, translation_model = enhancements.ollama_settings("translation")
            report["ollama"]["translation_model"] = installed_model(tags, translation_model)
            report["ollama"]["translation_profile"] = enhancements.translation_profile()
            expected_models["translation"] = translation_model
        originals = {"transport": enhancements.local_ollama_json,
                     "translate": application.translate_segments, "summarize": application.summarize_segments}
        active = threading.local()

        def transport(path, payload=None, **kwargs):
            if path != "/api/chat":
                return originals["transport"](path, payload, **kwargs)
            event = {"task": getattr(active, "task", None), "request": deepcopy(payload), "response_json": None}
            report["ollama_requests"].append(event)
            checkpoint()
            call_started = time.monotonic()
            try:
                response = originals["transport"](path, payload, **kwargs)
                event["response_json"] = deepcopy(response)
                return response
            except Exception as exc:
                event["error"] = {"type": type(exc).__name__, "message": str(exc)}
                if isinstance(exc, json.JSONDecodeError):
                    event["undecodable_response_text"] = exc.doc
                raise
            finally:
                event["elapsed_seconds"] = round(time.monotonic() - call_started, 3)
                checkpoint()

        def translate(segments, target, source_language=None):
            event = {"source_language": source_language, "target": target, "source_segments": deepcopy(segments)}
            report["actual_translation_calls"].append(event)
            active.task = "translation"
            checkpoint()
            try:
                result = originals["translate"](segments, target, source_language=source_language)
                event["output_segments"] = deepcopy(result)
                event["runtime"] = (marian_translation.model_details(source_language.split("-", 1)[0], target)
                                     if translation_backend == "marian" else
                                     {"backend": "ollama", "profile": report["ollama"]["translation_profile"],
                                      "model": deepcopy(report["ollama"]["translation_model"])})
                assert segments == event["source_segments"], "Translation mutated the recognized source."
                return result
            except Exception as exc:
                event["error"] = {"type": type(exc).__name__, "message": str(exc)}
                raise
            finally:
                active.task = None
                checkpoint()

        def summarize(segments):
            event = {"source_segments": deepcopy(segments)}
            report["actual_summary_calls"].append(event)
            active.task = "summary"
            checkpoint()
            try:
                result = originals["summarize"](segments)
                event["output"] = deepcopy(result)
                assert segments == event["source_segments"], "Summary mutated the recognized source."
                return result
            except Exception as exc:
                event["error"] = {"type": type(exc).__name__, "message": str(exc)}
                raise
            finally:
                active.task = None
                checkpoint()

        enhancements.local_ollama_json = transport
        application.translate_segments = translate
        application.summarize_segments = summarize
        checkpoint()
        workflow_path = args.output.with_name(args.output.stem + "-app.json")
        report["workflow_report_path"] = str(workflow_path.resolve())
        checkpoint()
        exit_code = app_smoke.main(["--audio", str(args.audio), "--output", str(workflow_path),
                                   "--target", args.translation, "--summary", "--timeout", "900"])
        report["workflow"] = json.loads(workflow_path.read_text())
        assert exit_code == 0 and report["workflow"]["complete"], report["workflow"].get("error")
        assert report["actual_translation_calls"] and report["actual_summary_calls"] and report["ollama_requests"]
        assert all(item["request"]["model"] == expected_models.get(item["task"]) for item in report["ollama_requests"])
        assert {item["task"] for item in report["ollama_requests"]} == set(expected_models)
        assert {name: file_sha(ROOT / name) for name in names} == report["source_sha256"], "Source changed during combined inference."
        report["complete"] = True
    except KeyboardInterrupt:
        report["error"] = {"type": "KeyboardInterrupt", "message": "Interrupted; partial evidence retained."}
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc),
                           "cause": repr(exc.__cause__) if exc.__cause__ else None}
    finally:
        if originals:
            enhancements.local_ollama_json = originals["transport"]
            application.translate_segments = originals["translate"]
            application.summarize_segments = originals["summarize"]
        if sampler is not None:
            sampler.stop()
            report["memory"] = sampler.snapshot()
            if not report["memory"]["measurement_complete"]:
                report["complete"] = False
            peak = report["memory"]["peak_combined_rss_mib"]
            report["memory_budget_passed"] = (peak <= args.memory_budget_mib
                                               if peak is not None and args.memory_budget_mib is not None else None)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        checkpoint()
    print(json.dumps({"complete": report["complete"], "elapsed_seconds": report["elapsed_seconds"],
                      "memory": report.get("memory", {}), "error": report.get("error")}), flush=True)
    return 0 if report["complete"] and report.get("memory_budget_passed") is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
