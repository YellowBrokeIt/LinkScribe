"""Replay saved candidate outputs through the production result check only.

No model requests are made. This is a corruption-check regression, not new
inference or an independent semantic assessment.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import enhancements


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    evidence = ROOT / "docs/gemma4-exposed-v2-2026-11-28"
    output = Path(__file__).with_name("retained-output-replay.json")
    if output.exists():
        raise RuntimeError("Refusing to replace retained replay evidence")
    corpus_path = evidence / "exposed-v2-corpus.json"
    corpus = json.loads(corpus_path.read_text())
    assert digest(corpus_path) == "2f31c4c9019d6bc821208c193a2344a9021c09124779afe21e775f05916e00f3"
    cases = []
    for original in corpus["cases"]:
        report_path = evidence / (original["id"] + ".json")
        saved = json.loads(report_path.read_text())
        assert saved["complete"] is True and len(saved["cases"]) == 1
        case = saved["cases"][0]
        assert case["id"] == original["id"]
        assert case["segments"] == original["segments"]
        source, translated = deepcopy(case["segments"]), deepcopy(case["translation"])
        before_source, before_translation = deepcopy(source), deepcopy(translated)
        try:
            enhancements._translation_result(source, translated, case["source_language"],
                                             case["target_language"])
            rejected, warning = False, None
        except enhancements.EnhancementError as exc:
            rejected, warning = True, str(exc)
        assert source == before_source and translated == before_translation
        cases.append({
            "id": case["id"], "retained_report": str(report_path.relative_to(ROOT)),
            "retained_report_sha256": digest(report_path),
            "rejected_by_result_guard": rejected, "warning": warning,
            "source_and_retained_translation_unchanged": True,
            "translation_meaning_approved": False,
        })
    result = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Replay existing full candidate outputs through the result guard; no model execution",
        "model_requests": 0, "corpus_sha256": digest(corpus_path),
        "enhancements_sha256": digest(ROOT / "enhancements.py"),
        "replay_sha256": digest(Path(__file__)),
        "case_count": len(cases),
        "rejected_count": sum(c["rejected_by_result_guard"] for c in cases),
        "translation_semantic_acceptance": False, "v1_release_approved": False,
        "cases": cases,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"case_count": len(cases), "rejected_count": result["rejected_count"],
                      "output": str(output.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
