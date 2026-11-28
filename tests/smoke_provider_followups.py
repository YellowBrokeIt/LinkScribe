"""Opt-in follow-up fixtures using the original real-provider acceptance runner.

Run both additional public fixtures from the repository root::

    PYTHONPATH=. python tests/smoke_provider_followups.py --output qa-provider-followups

Or select one explicitly (all original fixture names also remain available)::

    PYTHONPATH=. python tests/smoke_provider_followups.py \
        --fixture vimeo_sintel_rerendered_player --model small \
        --output qa-vimeo-player

The original harness performs actual acquisition, full recording recognition,
SQLite/export checks and restart checks, and returns failure on network/auth
errors. This wrapper only adds fixture definitions and their source fingerprints;
it does not replace fixtures, skip failures, or change the acquisition/ASR path.
Use a new output directory on each run to preserve earlier failure evidence.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_FILE = ROOT / "tests/fixtures/public_provider_followups.json"


def main():
    spec = importlib.util.spec_from_file_location(
        "linkscribe_provider_acceptance", ROOT / "tests/smoke_real_links.py")
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    harness.__doc__ = __doc__
    document = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
    if document["schema_version"] != 1:
        raise ValueError("Unsupported provider follow-up fixture schema.")
    fixtures = document["fixtures"]
    if set(fixtures) & set(harness.FIXTURES):
        raise ValueError("Follow-up fixtures must not replace the original fixture definitions.")
    harness.FIXTURES.update(fixtures)
    harness.SOURCE_FILES += ("tests/smoke_provider_followups.py",
                             "tests/fixtures/public_provider_followups.json")
    if not any(arg == "--fixture" or arg.startswith("--fixture=") for arg in sys.argv[1:]):
        for name in fixtures:
            sys.argv.extend(("--fixture", name))
    return harness.main()


if __name__ == "__main__":
    raise SystemExit(main())
