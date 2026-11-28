"""Opt-in paired speech regression using an isolated snapshot's real harness.

Only the CTranslate2 QA seed and model-resolution observations are added. The
snapshot's normal upload, recognition, persistence and exporters remain in use.
This does not change production ASR options or approve semantic accuracy.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--qa-seed", type=int, default=1729)
    args, remaining = parser.parse_known_args()
    tree = args.source_root.resolve()
    sys.path.insert(0, str(tree))
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    import ctranslate2
    import app
    assert Path(app.__file__).resolve() == tree / "app.py", "Wrong source snapshot imported."
    original = app._recognize

    @functools.wraps(original)
    def recognize(*values, **options):
        ctranslate2.set_random_seed(args.qa_seed)
        return original(*values, **options)

    app._recognize = recognize
    observer = load("quiet_followup_observers", tree / "tests/smoke_real_links.py")
    harness = load("quiet_followup_harness", tree / "tests/smoke_real_asr_quality.py")
    model_events = []

    def event(kind, **fields):
        model_events.append({"kind": kind, **fields})

    observer.observe_model_resolution(importlib.import_module("faster_whisper.transcribe"), event,
                                      lambda: "paired_quiet_regression")
    checkpoint = harness.checkpoint
    probe_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def observed_checkpoint(path, report):
        report["followup_protocol"] = {
            "qa_random_seed": args.qa_seed,
            "seed_scope": "Reset immediately before each actual recognition call in its worker thread.",
            "source_root": str(tree), "wrapper_sha256": probe_hash,
            "production_options_changed_by_wrapper": False,
            "actual_model_resolutions": model_events,
        }
        return checkpoint(path, report)

    harness.checkpoint = observed_checkpoint
    sys.argv = [sys.argv[0], *remaining]
    return harness.main()


if __name__ == "__main__":
    raise SystemExit(main())
