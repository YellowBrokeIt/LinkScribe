"""Owned zero-generation native phase, imported only after root authorization."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request

import psutil

from context import (HERE, ROOT, OWNED, PRIOR, GRAMMAR_PREP, read, sha, save, record,
                     event, require_storage, strict_json)
from native_contract import NativeContract

HTTP_LIMIT = 2 * 1024**2


class NativeHTTPError(RuntimeError):
    def __init__(self, status, body, receipt):
        super().__init__("Native HTTP response status " + str(status))
        self.status, self.body, self.receipt = status, body, receipt


def stop_daemon(process):
    try:
        parent = psutil.Process(process.pid)
        owned = [parent, *parent.children(recursive=True)]
    except psutil.NoSuchProcess:
        owned = []
    for child in reversed(owned):
        try: child.terminate()
        except psutil.NoSuchProcess: pass
    _, alive = psutil.wait_procs(owned, timeout=3)
    for child in alive:
        try: child.kill()
        except psutil.NoSuchProcess: pass
    _, alive = psutil.wait_procs(alive, timeout=3)
    process.wait(timeout=3)
    return not [child for child in alive if child.is_running() and child.status() != psutil.STATUS_ZOMBIE]


def parameters(display):
    result = {"stop": []}
    for line in display.splitlines():
        if not line.strip(): continue
        key, encoded = line.split(maxsplit=1)
        if key not in {"num_ctx", "temperature", "top_p", "stop"}:
            raise ValueError("Unexpected native import parameter.")
        value = strict_json(encoded)
        if key == "stop":
            if not isinstance(value, str): raise ValueError("Non-string native stop.")
            result[key].append(value)
        else:
            if key in result or type(value) not in (int, float) or (key == "num_ctx" and type(value) is not int):
                raise ValueError("Duplicate or incorrectly typed native parameter.")
            result[key] = value
    return result


def native_prepare(report, output, plan):
    # Import the already-reviewed native helpers only inside the authorized
    # native phase. Do not call their historical read_plan or generation paths.
    base = ROOT / "docs/krikri-screen-2026-11-28"
    sys.path.insert(0, str(base))
    import staging
    import native_verify
    common = staging.common
    profile = copy.deepcopy(read(PRIOR / "plan.json"))
    if profile["model"] != plan["model"]:
        raise ValueError("The complete verified native model identity differs from the predecessor.")
    profile["runtime"] = plan["runtime"]
    runtime = Path(profile["storage"]["owned_runtime_directory"])
    requests = read(GRAMMAR_PREP / "expected-requests.json")
    queries = read(GRAMMAR_PREP / "proposed-native-grammar-queries.json")["queries"]
    cases = read(PRIOR / "protected-source-cases.json")["cases"]
    if not len(cases) == len(requests) == 6:
        raise ValueError("Complete six-case native preparation inventory changed.")
    contract = NativeContract(requests, queries, plan["model"]["local_name"])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    process = None
    original_api = common.api
    bound_runner = None
    report.update({"http_calls": [], "prompts": [], "grammars": [], "generation_calls": 0,
                   "model_create_import_calls": 0, "model_downloads": 0,
                   "grammar_enforcement_not_yet_validated": True})
    daemon_log = OWNED / "logs/native-daemon-private.log"
    response_dir = OWNED / "native-responses"; response_dir.mkdir()
    grammar_dir = OWNED / "grammars"; grammar_dir.mkdir()

    def check_runner(port):
        nonlocal bound_runner
        actual = common.runner_identity(process)
        candidate = psutil.Process(actual["pid"])
        current = {**actual, "created": candidate.create_time()}
        if (actual["port"] != port or actual["executable_sha256"] != plan["runtime"]["files_sha256"]["lib/ollama/llama-server"]
                or os.getpgid(actual["pid"]) != os.getpgrp() or os.getsid(actual["pid"]) != os.getsid(0)):
            raise ValueError("Native API port is not the current owned pinned runner.")
        if bound_runner is not None and current != bound_runner:
            raise ValueError("Native runner identity changed within the one fixed stage.")
        bound_runner = current
        contract.bind_port(port)
        report["bound_runner"] = current

    def api(path, body=None, timeout=10, port=11434):
        if port != 11434:
            check_runner(port)
        kind = contract.allow(path, body, port)
        index = len(report["http_calls"])
        call = {"index": index, "kind": kind, "path": path, "port": port,
                "request": copy.deepcopy(body), "timeout_seconds": min(timeout, 180), "complete": False}
        report["http_calls"].append(call); save(output, report)
        raw_path = response_dir / (str(index) + ".bin")
        request = urllib.request.Request("http://127.0.0.1:" + str(port) + path,
                  data=None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
        try:
            try:
                response = opener.open(request, timeout=min(timeout, 180))
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.status
                raw = response.read(HTTP_LIMIT + 1)
            with raw_path.open("xb") as stream: stream.write(raw)
            call["raw_response"] = record(raw_path); call["http_status"] = status
            if len(raw) > HTTP_LIMIT:
                raise ValueError("Native response exceeds the bounded capture; retained data is incomplete.")
            value = strict_json(raw)
            call["response"] = value
            if status >= 400:
                raise NativeHTTPError(status, value, copy.deepcopy(call))
            contract.observe(kind, value)
            call["complete"] = True
            return value
        except BaseException as error:
            call["error"] = {"type": type(error).__name__, "message": str(error)}
            raise
        finally:
            report["request_counts"] = copy.deepcopy(contract.counts)
            save(output, report)

    common.api = api
    try:
        require_storage()
        for name, digest in plan["runtime"]["files_sha256"].items():
            if sha(Path(plan["runtime"]["directory"]) / name) != digest:
                raise ValueError("Pinned native runtime executable changed.")
        common.verify_blob(runtime, profile)
        report["cache"] = native_verify.cache_identity(runtime, profile)
        prior = read(PRIOR / "prepare.json")
        if report["cache"] != prior["cache"]:
            raise ValueError("The verified selected model/native package changed.")
        report["header"] = prior["header"]  # Full model bytes above remain identical.
        with socket.socket() as probe: probe.bind(("127.0.0.1", 11434))
        fd = os.open(daemon_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as log:
            process = subprocess.Popen([str(Path(plan["runtime"]["directory"]) / "bin/ollama"), "serve"],
                                       env=common.daemon_environment(runtime), stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=False)
            report["daemon_pid"] = process.pid
            report["runtime_version"] = common.ready(process)
            if report["runtime_version"].get("version") != plan["runtime"]["version"]:
                raise ValueError("Actual owned runtime version differs.")
            report["show"] = api("/api/show", {"model": plan["model"]["local_name"]})
            if (report["show"].get("system", "") or report["show"]["template"] != prior["show"]["template"]
                    or parameters(report["show"]["parameters"]) != profile["native_setup"]["import_parameters"]):
                raise ValueError("Native template, stops, context, sampling or publisher persona differs.")
            for case, expected in zip(cases, requests):
                if case["id"] != expected["id"]:
                    raise ValueError("Complete native source order changed.")
                value = native_verify.native_preflight(expected["request"], case, process, profile, report["header"])
                report["prompts"].append(value); save(output, report)
                event("case_complete", id=case["id"], native_render_only=True, generation_calls=0)
                if len(report["prompts"]) == 1:
                    event("initialized", generation_calls=0)
            for query in queries:
                check_runner(bound_runner["port"])
                row = {"id": query["id"], "request": query["request"], "port": bound_runner["port"]}
                report["grammars"].append(row); save(output, report)
                try:
                    value = api("/completion", query["request"], timeout=60, port=bound_runner["port"])
                except NativeHTTPError as error:
                    message = str(error.body.get("error", "")) if isinstance(error.body, dict) else ""
                    if (query["id"] != "unsupported-lookahead-gate-sentinel" or error.status not in (400, 500)
                            or not any(word in message.lower() for word in ("schema", "pattern", "grammar"))):
                        raise
                    row["conversion_error_closed"] = True
                    row["response_receipt"] = error.receipt
                    save(output, report)
                    continue
                grammar = value.get("generation_settings/grammar")
                if (not isinstance(grammar, str) or not grammar or "\0" in grammar
                        or len(grammar.encode("utf-8")) > 1024**2
                        or re.search(r"(?m)^root\s*::=", grammar) is None):
                    raise ValueError("Native conversion did not return bounded root-bearing GBNF.")
                destination = grammar_dir / (query["id"] + ".gbnf")
                with destination.open("xb") as stream: stream.write(grammar.encode("utf-8"))
                row["grammar"] = record(destination)
                row["response_call_index"] = len(report["http_calls"]) - 1
                row["actual_native_grammar_observed"] = True
                save(output, report)
    finally:
        if process is not None:
            try:
                report["unload_response"] = api("/api/chat", {"model": plan["model"]["local_name"],
                    "messages": [], "keep_alive": 0, "stream": False})
                report["resident_after_unload"] = api("/api/ps")
            except BaseException as error:
                report["unload_error"] = {"type": type(error).__name__, "message": str(error)}
            report["owned_daemon_stopped"] = stop_daemon(process) and process.poll() is not None
        common.api = original_api
        report["native_api_builder_restored"] = common.api is original_api
        if daemon_log.exists():
            raw = daemon_log.read_bytes()
            report["private_daemon_log"] = record(daemon_log)
            lines = raw.decode("utf-8", errors="replace").splitlines()
            report["converter_fallback_diagnostics"] = [line for line in lines if "accepting any string" in line]
        save(output, report)
    if (not report.get("owned_daemon_stopped") or report.get("unload_error")
            or report.get("unload_response", {}).get("done_reason") != "unload"
            or report.get("resident_after_unload", {}).get("models") != []):
        raise ValueError("The zero-generation native phase did not explicitly unload and stop cleanly.")
    contract.require_complete()
    for line in report.get("converter_fallback_diagnostics", []):
        if "pattern ^(?=.*<x0/>).*$ is not supported" not in line:
            raise ValueError("A real candidate schema produced an unsupported-pattern fallback diagnostic.")
    report["all_native_conversion_requests_complete"] = True
    report["grammar_enforcement_not_yet_validated"] = True
