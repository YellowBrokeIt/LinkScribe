#!/usr/bin/env python3
"""Download and verify the declared official model; never run inference."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request

HERE = Path(__file__).resolve().parent
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            result.update(block)
    return result.hexdigest()


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def api(path, body=None, timeout=5):
    request = urllib.request.Request("http://127.0.0.1:11434" + path,
                                    data=None if body is None else json.dumps(body).encode(),
                                    headers={"Content-Type": "application/json"})
    with LOCAL.open(request, timeout=timeout) as response:
        return json.load(response)


def daemon_environment(runtime):
    # Keep startup logs private even though the child receives only a small
    # allowlist. Proxy values, when needed for official downloads, are not evidence.
    keys = ("PATH", "HOME", "LANG", "LC_ALL", "LD_LIBRARY_PATH", "TMPDIR",
            "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY",
            "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy")
    environment = {key: os.environ[key] for key in keys if key in os.environ}
    environment.update({"OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(runtime / "models"),
                        "OLLAMA_NO_CLOUD": "1", "OLLAMA_NUM_PARALLEL": "1",
                        "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_CONTEXT_LENGTH": "8192",
                        "OLLAMA_KEEP_ALIVE": "1m"})
    return environment


def stop_owned(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
    except ProcessLookupError:
        pass


def ready(process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("Owned Ollama daemon exited before readiness.")
        try:
            return api("/api/version")
        except OSError:
            time.sleep(0.25)
    raise TimeoutError("Owned daemon did not become ready.")


def verify_cached_model(runtime, model):
    manifest = runtime / "models/manifests/registry.ollama.ai/library/qwen3" / model["tag"].split(":", 1)[1]
    if sha(manifest) != model["cache_manifest_sha256"]:
        raise ValueError("Cached model manifest does not match the observed runtime layout.")
    expected = json.loads((HERE / "official-manifest.json").read_bytes())
    provenance = {"mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                  "digest": "sha256:" + model["manifest_sha256"],
                  "size": (HERE / "official-manifest.json").stat().st_size}
    cache = json.loads(manifest.read_bytes())
    if cache != {**expected, "layers": [*expected["layers"], provenance]}:
        raise ValueError("Cached descriptors differ from the official package plus its sole provenance layer.")
    verified = []
    for entry in [cache["config"], *cache["layers"]]:
        algorithm, digest = entry["digest"].split(":", 1)
        if algorithm != "sha256":
            raise ValueError("Unexpected model digest algorithm.")
        path = runtime / "models/blobs" / ("sha256-" + digest)
        if path.stat().st_size != entry["size"] or sha(path) != digest:
            raise ValueError("A downloaded model layer failed size/digest verification.")
        verified.append({**entry, "verified": True})
    original = runtime / "models/blobs" / ("sha256-" + model["manifest_sha256"])
    if original.read_bytes() != (HERE / "official-manifest.json").read_bytes():
        raise ValueError("The added provenance blob is not the frozen original registry manifest.")
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--cached-only", action="store_true", help="Verify an already completed pull without another download.")
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    plan = json.loads((HERE / "plan.json").read_text())
    binary = runtime / "bin/ollama"
    if sha(binary) != plan["runtime"]["binary_sha256"]:
        raise ValueError("The runtime differs from the verified release.")
    output = HERE / plan["setup_report"]
    if output.exists():
        raise ValueError("Refusing to overwrite setup evidence.")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 11434))
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "inference_calls": 0, "plan_sha256": sha(HERE / "plan.json"),
              "runtime_binary_sha256": sha(binary), "layers": []}
    save(output, report)
    private_log = runtime / "model-refresh-setup-v2-private.log"
    descriptor = os.open(private_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as log:
            process = subprocess.Popen([str(binary), "serve"], env=daemon_environment(runtime),
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                report["runtime"] = ready(process)
                if report["runtime"].get("version") != plan["runtime"]["version"]:
                    raise ValueError("Runtime version does not match the plan.")
                if api("/api/ps").get("models"):
                    raise ValueError("Pull-only daemon unexpectedly has a resident model.")
                if args.cached_only:
                    report["pull"] = {"performed": False, "reason": "Official pull already succeeded; verifying retained cache only."}
                else:
                    print("Pulling the official candidate; no inference is being run.", flush=True)
                    report["pull"] = api("/api/pull", {"model": plan["model"]["tag"], "stream": False}, timeout=600)
                report["layers"] = verify_cached_model(runtime, plan["model"])
                tags = api("/api/tags")
                selected = next((item for item in tags.get("models", [])
                                 if item.get("name") == plan["model"]["tag"]), None)
                if not selected or selected.get("digest") != plan["model"]["manifest_sha256"]:
                    raise ValueError("Installed model identity does not match the official manifest.")
                report["installed_model"] = selected
                show = api("/api/show", {"model": plan["model"]["tag"]})
                template = show.get("template", "")
                if hashlib.sha256(template.encode()).hexdigest() != plan["model"]["effective_template_sha256"]:
                    raise ValueError("The effective runtime template differs from the separately verified native formatting.")
                report["show"] = show
                report["resident_models_after_pull"] = api("/api/ps").get("models")
                if report["resident_models_after_pull"]:
                    raise ValueError("Setup unexpectedly loaded a model for inference.")
                report["complete"] = True
            finally:
                stop_owned(process)
                report["owned_daemon_stopped"] = process.poll() is not None
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save(output, report)
    print(json.dumps({"complete": report["complete"], "error": report.get("error"),
                      "inference_calls": report["inference_calls"], "output": str(output)}), flush=True)
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
