"""Evaluate actual local English/Greek translation; never certify semantic quality.

Run explicitly with an installed local model (no services or downloads are started):
    PYTHONPATH=. python tests/evaluate_translation_quality.py --output /tmp/quality.json

References and review indicators are report data, never model input. A zero exit
code means execution/structure succeeded, not that meaning or fluency is approved.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid

import enhancements


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "tests/fixtures/translation_quality_cases.json"
SPLITS = ("development", "holdout", "long_form")
INTERPRETATION = (
    "Indicators only identify outputs needing review. Indicator pass does not "
    "approve meaning, names, numerical relationships, negation, completeness or fluency. "
    "Complete describes the requested selection; corpus_complete identifies full coverage. "
    "Compare exact outputs with the references and review criteria separately."
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_checkpoint(path, report):
    """Keep the previous valid report until a complete replacement is durable."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_corpus(path):
    raw = Path(path).read_bytes()
    if len(raw) > 512 * 1024:
        raise ValueError("Corpus exceeds the 512 KiB evaluation limit.")
    corpus = json.loads(raw)
    json.dumps(corpus, allow_nan=False)  # Reject non-standard numeric metadata too.
    if not isinstance(corpus, dict) or corpus.get("schema_version") != 1:
        raise ValueError("Expected a schema_version 1 corpus.")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError("Corpus must contain between 1 and 32 cases.")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", case.get("id", "")):
            raise ValueError("Every case needs a short, unique ASCII identifier.")
        if case["id"] in ids:
            raise ValueError("Duplicate corpus case identifier.")
        ids.add(case["id"])
        if (case.get("split") not in SPLITS or
                {case.get("source_language"), case.get("target_language")} != {"en", "el"}):
            raise ValueError("Each case needs a supported split and English/Greek direction.")
        segments, references = case.get("segments"), case.get("reference_translations")
        if (not isinstance(segments, list) or not 1 <= len(segments) <= 100 or
                not isinstance(references, list) or len(references) != len(segments)):
            raise ValueError("Cases need 1–100 segments with aligned reference translations.")
        for segment, reference in zip(segments, references):
            if (not isinstance(segment, dict) or not isinstance(segment.get("text"), str) or
                    not 1 <= len(segment["text"]) <= 30000 or not isinstance(reference, str) or
                    not reference.strip()):
                raise ValueError("Invalid source text or reference translation.")
            for value in (segment["text"], reference):
                value.encode("utf-8")
            start, end = segment.get("start"), segment.get("end")
            if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in (start, end)) or not 0 <= start <= end):
                raise ValueError("Segment timestamps must be finite and ordered.")
        indicators = case.get("indicators", {})
        if not isinstance(indicators, dict):
            raise ValueError("Indicators must be an object.")
        for term in indicators.get("required_terms", []):
            if (not isinstance(term, dict) or not isinstance(term.get("label"), str) or
                    not isinstance(term.get("alternatives"), list) or not term["alternatives"] or
                    any(not isinstance(s, str) or not s.strip() for s in term["alternatives"])):
                raise ValueError("Each term indicator needs a label and nonempty alternatives.")
        if any(not isinstance(s, str) or not s.strip() for s in indicators.get("numbers", [])):
            raise ValueError("Numeric indicators must be nonempty strings.")
    return corpus


def select_cases(corpus, case_ids=None, splits=None):
    cases = corpus["cases"]
    if case_ids and (len(set(case_ids)) != len(case_ids) or
                     set(case_ids) - {case["id"] for case in cases}):
        raise ValueError("Requested case IDs must be known and unique.")
    if splits and set(splits) - set(SPLITS):
        raise ValueError("Unknown corpus split.")
    selected = [case for case in cases if (not case_ids or case["id"] in case_ids)
                and (not splits or case["split"] in splits)]
    if not selected:
        raise ValueError("The requested case/split selection is empty.")
    return selected


def source_identity(corpus_path):
    paths = [ROOT / "enhancements.py", ROOT / "marian_translation.py", Path(__file__), Path(corpus_path)]
    fingerprints = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name:
                    hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    identity = {"sha256": fingerprints, "git_commit": None, "git_dirty": None}
    try:
        identity["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
        identity["git_dirty"] = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL, timeout=5).strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return identity


def runtime_identity():
    if enhancements.translation_backend() == "marian":
        import marian_translation
        if not all(marian_translation.cache_status()["pairs_cached"].values()):
            raise ValueError("Prepare both local models first: python -m marian_translation --pair both")
        return {"backend": "marian-ctranslate2", "task": "translation",
                "models": {pair: marian_translation.model_details(*pair.split("-"))
                           for pair in ("en-el", "el-en")}}
    url, model = enhancements.ollama_settings(task="translation")
    version = enhancements.local_ollama_json("/api/version")
    tags = enhancements.local_ollama_json("/api/tags")
    names = {model, model + ":latest"} if ":" not in model.rsplit("/", 1)[-1] else {model}
    selected = next((item for item in tags.get("models", [])
                     if item.get("name") in names or item.get("model") in names), None)
    if not selected or not selected.get("digest"):
        raise ValueError(f"Configured model {model!r} is not installed with an identifiable digest.")
    if not isinstance(version, dict) or not isinstance(version.get("version"), str):
        raise ValueError("Ollama did not return its runtime version.")
    identity = {"url": url, "ollama_version": version["version"], "configured_model": model,
                "model": copy.deepcopy(selected), "task": "translation",
                "translation_profile": enhancements.translation_profile()}
    json.dumps(identity, allow_nan=False)
    return identity


