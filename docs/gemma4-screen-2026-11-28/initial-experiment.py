#!/usr/bin/env python3
"""One pinned text-only Gemma 4 preparation and development screen.

The phase supervisor measures import, model loading and generation. No heldout
files are read, no production file is edited, and old outputs are never replaced.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def event(name, **fields):
    print("GEMMA_EVENT " + json.dumps({"event": name, **fields}), flush=True)


def api(path, body=None, timeout=10, port=11434):
    request = urllib.request.Request("http://127.0.0.1:" + str(port) + path,
                                    data=None if body is None else json.dumps(body).encode(),
                                    headers={"Content-Type": "application/json"})
    with LOCAL.open(request, timeout=timeout) as response:
        return json.load(response)


def read_plan():
    if sha(HERE / "plan.json") != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("The frozen pre-output plan changed.")
    plan = json.loads((HERE / "plan.json").read_text())
    for name, expected in plan["source_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("A frozen source or development input changed: " + name)
    for name, expected in plan["runtime"]["files_sha256"].items():
        if sha(Path(plan["runtime"]["directory"]) / name) != expected:
            raise ValueError("The verified native runtime changed: " + name)
    return plan


def model_blob(runtime, plan):
    return runtime / "models/blobs" / ("sha256-" + plan["model"]["sha256"])


def verify_blob(runtime, plan):
    path = model_blob(runtime, plan)
    if path.is_symlink() or path.stat().st_size != plan["model"]["bytes"] or sha(path) != plan["model"]["sha256"]:
        raise ValueError("The complete official GGUF identity does not match the plan.")


def download(runtime, plan):
    output = HERE / "download.json"
    if output.exists():
        raise ValueError("Refusing to overwrite a previous download attempt.")
    dest = model_blob(runtime, plan)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    if dest.exists() or partial.exists():
        raise ValueError("The new candidate path already exists.")
    free = shutil.disk_usage(runtime).free
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "plan_sha256": sha(HERE / "plan.json"), "generation_calls": 0,
              "free_disk_before_bytes": free, "model": plan["model"]}
    save(output, report)
    if free < plan["model"]["bytes"] + 1024**3:
        raise ValueError("Insufficient space for the single payload plus 1 GiB working reserve.")
    began = time.monotonic()
    written = 0
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(plan["model"]["url"], timeout=60) as response, partial.open("xb") as stream:
            while block := response.read(4 * 1024 * 1024):
                written += len(block)
                if written > plan["model"]["bytes"]:
                    raise ValueError("Download exceeds the declared payload size.")
                digest.update(block)
                stream.write(block)
        if written != plan["model"]["bytes"] or digest.hexdigest() != plan["model"]["sha256"]:
            raise ValueError("The downloaded payload failed full size/SHA256 verification.")
        partial.replace(dest)
        report["complete"] = True
        report["verified_sha256"] = digest.hexdigest()
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report.update({"bytes_received": written, "elapsed_seconds": round(time.monotonic() - began, 3),
                       "free_disk_after_bytes": shutil.disk_usage(runtime).free,
                       "finished_at": datetime.now(timezone.utc).isoformat()})
        save(output, report)


def daemon_environment(runtime):
    keys = ("PATH", "HOME", "LANG", "LC_ALL", "LD_LIBRARY_PATH", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR")
    environment = {key: os.environ[key] for key in keys if key in os.environ}
    environment.update({"OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(runtime / "models"),
                        "OLLAMA_NO_CLOUD": "1", "OLLAMA_NUM_PARALLEL": "1",
                        "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_CONTEXT_LENGTH": "4096",
                        "OLLAMA_KEEP_ALIVE": "1m", "OLLAMA_LOAD_TIMEOUT": "180s"})
    return environment


def ready(process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("Owned daemon exited before readiness.")
        try:
            return api("/api/version")
        except OSError:
            time.sleep(0.25)
    raise TimeoutError("Owned daemon did not become ready.")


def stop_owned(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    except ProcessLookupError:
        pass


def cached_identity(runtime, plan):
    manifest = runtime / "models/manifests/registry.ollama.ai/library" / plan["model"]["local_name"].split(":")[0] / plan["model"]["local_name"].split(":")[1]
    content = json.loads(manifest.read_text())
    layers = content["layers"]
    models = [x for x in layers if x["mediaType"] == "application/vnd.ollama.image.model"]
    if len(models) != 1 or models[0]["digest"] != "sha256:" + plan["model"]["sha256"]:
        raise ValueError("Import changed or replaced the declared standalone text model.")
    if any(x["mediaType"] in {"application/vnd.ollama.image.projector", "application/vnd.ollama.image.draft"} for x in layers):
        raise ValueError("Unexpected projector or draft in this text-only import.")
    descriptors = [content["config"], *layers]
    for entry in descriptors:
        path = runtime / "models/blobs" / entry["digest"].replace(":", "-")
        if path.stat().st_size != entry["size"] or sha(path) != entry["digest"].split(":", 1)[1]:
            raise ValueError("Imported cache descriptor fails full verification.")
    config = json.loads((runtime / "models/blobs" / content["config"]["digest"].replace(":", "-")).read_text())
    return {"manifest_sha256": sha(manifest), "manifest": content, "config": config,
            "all_descriptor_bytes_verified": True, "projector_or_draft_present": False}


def expected_request(case_id, plan):
    baseline = json.loads((ROOT / plan["evaluation"]["retained_baseline"]).read_text())
    case = next(c for c in baseline["cases"] if c["id"] == case_id)
    requests = [r["request"] for r in case["requests"] if r["kind"] == "inference"]
    if len(requests) != 1:
        raise ValueError("The exposed short case no longer uses one complete production request.")
    body = copy.deepcopy(requests[0])
    body["model"] = plan["model"]["local_name"]
    body["options"]["num_ctx"] = 4096
    return body


def native_prompt(body):
    messages = body["messages"]
    if len(messages) != 2 or [m["role"] for m in messages] != ["system", "user"]:
        raise ValueError("Unexpected message structure for the frozen short screen.")
    return ("<bos><|turn>system\n" + messages[0]["content"].strip() + "<turn|>\n"
            + "<|turn>user\n" + messages[1]["content"].strip() + "<turn|>\n<|turn>model\n")


def runner_identity(process):
    import psutil
    matches = [p for p in psutil.Process(process.pid).children(recursive=True) if p.name() == "llama-server"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one owned native text runner.")
    runner = matches[0]
    command = runner.cmdline()
    if any(x in command for x in ["--mmproj", "--spec-draft-model", "--spec-type"]):
        raise ValueError("The actual text runner loaded an optional projector/draft.")
    port = int(command[command.index("--port") + 1])
    if command[command.index("-c") + 1] != "4096":
        raise ValueError("The native context allocation differs from the fixed screen.")
    return {"pid": runner.pid, "executable": command[0], "executable_sha256": sha(command[0]),
            "command": command, "port": port, "optional_projector_and_draft_arguments_absent": True}


def prepare(runtime, plan, process, report):
    event("import_start")
    blob = model_blob(runtime, plan)
    report["storage_before_import"] = {"free_bytes": shutil.disk_usage(runtime).free,
                                        "payload_allocated_bytes": blob.stat().st_blocks * 512,
                                        "payload_inode": blob.stat().st_ino}
    body = {"model": plan["model"]["local_name"], "stream": False,
            "files": {plan["model"]["filename"]: "sha256:" + plan["model"]["sha256"]},
            "parameters": {"temperature": 1.0, "top_p": 0.95, "top_k": 64}}
    report["create_request"] = body
    report["create_response"] = api("/api/create", body, timeout=180)
    report["cache"] = cached_identity(runtime, plan)
    report["storage_after_import"] = {"free_bytes": shutil.disk_usage(runtime).free,
                                       "payload_allocated_bytes": blob.stat().st_blocks * 512,
                                       "payload_inode": blob.stat().st_ino,
                                       "all_blob_allocated_bytes": sum(p.stat().st_blocks * 512 for p in (runtime / "models/blobs").iterdir() if p.is_file())}
    report["show"] = api("/api/show", {"model": plan["model"]["local_name"]})
    report["tags"] = api("/api/tags")
    event("import_complete", manifest_sha256=report["cache"]["manifest_sha256"])
    corpus = json.loads((HERE / "development-cases.json").read_text())
    report["prompts"] = []
    for case in corpus["cases"]:
        body = expected_request(case["id"], plan)
        rendered = native_prompt(body)
        if any(s["text"] not in rendered for s in case["segments"]):
            raise ValueError("A complete source segment is absent from the native prompt.")
        debug_body = {**body, "_debug_render_only": True}
        response = api("/api/chat", debug_body, timeout=180)
        if response.get("_debug_info", {}).get("rendered_template") != rendered:
            raise ValueError("Actual native rendering differs from the frozen official system/user format.")
        if response.get("eval_count", 0) or response.get("message", {}).get("content"):
            raise ValueError("Render-only preparation unexpectedly generated an answer.")
        runner = runner_identity(process)
        token_response = api("/tokenize", {"content": rendered, "add_special": False, "parse_special": True},
                             port=runner["port"])
        tokens = token_response.get("tokens")
        if (not isinstance(tokens, list) or not tokens or any(type(x) is not int for x in tokens)
                or tokens[0] != 2 or tokens.count(2) != 1 or len(tokens) + 2048 + 1 > 4096):
            raise ValueError("Native tokens fail full prompt + maximum output + end-token accounting.")
        report["prompts"].append({"id": case["id"], "request": body, "rendered_prompt": rendered,
                                  "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                                  "debug_response": response, "tokens": tokens,
                                  "prompt_tokens": len(tokens), "maximum_output_tokens": 2048,
                                  "context_tokens": 4096, "unused_capacity_after_maximum_output": 4096 - len(tokens) - 2048,
                                  "complete_source_segments": len(case["segments"]), "runner": runner})
        save(HERE / "prepare.json", report)
    report["unload_response"] = api("/api/chat", {"model": plan["model"]["local_name"], "messages": [], "keep_alive": 0, "stream": False})
    if report["unload_response"].get("done_reason") != "unload" or api("/api/ps").get("models"):
        raise ValueError("Preparation cleanup did not unload the native model.")
    report["generation_calls"] = 0
    report["complete"] = True
    event("prepare_complete", prompt_token_counts=[x["prompt_tokens"] for x in report["prompts"]])


def infer(runtime, plan, process, report):
    freeze_path = HERE / "inference-freeze.json"
    if sha(freeze_path) != (HERE / "inference-freeze.sha256").read_text().strip():
        raise ValueError("Final prepared identity changed.")
    freeze = json.loads(freeze_path.read_text())
    if freeze["plan_sha256"] != sha(HERE / "plan.json"):
        raise ValueError("Final freeze does not bind the declared plan.")
    for name, expected in freeze["prepared_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError("Prepared evidence changed: " + name)
    setup = json.loads((HERE / "prepare.json").read_text())
    if not setup["complete"] or not json.loads((HERE / "prepare-resources.json").read_text())["passed"]:
        raise ValueError("Import/load/tokenization did not pass the bounded preparation.")
    if cached_identity(runtime, plan) != setup["cache"]:
        raise ValueError("Prepared native package changed.")
    os.environ.update({"LINKSCRIBE_TRANSLATION_BACKEND": "ollama", "LINKSCRIBE_TRANSLATION_MODEL": plan["model"]["local_name"],
                       "LINKSCRIBE_OLLAMA_THREADS": "4", "LINKSCRIBE_OLLAMA_URL": "http://127.0.0.1:11434"})
    os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    spec = importlib.util.spec_from_file_location("enhancements", HERE / "enhancements-context4096.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["enhancements"] = module
    spec.loader.exec_module(module)
    import evaluate_translation_quality as qa
    original_identity = qa.source_identity
    def identity(path):
        value = original_identity(path)
        value["executed_enhancements_snapshot"] = {"path": str(HERE / "enhancements-context4096.py"),
                                                  "sha256": sha(HERE / "enhancements-context4096.py"),
                                                  "only_code_change": "num_ctx 8192 -> 4096"}
        return value
    qa.source_identity = identity
    report["cases"] = []
    for case_id in plan["evaluation"]["case_ids"]:
        path = HERE / (case_id + ".json")
        if path.exists():
            raise ValueError("Refusing a repeated development case.")
        event("case_start", id=case_id)
        value, status = qa.evaluate(HERE / "development-cases.json", path, case_ids=[case_id], splits=["development"])
        case = value["cases"][0] if value.get("cases") else {}
        requests = case.get("requests", [])
        calls = [x for x in requests if x["kind"] == "inference"]
        controls = [x for x in requests if x["kind"] == "control"]
        checks = {"one_exact_declared_request": len(calls) == 1 and calls[0]["request"] == expected_request(case_id, plan),
                  "request_timeout_240s": len(calls) == 1 and calls[0]["timeout_seconds"] == 240,
                  "structure_and_execution_complete": status == 0 and value.get("complete") is True,
                  "normal_completion": bool(calls), "empty_reasoning": bool(calls),
                  "nonempty_final_content": bool(calls), "output_below_cap": bool(calls),
                  "unload_acknowledged": bool(controls), "resident_models_empty": api("/api/ps").get("models") == []}
        for call in calls:
            response = json.loads(call.get("response_json", "{}"))
            message = response.get("message", {})
            checks["normal_completion"] &= response.get("done") is True and response.get("done_reason") == "stop"
            checks["empty_reasoning"] &= isinstance(message.get("thinking", ""), str) and not message.get("thinking", "").strip()
            checks["nonempty_final_content"] &= isinstance(message.get("content"), str) and bool(message.get("content", "").strip())
            checks["output_below_cap"] &= type(response.get("eval_count")) is int and 0 < response["eval_count"] < 2048
        for control in controls:
            response = json.loads(control.get("response_json", "{}"))
            checks["unload_acknowledged"] &= response.get("done") is True and response.get("done_reason") == "unload"
        entry = {"id": case_id, "report": path.name, "sha256": sha(path), "checks": checks,
                 "semantic_quality": "unreviewed", "automatic_status": case.get("automatic_status")}
        report["cases"].append(entry)
        report["generation_calls"] = len(report["cases"])
        save(HERE / "infer.json", report)
        event("case_complete" if all(checks.values()) else "case_failed", id=case_id, report=str(path), sha256=sha(path))
        if not all(checks.values()):
            raise ValueError("First execution/protocol/structure failure; the frozen screen stops.")
    report["complete"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("download", "prepare", "infer"), required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    plan = read_plan()
    runtime = args.runtime_dir.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    if args.phase == "download":
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("Download time limit.")))
        signal.alarm(plan["limits"]["download_seconds"])
        try:
            download(runtime, plan)
        finally:
            signal.alarm(0)
        return 0
    output = HERE / (args.phase + ".json")
    if output.exists():
        raise ValueError("Refusing to overwrite a previous phase.")
    verify_blob(runtime, plan)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 11434))
    report = {"phase": args.phase, "started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "plan_sha256": sha(HERE / "plan.json"), "generation_calls": 0,
              "semantic_quality": "unreviewed", "heldouts_opened_or_run": False}
    save(output, report)
    process = None
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Supervisor stopped phase.")))
    try:
        descriptor = os.open(runtime / (args.phase + "-daemon-private.log"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as log:
            process = subprocess.Popen([str(Path(plan["runtime"]["directory"]) / "bin/ollama"), "serve"],
                                       env=daemon_environment(runtime), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            report["runtime"] = ready(process)
            if report["runtime"].get("version") != plan["runtime"]["version"]:
                raise ValueError("Executing runtime version differs from the plan.")
            if args.phase == "prepare":
                prepare(runtime, plan, process, report)
            else:
                infer(runtime, plan, process, report)
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if process is not None:
            stop_owned(process)
            report["owned_daemon_stopped"] = process.poll() is not None
        report["frozen_inputs_unchanged"] = all(sha(ROOT / p) == expected for p, expected in plan["source_sha256"].items())
        report["complete"] = report["complete"] and report["frozen_inputs_unchanged"]
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save(output, report)
    event("phase_complete", phase=args.phase, complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
