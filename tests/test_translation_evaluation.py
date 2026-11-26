"""Evaluator regressions use synthetic model responses, never language approval."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import enhancements


spec = importlib.util.spec_from_file_location(
    "linkscribe_quality", Path(__file__).with_name("evaluate_translation_quality.py"))
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


def make_case(identifier="example", split="development"):
    return {
        "id": identifier, "split": split, "source_language": "en", "target_language": "el",
        "categories": ["terminology", "numbers"],
        "segments": [{"start": 0.25, "end": 3.75, "speaker": "Speaker 1",
                      "text": "Maria saved 12 transcripts.", "extra": {"preserve": True}}],
        "reference_translations": ["Η Μαρία αποθήκευσε 12 απομαγνητοφωνήσεις."],
        "review_criteria": ["The person saved the transcripts, not the audio."],
        "indicators": {"required_terms": [{"label": "transcripts",
                                             "alternatives": ["απομαγνητοφωνήσεις"]}],
                       "numbers": ["12"]},
    }


@pytest.fixture
def corpus(tmp_path):
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps({"schema_version": 1, "corpus_version": "test-v1",
                               "cases": [make_case()]}, ensure_ascii=False), encoding="utf-8")
    return path


def change_corpus(path, cases):
    value = json.loads(path.read_text(encoding="utf-8"))
    value["cases"] = cases
    path.write_text(json.dumps(value, ensure_ascii=True), encoding="utf-8")


def install_model(monkeypatch, chat=None, tags=None):
    calls = []

    def transport(path, payload=None, timeout=1.5):
        if path == "/api/version":
            return {"version": "test-runtime"}
        if path == "/api/tags":
            return {"models": [{"name": "qwen3:4b", "digest": "a" * 64,
                                "details": {"quantization_level": "Q4_K_M"}}]} if tags is None else tags
        assert path == "/api/chat"
        calls.append(copy.deepcopy(payload))
        return chat(payload) if chat else {
            "done": True,
            "message": {"content": json.dumps({"translations": ["Η Μαρία αποθήκευσε 12 απομαγνητοφωνήσεις."]})},
        }

    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.delenv("LINKSCRIBE_TRANSLATION_MODEL", raising=False)
    monkeypatch.delenv("LINKSCRIBE_OLLAMA_URL", raising=False)
    monkeypatch.delenv("LINKSCRIBE_OLLAMA_THREADS", raising=False)
    monkeypatch.setattr(enhancements, "local_ollama_json", transport)
    return transport, calls


def reply(text):
    return {"done": True, "message": {"content": json.dumps({"translations": [text]})}}


def run(corpus, tmp_path, **kwargs):
    return quality.evaluate(corpus, tmp_path / "report.json", **kwargs)


def test_real_production_boundary_preserves_provenance_without_quality_approval(monkeypatch, corpus, tmp_path):
    original, calls = install_model(monkeypatch)
    report, code = run(corpus, tmp_path)
    assert code == 0 and report["complete"] and report["corpus_complete"]
    assert report["automatic_status"] == "pass"
    assert report["semantic_quality"] == report["cases"][0]["semantic_quality"] == "unreviewed"
    assert report["runtime"]["model"]["digest"] == "a" * 64
    assert report["runtime"]["ollama_version"] == "test-runtime"
    assert report["source"]["sha256"]["corpus.json"] == hashlib.sha256(corpus.read_bytes()).hexdigest()
    item = report["cases"][0]
    assert all(item["structural_checks"].values())
    assert item["request_count"] == 1
    assert item["requests"][0]["request"] == calls[0]
    assert calls[0]["options"] == {"temperature": 0, "num_ctx": 8192, "num_predict": 2048}
    assert item["requests"][0]["request_bytes_utf8"] == len(json.dumps(calls[0]).encode())
    assert json.loads(item["requests"][0]["response_json"])["done"] is True
    assert enhancements.local_ollama_json is original
    # Only source text enters the prompt: reference answers and review notes cannot leak.
    request = json.dumps(calls[0], ensure_ascii=False)
    assert "Maria saved 12 transcripts." in request
    assert item["reference_translations"][0] not in request
    assert item["review_criteria"][0] not in request


def test_lexical_pass_cannot_certify_negation_scope(monkeypatch, corpus, tmp_path):
    case = make_case()
    case["segments"][0]["text"] = "Maria saved 12 transcripts, not 21."
    case["indicators"]["numbers"] = ["12", "21"]
    case["review_criteria"] = ["Twelve were saved; twenty-one were not saved."]
    change_corpus(corpus, [case])
    # Both figures and terminology occur, but the meaning is reversed.
    install_model(monkeypatch, lambda _: reply("Η Μαρία αποθήκευσε 21 απομαγνητοφωνήσεις, όχι 12."))
    report, code = run(corpus, tmp_path)
    assert code == 0 and report["automatic_status"] == "pass"
    assert report["semantic_quality"] == "unreviewed"
    assert "negation" in report["interpretation"]


def test_actual_thread_setting_is_recorded_without_changing_the_request(monkeypatch, corpus, tmp_path):
    _, calls = install_model(monkeypatch)
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_THREADS", "4")
    report, code = run(corpus, tmp_path)
    assert code == 0
    assert calls[0]["options"]["num_thread"] == 4
    assert report["cases"][0]["requests"][0]["request"]["options"] == calls[0]["options"]


def test_evaluator_identifies_translation_override_and_passes_source_language(monkeypatch, corpus, tmp_path):
    original, calls = install_model(monkeypatch, lambda _: {
        "done": True, "message": {"content": "Η Μαρία αποθήκευσε 12 απομαγνητοφωνήσεις."}},
        tags={"models": [{"name": "translategemma:4b", "digest": "b" * 64}]})
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "")  # Summary configuration is independent.
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")
    sources = []
    translate = enhancements.translate_segments

    def tracked(segments, target, source_language=None):
        sources.append(source_language)
        return translate(segments, target, source_language=source_language)

    monkeypatch.setattr(enhancements, "translate_segments", tracked)
    report, code = run(corpus, tmp_path)
    assert code == 0 and sources == ["en"]
    assert report["runtime"]["task"] == "translation"
    assert report["runtime"]["translation_profile"] == "translategemma"
    assert report["runtime"]["configured_model"] == "translategemma:4b"
    assert report["runtime"]["model"]["digest"] == "b" * 64
    assert calls[0]["model"] == "translategemma:4b" and "format" not in calls[0]
    assert enhancements.local_ollama_json is original


@pytest.mark.parametrize("text,kind", [
    ("Maria saved 12 transcripts.", "unchanged_source"),
    ("Maria saved 12 transcripts.", "target_script_missing"),
    ("Η Μαρία saved twelve transcripts in the local directory.", "substantial_latin_text"),
    ("Η Μαρία αποθήκευσε 12 αρχεία.", "term_not_observed"),
    ("Η Μαρία αποθήκευσε 112 απομαγνητοφωνήσεις.", "number_not_observed"),
])
def test_lexical_misses_request_review_without_claiming_execution_failed(monkeypatch, corpus, tmp_path, text, kind):
    install_model(monkeypatch, lambda _: reply(text))
    report, code = run(corpus, tmp_path)
    assert code == 0 and report["automatic_status"] == "review"
    assert kind in {flag["kind"] for flag in report["cases"][0]["review_flags"]}
    assert report["semantic_quality"] == "unreviewed"
    strict, code = run(corpus, tmp_path, fail_on_review=True)
    assert code == 1 and strict["counts"]["review"] == 1


@pytest.mark.parametrize("number", ["5,00:00", "5.000", "50000"])
def test_number_tokens_do_not_use_substring_matches(monkeypatch, corpus, tmp_path, number):
    case = make_case()
    case["indicators"]["numbers"] = ["5,000"]
    change_corpus(corpus, [case])
    install_model(monkeypatch, lambda _: reply(f"Υπάρχουν {number} απομαγνητοφωνήσεις."))
    report, _ = run(corpus, tmp_path)
    assert any(flag.get("expected") == "5,000" for flag in report["cases"][0]["review_flags"])


def test_repeated_numbers_have_occurrence_counts(monkeypatch, corpus, tmp_path):
    case = make_case()
    case["indicators"]["numbers"] = ["12", "12"]
    change_corpus(corpus, [case])
    install_model(monkeypatch)
    report, _ = run(corpus, tmp_path)
    assert {"kind": "number_not_observed", "expected": "12", "expected_count": 2,
            "observed_count": 1} in report["cases"][0]["review_flags"]


def test_copied_segment_is_detected_when_another_segment_is_greek(monkeypatch, corpus, tmp_path):
    case = make_case()
    case["segments"].append({"start": 4, "end": 6, "text": "The invoice costs 21 euros."})
    case["reference_translations"].append("Το τιμολόγιο είναι 21 ευρώ.")
    change_corpus(corpus, [case])
    install_model(monkeypatch, lambda _: {"message": {"content": json.dumps({"translations": [
        "Η Μαρία αποθήκευσε 12 απομαγνητοφωνήσεις.", "The invoice costs 21 euros."]})}})
    report, _ = run(corpus, tmp_path)
    assert {"kind": "unchanged_source", "segment": 1} in report["cases"][0]["review_flags"]


@pytest.mark.parametrize("failure", ["mutate", "metadata", "count", "invalid_text"])
def test_structural_failures_cannot_be_lexical_passes(monkeypatch, corpus, tmp_path, failure):
    install_model(monkeypatch)

    def broken(source, target, source_language=None):
        result = copy.deepcopy(source)
        result[0]["text"] = "Η Μαρία αποθήκευσε 12 απομαγνητοφωνήσεις."
        if failure == "mutate":
            source[0]["extra"]["preserve"] = False
        elif failure == "metadata":
            result[0].pop("speaker")
        elif failure == "count":
            result.append(copy.deepcopy(result[0]))
        else:
            result[0]["text"] = "\ud800"
        return result

    monkeypatch.setattr(enhancements, "translate_segments", broken)
    report, code = run(corpus, tmp_path)
    assert code == 1 and report["automatic_status"] == "fail"
    assert not all(report["cases"][0]["structural_checks"].values())
    assert report["cases"][0]["review_flags"] == []


def test_source_mutation_is_retained_even_when_inference_raises(monkeypatch, corpus, tmp_path):
    install_model(monkeypatch)

    def broken(source, target, source_language=None):
        source[0]["start"] = 999
        raise RuntimeError("failed after mutation")

    monkeypatch.setattr(enhancements, "translate_segments", broken)
    report, code = run(corpus, tmp_path)
    assert code == 1 and report["automatic_status"] == "error"
    assert report["cases"][0]["structural_checks"]["source_unchanged"] is False


@pytest.mark.parametrize("content", ['{"translations":["one"],"translations":["two"]}',
                                      '{"translations":["\\ud800"]}'])
def test_rejected_model_responses_are_saved_losslessly(monkeypatch, corpus, tmp_path, content):
    outer = {"done": True, "message": {"content": content}}
    original, _ = install_model(monkeypatch, lambda _: outer)
    report, code = run(corpus, tmp_path)
    assert code == 1 and report["cases"][0]["automatic_status"] == "error"
    saved = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert json.loads(saved["cases"][0]["requests"][0]["response_json"]) == outer
    assert enhancements.local_ollama_json is original


def test_malformed_outer_json_is_retained_before_production_wraps_error(monkeypatch, corpus, tmp_path):
    document = '{"message": invalid \ud800'

    def broken(_):
        raise json.JSONDecodeError("synthetic broken JSON", document, 12)

    install_model(monkeypatch, broken)
    report, code = run(corpus, tmp_path)
    assert code == 1
    request = report["cases"][0]["requests"][0]
    assert request["invalid_response_text"] == document
    assert request["raw_evidence_available"] is True
    assert "\\ud800" in (tmp_path / "report.json").read_text(encoding="utf-8")


def test_response_metadata_nan_does_not_destroy_valid_report(monkeypatch, corpus, tmp_path):
    outer = reply("Η Μαρία αποθήκευσε 12 απομαγνητοφωνήσεις.")
    outer["duration"] = float("nan")
    install_model(monkeypatch, lambda _: outer)
    report, code = run(corpus, tmp_path)
    assert code == 0
    assert "NaN" in report["cases"][0]["requests"][0]["response_json"]
    json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))


def test_transport_failure_identifies_absent_raw_evidence(monkeypatch, corpus, tmp_path):
    def offline(_):
        raise TimeoutError("synthetic timeout")

    original, _ = install_model(monkeypatch, offline)
    report, code = run(corpus, tmp_path)
    assert code == 1 and report["complete"]
    request = report["cases"][0]["requests"][0]
    assert request["raw_evidence_available"] is False
    assert request["raw_evidence_unavailable_reason"]
    assert "response_json" not in request
    assert enhancements.local_ollama_json is original


@pytest.mark.parametrize("tags", [{"models": []}, {"models": [{"name": "qwen3:4b"}]},
                                  {"models": [{"name": "qwen3:4b", "digest": "test", "bad": float("nan")}] }])
def test_bad_model_setup_leaves_incomplete_report_without_inference(monkeypatch, corpus, tmp_path, tags):
    _, calls = install_model(monkeypatch, tags=tags)
    report, code = run(corpus, tmp_path)
    assert code == 1 and not report["complete"] and not report["corpus_complete"]
    assert report["automatic_status"] == "incomplete"
    assert report["completed_cases"] == 0 and report["requested_cases"] == 1
    assert report["error"] and calls == []
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["error"] == report["error"]


def test_interrupt_keeps_completed_case_and_inflight_request(monkeypatch, corpus, tmp_path):
    change_corpus(corpus, [make_case("first"), make_case("second", "holdout")])
    completed = []

    def chat(_):
        if completed:
            pending = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
            assert pending["completed_cases"] == 1 and pending["complete"] is False
            assert pending["cases"][1]["requests"][0]["request"]["model"] == "qwen3:4b"
            raise KeyboardInterrupt()
        completed.append(True)
        return reply("Η Μαρία αποθήκευσε 12 απομαγνητοφωνήσεις.")

    original, _ = install_model(monkeypatch, chat)
    report, code = run(corpus, tmp_path)
    assert code == 130 and not report["complete"]
    assert report["completed_cases"] == 1 and report["requested_cases"] == 2
    assert report["counts"] == {"pass": 1, "review": 0, "fail": 0, "error": 0, "incomplete": 1}
    assert report["cases"][1]["requests"][0]["error"]["type"] == "KeyboardInterrupt"
    assert report["selection"]["case_ids"] == ["first", "second"]
    assert enhancements.local_ollama_json is original


def test_checkpoint_replace_failure_keeps_previous_report_and_removes_tempfile(monkeypatch, tmp_path):
    path = tmp_path / "report.json"
    quality.atomic_checkpoint(path, {"complete": False})

    def fail_replace(*_):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(quality.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk failure"):
        quality.atomic_checkpoint(path, {"complete": True})
    assert json.loads(path.read_text(encoding="utf-8")) == {"complete": False}
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("kwargs", [{"case_ids": ["missing"]}, {"case_ids": ["example", "example"]},
                                    {"splits": ["unknown"]}, {"splits": ["holdout"]}])
def test_invalid_selection_is_rejected_before_model_access(monkeypatch, corpus, tmp_path, kwargs):
    _, calls = install_model(monkeypatch)
    with pytest.raises(ValueError):
        run(corpus, tmp_path, **kwargs)
    assert not calls


def test_subset_completion_is_distinct_from_full_corpus_completion(monkeypatch, corpus, tmp_path):
    change_corpus(corpus, [make_case("dev"), make_case("held", "holdout")])
    install_model(monkeypatch)
    report, code = run(corpus, tmp_path, splits=["holdout"])
    assert code == 0 and report["complete"] and not report["corpus_complete"]
    assert report["selection"] == {"case_ids": ["held"], "corpus_cases": 2,
                                    "split_counts": {"holdout": 1}}


def test_report_cannot_overwrite_its_corpus(monkeypatch, corpus):
    _, calls = install_model(monkeypatch)
    before = corpus.read_bytes()
    with pytest.raises(ValueError, match="replace corpus"):
        quality.evaluate(corpus, corpus)
    assert corpus.read_bytes() == before and not calls


def test_cli_exit_code_and_summary_preserve_review_status(monkeypatch, corpus, tmp_path, capsys):
    install_model(monkeypatch, lambda _: reply("Maria saved 12 transcripts."))
    code = quality.main(["--corpus", str(corpus), "--output", str(tmp_path / "report.json"),
                         "--case", "example", "--fail-on-review-flags"])
    summary = json.loads(capsys.readouterr().out)
    assert code == 1 and summary["automatic_status"] == "review"
    assert summary["semantic_quality"] == "unreviewed"


@pytest.mark.parametrize("change", [
    lambda data: data["cases"].append(copy.deepcopy(data["cases"][0])),
    lambda data: data["cases"][0]["segments"][0].update(start=float("nan")),
    lambda data: data["cases"][0]["segments"][0].update(text="\ud800"),
    lambda data: data["cases"][0].update(reference_translations=[]),
])
def test_invalid_corpus_is_rejected(corpus, change):
    data = json.loads(corpus.read_text(encoding="utf-8"))
    change(data)
    corpus.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises((ValueError, UnicodeError)):
        quality.read_corpus(corpus)