@contextmanager
def observe_requests(records, checkpoint):
    """Observe the production boundary without replacing its transport policy."""
    if enhancements.translation_backend() == "marian":
        with observe_native_requests(records, checkpoint):
            yield
        return
    original = enhancements.local_ollama_json

    def observed(path, payload=None, timeout=1.5):
        if path != "/api/chat":
            return original(path, payload, timeout=timeout)
        entry = {"request": copy.deepcopy(payload), "timeout_seconds": timeout,
                 "request_bytes_utf8": len(json.dumps(payload).encode("utf-8")),
                 "started_at": utc_now(), "raw_evidence_available": False}
        records.append(entry)
        checkpoint()
        started = time.monotonic()
        try:
            response = original(path, payload, timeout=timeout)
            # This preserves the returned JSON object, including lone surrogates
            # and non-standard floats, without claiming original HTTP whitespace.
            entry["response_json"] = json.dumps(response, ensure_ascii=True, allow_nan=True)
            entry["raw_evidence_available"] = True
            return response
        except BaseException as exc:
            entry["error"] = {"type": type(exc).__name__, "message": str(exc)}
            if isinstance(exc, json.JSONDecodeError):
                entry["invalid_response_text"] = exc.doc
                entry["raw_evidence_available"] = True
            else:
                entry["raw_evidence_unavailable_reason"] = "Production transport did not return response JSON."
            raise
        finally:
            entry["elapsed_seconds"] = round(time.monotonic() - started, 3)
            checkpoint()

    enhancements.local_ollama_json = observed
    try:
        yield
    finally:
        enhancements.local_ollama_json = original


