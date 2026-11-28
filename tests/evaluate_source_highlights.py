#!/usr/bin/env python3
"""Evaluate actual source-excerpt selection against frozen owned transcripts.

No inference, model downloads or network services are needed. Exact source
fidelity and reference coverage are separate: matching copied text does not
establish useful, balanced or non-misleading highlights. Reference criteria
are never passed to the selector.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CORPORA = {
    "development": ROOT / "tests/fixtures/source_highlights_development.json",
    "validation": ROOT / "tests/fixtures/source_highlights_validation_v1.json",
}
FREEZE = ROOT / "docs/source-highlights-2026-11-28/corpus-freeze.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def checkpoint(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_corpus(split: str, selected: list[str]) -> tuple[dict, list[dict], str]:
    path = CORPORA[split]
    raw = path.read_bytes()
    if len(raw) > 512 * 1024:
        raise ValueError("Corpus exceeds the evaluation size bound.")
    corpus_hash = digest(raw)
    freeze = json.loads(FREEZE.read_bytes())
    expected = next((item["sha256"] for item in freeze["files"]
                     if item["path"] == path.relative_to(ROOT).as_posix()), None)
    if expected != corpus_hash:
        raise ValueError("Corpus does not match its pre-output freeze record.")
    corpus = json.loads(raw)
    canonical(corpus)
    if (corpus.get("schema_version") != 1 or corpus.get("frozen") is not True
            or corpus.get("split") != split):
        raise ValueError("Expected a frozen schema-version-1 corpus for this split.")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 16:
        raise ValueError("Expected one to sixteen cases.")
    identifiers = set()
    for case in cases:
        identifier = case.get("id", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", identifier) or identifier in identifiers:
            raise ValueError("Case identifiers must be unique short ASCII names.")
        identifiers.add(identifier)
        if case.get("source_language") not in {"en", "el"}:
            raise ValueError("This corpus evaluates only English and Greek sources.")
        segments = case.get("segments")
        if not isinstance(segments, list) or not 1 <= len(segments) <= 512:
            raise ValueError("Invalid source segment count.")
        previous = -1
        for segment in segments:
            start, end, text = segment.get("start"), segment.get("end"), segment.get("text")
            if (not isinstance(text, str) or not text.strip()
                    or any(isinstance(n, bool) or not isinstance(n, (int, float))
                           or not math.isfinite(n) for n in (start, end))
                    or not 0 <= start <= end <= 7200 or start < previous):
                raise ValueError("Invalid source text or timestamps.")
            previous = start
        groups = [group for goal in case["coverage_goals"]
                  for group in goal["sufficient_segment_groups"]]
        for rule in case["context_rules"]:
            groups.append(rule["when_any_selected"])
            groups.extend(rule["require_any_complete_group"])
        if any(not group or any(isinstance(i, bool) or not isinstance(i, int)
                                or not 0 <= i < len(segments) for i in group)
               for group in groups):
            raise ValueError("Reference criteria contain invalid source indices.")
    if len(selected) != len(set(selected)) or set(selected) - identifiers:
        raise ValueError("Requested case IDs must be unique and exist in this split.")
    return corpus, [case for case in cases if not selected or case["id"] in selected], corpus_hash


def audit_selection(result: dict, segments: list[dict]) -> tuple[list[int], list[str]]:
    """Independently reconstruct every output passage from original segments."""
    if (not isinstance(result, dict) or result.get("kind") != "source_highlights"
            or result.get("version") != 1
            or result.get("method") != "deterministic_source_selection"):
        raise ValueError("Unexpected source-highlights result contract.")
    excerpts = result.get("excerpts")
    if not isinstance(excerpts, list) or not 1 <= len(excerpts) <= 6:
        raise ValueError("Expected one to six actual excerpts.")
    selected = []
    previous = -1
    for excerpt in excerpts:
        if set(excerpt) != {"segment_indices", "start", "end", "text"}:
            raise ValueError("Unexpected excerpt fields, including possible generated headings.")
        indices = excerpt["segment_indices"]
        if (not isinstance(indices, list) or not indices
                or any(isinstance(i, bool) or not isinstance(i, int)
                       or not 0 <= i < len(segments) for i in indices)
                or indices != list(range(indices[0], indices[-1] + 1))
                or indices[0] <= previous):
            raise ValueError("Excerpt source indices are invalid, noncontiguous or repeated.")
        if excerpt["text"] != "\n".join(segments[i]["text"] for i in indices):
            raise ValueError("Delivered excerpt changes or truncates the source text.")
        if (excerpt["start"] != segments[indices[0]]["start"]
                or excerpt["end"] != max(segments[i]["end"] for i in indices)):
            raise ValueError("Excerpt timestamps are not actual source boundaries.")
        selected.extend(indices)
        previous = indices[-1]
    if (result.get("source_segment_count") != len(segments)
            or result.get("selected_segment_count") != len(selected)):
        raise ValueError("Reported source or selection count is inaccurate.")
    return selected, ["verbatim complete source segments", "actual timestamp boundaries",
                      "ordered contiguous passages", "no duplicate source selections",
                      "no generated excerpt headings", "accurate segment counts"]


def review_coverage(case: dict, selected: list[int]) -> dict:
    chosen = set(selected)
    goals = []
    for goal in case["coverage_goals"]:
        matches = [group for group in goal["sufficient_segment_groups"] if set(group) <= chosen]
        goals.append({**goal, "covered": bool(matches), "matched_groups": matches})
    contexts = []
    for rule in case["context_rules"]:
        applies = bool(chosen.intersection(rule["when_any_selected"]))
        satisfied = any(set(group) <= chosen for group in rule["require_any_complete_group"])
        contexts.append({**rule, "applies": applies, "satisfied": not applies or satisfied})
    return {"goals_covered": sum(goal["covered"] for goal in goals),
            "goals_total": len(goals), "goals": goals, "context_rules": contexts,
            "review_flags": (["Missing reference coverage: " + goal["description"]
                              for goal in goals if not goal["covered"]]
                             + ["Possible context loss: " + item["reason"]
                                for item in contexts if not item["satisfied"]]),
            "semantic_quality": "unreviewed",
            "note": "Reference matches check source inclusion, not general semantic safety or usefulness."}


def evaluate(split: str, selected: list[str], output: Path, strict: bool) -> int:
    if output.exists():
        raise ValueError("Use a new output path to preserve earlier evaluation evidence.")
    corpus, cases, corpus_hash = read_corpus(split, selected)
    module_path = ROOT / "source_highlights.py"
    identity = {"source_highlights.py": digest(module_path.read_bytes()),
                "tests/evaluate_source_highlights.py": digest(Path(__file__).read_bytes()),
                CORPORA[split].relative_to(ROOT).as_posix(): corpus_hash}
    import source_highlights
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    report = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
              "split": split, "corpus_version": corpus["corpus_version"],
              "requested_case_ids": [case["id"] for case in cases],
              "source_sha256": identity, "git_commit": commit,
              "python": platform.python_version(), "complete": False,
              "corpus_complete": False, "semantic_quality": "unreviewed", "cases": []}
    checkpoint(output, report)
    for case in cases:
        entry = {"id": case["id"], "source_language": case["source_language"],
                 "purpose": case["purpose"], "source_segments": case["segments"],
                 "input_sha256": digest(canonical(case["segments"])),
                 "review_questions": case["review_questions"]}
        started = time.monotonic()
        try:
            supplied = deepcopy(case["segments"])
            result = source_highlights.select_highlights(supplied, source_language=case["source_language"])
            entry["result"] = result
            if supplied != case["segments"]:
                raise ValueError("Selector mutated the original source segments.")
            chosen, checks = audit_selection(result, case["segments"])
            source_highlights.validate_highlights(result, case["segments"])
            entry.update({"execution_status": "passed", "fidelity_checks": checks,
                          "selected_indices": chosen, "selection_fraction": len(chosen) / len(supplied),
                          "source_text_bytes": sum(len(s["text"].encode("utf-8")) for s in supplied),
                          "selected_text_bytes": sum(len(e["text"].encode("utf-8")) for e in result["excerpts"]),
                          "coverage": review_coverage(case, chosen)})
        except Exception as error:
            entry.update({"execution_status": "failed", "error": f"{type(error).__name__}: {error}"})
        entry["elapsed_seconds"] = round(time.monotonic() - started, 6)
        report["cases"].append(entry)
        checkpoint(output, report)
    unchanged = all(digest((ROOT / name).read_bytes()) == value for name, value in identity.items())
    report.update({"complete": True, "corpus_complete": len(cases) == len(corpus["cases"]),
                   "source_unchanged": unchanged, "finished_at": datetime.now(timezone.utc).isoformat(),
                   "execution_failures": sum(c["execution_status"] != "passed" for c in report["cases"]),
                   "cases_with_review_flags": sum(bool(c.get("coverage", {}).get("review_flags"))
                                                  for c in report["cases"])})
    checkpoint(output, report)
    print(json.dumps({key: report[key] for key in ("complete", "corpus_complete", "source_unchanged",
                                                  "execution_failures", "cases_with_review_flags")}, indent=2))
    if not unchanged or report["execution_failures"]:
        return 1
    return 2 if strict and report["cases_with_review_flags"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=tuple(CORPORA), default="development")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fail-on-review-flags", action="store_true")
    args = parser.parse_args()
    raise SystemExit(evaluate(args.split, args.case, args.output, args.fail_on_review_flags))
