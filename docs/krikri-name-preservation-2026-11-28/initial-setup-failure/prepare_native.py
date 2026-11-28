"""Render the new generic instruction with the unchanged verified native model.

This phase reuses the prior import and generates no model response.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess

from context import BASE, HERE, ROOT, PRIVATE, common, read_plan, cache_identity, native_preflight


def main():
    plan = read_plan()
    runtime = Path(plan["storage"]["owned_runtime_directory"])
    output = HERE / "prepare.json"
    if output.exists():
        raise ValueError("Refusing to repeat name-instruction preparation.")
    report = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "generation_calls": 0, "native_create_calls": 0, "model_downloads": 0,
              "plan_sha256": common.sha(HERE / "plan.json"), "baseline_manifest_sha256": common.sha(BASE / "evidence-manifest.json")}
    common.save(output, report)
    process = None
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("External supervisor stopped preparation.")))
    try:
        common.verify_blob(runtime, plan)
        prepared = json.loads((BASE / "prepare.json").read_text())
        report["header"] = prepared["header"]
        report["cache"] = cache_identity(runtime, plan)
        if report["cache"] != prepared["cache"]:
            raise ValueError("The native model/package differs from the frozen failed baseline.")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 11434))
        PRIVATE.mkdir(parents=True, exist_ok=True)
        fd = os.open(PRIVATE / "prepare-daemon-private.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as log:
            process = subprocess.Popen([str(Path(plan["runtime"]["directory"]) / "bin/ollama"), "serve"],
                                       env=common.daemon_environment(runtime), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            report["runtime"] = common.ready(process)
            if report["runtime"].get("version") != plan["runtime"]["version"]:
                raise ValueError("Runtime differs from the original fixed profile.")
            report["show"] = common.api("/api/show", {"model": plan["model"]["local_name"]})
            if report["show"]["template"] != prepared["show"]["template"] or report["show"]["parameters"] != prepared["show"]["parameters"] or report["show"].get("system", ""):
                raise ValueError("Native template/parameters/persona differ from the frozen baseline.")
            cases = json.loads((HERE / "development-cases.json").read_text())["cases"]
            expected = json.loads((HERE / "expected-requests.json").read_text())
            report["prompts"] = []
            for case, request in zip(cases, expected):
                if case["id"] != request["id"]:
                    raise ValueError("The original source/request order changed.")
                value = native_preflight(request["request"], case, process, plan, report["header"])
                if not report["prompts"]:
                    common.event("case_start", id="name-instruction-render-only", generation_calls=0)
                report["prompts"].append(value)
                common.save(output, report)
            report["unload_response"] = common.api("/api/chat", {"model": plan["model"]["local_name"], "messages": [], "keep_alive": 0, "stream": False})
            report["resident_after_unload"] = common.api("/api/ps")
            if report["unload_response"].get("done_reason") != "unload" or report["resident_after_unload"].get("models") != []:
                raise ValueError("Native render-only preparation did not unload cleanly.")
            report["complete"] = True
            common.event("case_complete", id="name-instruction-render-only", generation_calls=0,
                         prompt_token_counts=[p["prompt_tokens"] for p in report["prompts"]])
    except BaseException as error:
        report["complete"] = False
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if process is not None:
            common.stop_owned(process)
            report["owned_daemon_stopped"] = process.poll() is not None
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
        report["complete"] &= report["frozen_inputs_unchanged"]
        common.save(output, report)
    common.event("phase_complete", phase="prepare", complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