@contextmanager
def observe_native_requests(records, checkpoint):
    """Record actual native arguments/results while delegating all inference."""
    import marian_translation
    original = marian_translation._translate_batch

    def observed(engine, source_tokenizer, target_tokenizer, texts):
        class ObservedEngine:
            def translate_batch(self, tokens, **options):
                entry = {"request": {"backend": "marian-ctranslate2",
                                     "source_texts": copy.deepcopy(texts),
                                     "source_tokens": copy.deepcopy(tokens),
                                     "options": copy.deepcopy(options)},
                         "started_at": utc_now(), "raw_evidence_available": False}
                records.append(entry)
                checkpoint()
                started = time.monotonic()
                try:
                    results = engine.translate_batch(tokens, **options)
                    entry["response_tokens"] = [copy.deepcopy(result.hypotheses) for result in results]
                    entry["raw_evidence_available"] = True
                    return results
                except BaseException as exc:
                    entry["error"] = {"type": type(exc).__name__, "message": str(exc)}
                    raise
                finally:
                    entry["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    checkpoint()

        return original(ObservedEngine(), source_tokenizer, target_tokenizer, texts)

    marian_translation._translate_batch = observed
    try:
        yield
    finally:
        marian_translation._translate_batch = original


def folded(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(c))


def review_flags(case, translated):
    """Conservative lexical signals, deliberately not correctness assertions."""
    texts = [item["text"] for item in translated]
    joined = " ".join(texts)
    flags = []
    for index, (source, text) in enumerate(zip(case["segments"], texts)):
        greek = sum("GREEK" in unicodedata.name(char, "") and char.isalpha() for char in text)
        latin = sum("LATIN" in unicodedata.name(char, "") and char.isalpha() for char in text)
        if folded(source["text"].strip()) == folded(text.strip()) and greek + latin > 3:
            flags.append({"kind": "unchanged_source", "segment": index})
        if case["target_language"] == "el" and latin > 3 and not greek:
            flags.append({"kind": "target_script_missing", "segment": index})
        elif case["target_language"] == "el" and latin > 12 and greek < latin:
            flags.append({"kind": "substantial_latin_text", "segment": index})
        elif case["target_language"] == "en" and greek > 3 and greek > latin / 4:
            flags.append({"kind": "substantial_greek_text", "segment": index})
    for term in case.get("indicators", {}).get("required_terms", []):
        if not any(folded(alternative) in folded(joined) for alternative in term["alternatives"]):
            flags.append({"kind": "term_not_observed", "label": term["label"],
                          "alternatives": term["alternatives"]})
    tokens = Counter(re.findall(r"(?<!\w)[+-]?\d+(?:[.,:]\d+)*(?!\w)", joined))
    for number, count in Counter(case.get("indicators", {}).get("numbers", [])).items():
        if tokens[number] < count:
            flags.append({"kind": "number_not_observed", "expected": number,
                          "expected_count": count, "observed_count": tokens[number]})
    return flags


def structural_checks(before, after, translated):
    count = isinstance(translated, list) and len(translated) == len(before)
    metadata = count and all(isinstance(item, dict) and
                            {k: v for k, v in item.items() if k != "text"} ==
                            {k: v for k, v in source.items() if k != "text"}
                            for source, item in zip(before, translated))
    valid_text = count
    if count:
        for source, item in zip(before, translated):
            text = item.get("text") if isinstance(item, dict) else None
            try:
                valid_text = valid_text and isinstance(text, str) and (
                    bool(text.strip()) or not source["text"].strip())
                if isinstance(text, str):
                    text.encode("utf-8")
            except UnicodeError:
                valid_text = False
    return {"source_unchanged": before == after, "segment_count": count,
            "metadata_preserved": metadata, "valid_text": valid_text}


def evaluate(corpus_path, output, case_ids=None, splits=None, fail_on_review=False):
    corpus_path, output = Path(corpus_path).resolve(), Path(output).resolve()
    if output in {corpus_path, Path(__file__).resolve(), ROOT / "enhancements.py", ROOT / "marian_translation.py"}:
        raise ValueError("Report output must not replace corpus or implementation source.")
    corpus = read_corpus(corpus_path)
    selected = select_cases(corpus, case_ids, splits)
    report = {"schema_version": 1, "run_id": str(uuid.uuid4()), "created_at": utc_now(),
              "corpus_version": corpus.get("corpus_version"), "source": source_identity(corpus_path),
              "interpretation": INTERPRETATION, "semantic_quality": "unreviewed",
              "complete": False, "corpus_complete": False, "automatic_status": "incomplete",
              "requested_cases": len(selected), "completed_cases": 0,
              "selection": {"case_ids": [case["id"] for case in selected],
                            "corpus_cases": len(corpus["cases"]),
                            "split_counts": dict(Counter(case["split"] for case in selected))},
              "runtime": None, "cases": []}
    checkpoint = lambda: atomic_checkpoint(output, report)
    checkpoint()
    started = time.monotonic()
    interrupted = False
    try:
        report["runtime"] = runtime_identity()
        checkpoint()
        for case in selected:
            result = {**copy.deepcopy(case), "automatic_status": "incomplete",
                      "semantic_quality": "unreviewed", "requests": [], "translation": None,
                      "structural_checks": {}, "review_flags": []}
            report["cases"].append(result)
            source = copy.deepcopy(case["segments"])
            before = copy.deepcopy(source)
            case_start = time.monotonic()
            checkpoint()
            try:
                with observe_requests(result["requests"], checkpoint):
                    result["translation"] = enhancements.translate_segments(
                        source, case["target_language"], source_language=case["source_language"])
            except Exception as exc:
                result["error"] = {"type": type(exc).__name__, "message": str(exc)}
            result["structural_checks"] = structural_checks(before, source, result["translation"])
            if "error" in result:
                result["automatic_status"] = "error"
            elif not all(result["structural_checks"].values()):
                result["automatic_status"] = "fail"
            else:
                result["review_flags"] = review_flags(case, result["translation"])
                result["automatic_status"] = "review" if result["review_flags"] else "pass"
            result["elapsed_seconds"] = round(time.monotonic() - case_start, 3)
            result["request_count"] = len(result["requests"])
            report["completed_cases"] += 1
            checkpoint()
            print(f"{case['id']}: {result['automatic_status']} "
                  f"({report['completed_cases']}/{len(selected)})", file=sys.stderr, flush=True)
        report["complete"] = True
        report["corpus_complete"] = len(selected) == len(corpus["cases"])
    except KeyboardInterrupt:
        interrupted = True
        report["error"] = {"type": "KeyboardInterrupt", "message": "Evaluation interrupted; evidence is incomplete."}
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        counts = Counter(case["automatic_status"] for case in report["cases"])
        report["counts"] = {key: counts[key] for key in ("pass", "review", "fail", "error", "incomplete")}
        report["automatic_status"] = ("incomplete" if not report["complete"] else
                                      next((s for s in ("error", "fail", "review") if counts[s]), "pass"))
        report["finished_at"] = utc_now()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        checkpoint()
    exit_code = 130 if interrupted else int(not report["complete"] or counts["error"] > 0 or
                                           counts["fail"] > 0 or (fail_on_review and counts["review"] > 0))
    return report, exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--split", action="append", choices=SPLITS)
    parser.add_argument("--fail-on-review-flags", action="store_true")
    args = parser.parse_args(argv)
    try:
        report, code = evaluate(args.corpus, args.output, args.case_ids, args.split, args.fail_on_review_flags)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: report[key] for key in ("run_id", "complete", "corpus_complete",
                     "automatic_status", "semantic_quality", "completed_cases", "requested_cases", "counts")},
                     ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
