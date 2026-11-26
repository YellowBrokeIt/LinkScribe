"""Model lifetime tests use synthetic transports and small Python objects."""
from copy import deepcopy
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import weakref

import pytest

import app
import enhancements as ai


@pytest.fixture(autouse=True)
def clean_runtime(monkeypatch):
    for key in ("LINKSCRIBE_OLLAMA_MODEL", "LINKSCRIBE_TRANSLATION_MODEL", "LINKSCRIBE_TRANSLATION_BACKEND",
                "LINKSCRIBE_OLLAMA_URL", "LINKSCRIBE_OLLAMA_THREADS", "LINKSCRIBE_OLLAMA_RETAIN_MODELS"):
        monkeypatch.delenv(key, raising=False)
    assert ai._OLLAMA_PHASE.get() is None


def segments():
    return [{"start": 0.5, "end": 2.5, "text": "First source."},
            {"start": 3.5, "end": 5.5, "text": "Second source."}]


def prime_audio(monkeypatch):
    references = []

    class Model:
        def __init__(self):
            self.cycle = self  # Exercise a model-wrapper reference cycle.
            references.append(weakref.ref(self))

    def cached():
        return lru_cache(maxsize=1)(Model)

    whisper, speaker, vad = cached(), cached(), cached()
    monkeypatch.setattr(app, "_whisper_model", whisper)
    monkeypatch.setitem(sys.modules, "diarization", SimpleNamespace(_encoder=speaker))
    monkeypatch.setitem(sys.modules, "faster_whisper.vad", SimpleNamespace(get_vad_model=vad))
    for cache in (whisper, speaker, vad):
        cache()
    return (whisper, speaker, vad), references


def test_completed_audio_models_are_released_before_text_models(monkeypatch):
    caches, references = prime_audio(monkeypatch)
    order = []
    collect = app.gc.collect
    monkeypatch.setattr(app.gc, "collect", lambda: (order.append("collect"), collect())[1])
    monkeypatch.setattr(app, "_set", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_write_exports", lambda *args, **kwargs: order.append("save"))

    def speakers(audio, source, **kwargs):
        assert all(cache.cache_info().currsize == 1 for cache in caches)
        order.append("speakers")
        return {"segments": source, "warnings": [], "provenance": {"backend": "synthetic"}}

    def translate(source, target, **kwargs):
        assert all(cache.cache_info().currsize == 0 for cache in caches)
        assert all(reference() is None for reference in references)
        order.append("translation")
        return deepcopy(source)

    def summary(source, **kwargs):
        order.append("summary")
        return {"summary": "Test", "key_points": [], "chapters": []}

    monkeypatch.setattr(app, "assign_speakers", speakers)
    monkeypatch.setattr(app, "translate_segments", translate)
    monkeypatch.setattr(app, "summarize_segments", summary)
    source = segments()
    before = deepcopy(source)
    app._enhance_and_save("test", source, "en", "local_audio_ai", Path("owned.wav"), True, "el", True)
    assert order == ["speakers", "collect", "translation", "summary", "save"]
    assert source == before
    caches[0]()  # A later audio job can safely reload the cleared cache.
    assert caches[0].cache_info().currsize == 1


@pytest.mark.parametrize("target", ["none", "en"])
def test_jobs_without_text_inference_retain_audio_cache_reuse(monkeypatch, target):
    caches, _ = prime_audio(monkeypatch)
    monkeypatch.setattr(app, "_set", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_write_exports", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.gc, "collect", lambda: pytest.fail("Unexpected collection"))
    app._enhance_and_save("test", segments(), "en", "local_audio_ai", None, False, target, False)
    assert all(cache.cache_info().currsize == 1 for cache in caches)
    assert caches[0]() is caches[0]()


def test_cleanup_does_not_import_missing_optional_models(monkeypatch):
    monkeypatch.setattr(app, "_whisper_model", lru_cache(maxsize=1)(lambda: None))
    monkeypatch.delitem(sys.modules, "diarization", raising=False)
    monkeypatch.delitem(sys.modules, "faster_whisper.vad", raising=False)
    monkeypatch.setattr(app.gc, "collect", lambda: pytest.fail("Nothing was released"))
    app._release_audio_models()
    assert "diarization" not in sys.modules and "faster_whisper.vad" not in sys.modules


def test_translation_unloads_once_after_all_fragments_and_pins_exact_model(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")
    events = []

    def transport(path, payload, timeout):
        events.append(deepcopy(payload))
        if ai.is_ollama_control_request(payload):
            assert timeout == 5
            return {"done": True, "done_reason": "unload"}
        monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "other-model:later")
        return {"done": True, "message": {"content": "Μετάφραση."}}

    monkeypatch.setattr(ai, "local_ollama_json", transport)
    output = ai.translate_segments(segments(), "el", "en")
    assert len(output) == 2
    assert [ai.is_ollama_control_request(item) for item in events] == [False, False, True]
    assert {item["model"] for item in events} == {"translategemma:4b"}
    assert ai._OLLAMA_PHASE.get() is None


def test_summary_unloads_once_after_the_entire_operation(monkeypatch):
    events = []

    def transport(path, payload, timeout):
        control = ai.is_ollama_control_request(payload)
        events.append(control)
        if control:
            return {"done": True, "done_reason": "unload"}
        system = payload["messages"][0]["content"]
        if "key_points" in system:
            value = {"summary": "A synthetic result.", "key_points": ["A point"], "chapter_title": "Topic"}
        else:
            value = {"notes": "Synthetic factual notes.", "chapter_title": "Topic"}
        return {"done": True, "message": {"content": json.dumps(value)}}

    monkeypatch.setattr(ai, "local_ollama_json", transport)
    source = [{"start": i, "end": i + 1, "text": "An ordinary source sentence. " * 140} for i in range(3)]
    result = ai.summarize_segments(source)
    assert result["summary"] and len(events) > 2
    assert events[-1] is True and not any(events[:-1])


@pytest.mark.parametrize("failure", [TimeoutError("inference timed out"), ValueError("malformed response"), KeyboardInterrupt()])
def test_failed_requests_still_attempt_one_bounded_cleanup(monkeypatch, failure):
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")
    calls = []

    def transport(path, payload, timeout):
        calls.append((deepcopy(payload), timeout))
        if ai.is_ollama_control_request(payload):
            raise TimeoutError("cleanup also timed out")
        raise failure

    monkeypatch.setattr(ai, "local_ollama_json", transport)
    before = segments()
    expected = KeyboardInterrupt if isinstance(failure, KeyboardInterrupt) else ai.EnhancementError
    with pytest.raises(expected) as caught:
        ai.translate_segments(before, "el", "en")
    assert caught.value is failure or caught.value.__cause__ is failure
    assert len(calls) == 2 and calls[-1][1] == 5
    assert ai.is_ollama_control_request(calls[-1][0]) and before == segments()
    assert ai._OLLAMA_PHASE.get() is None


def test_cleanup_failure_cannot_discard_completed_translation(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")

    def transport(path, payload, timeout):
        if ai.is_ollama_control_request(payload):
            raise OSError("cleanup unavailable")
        return {"done": True, "message": {"content": "Μετάφραση."}}

    monkeypatch.setattr(ai, "local_ollama_json", transport)
    assert ai.translate_segments(segments(), "el", "en")[0]["text"] == "Μετάφραση."


def test_shared_daemon_retention_opt_out_preserves_inference(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_RETAIN_MODELS", "1")
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")
    calls = []

    def transport(path, payload, timeout):
        calls.append(payload)
        return {"done": True, "message": {"content": "Μετάφραση."}}

    monkeypatch.setattr(ai, "local_ollama_json", transport)
    assert ai.translate_segments(segments(), "el", "en")
    assert len(calls) == 2 and not any(ai.is_ollama_control_request(item) for item in calls)


def test_no_op_and_native_translation_do_not_unload_unrelated_models(monkeypatch):
    monkeypatch.setattr(ai, "local_ollama_json", lambda *args, **kwargs: pytest.fail("Unexpected model request"))
    assert ai.translate_segments(segments(), "en", "en") == segments()
    with pytest.raises(ai.EnhancementError):
        ai.summarize_segments([])
    import marian_translation
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_BACKEND", "marian")
    native_result = [{**item, "text": "Μια συνθετική μετάφραση."} for item in segments()]
    monkeypatch.setattr(marian_translation, "translate_segments", lambda source, *_: native_result)
    assert ai.translate_segments(segments(), "el", "en") == native_result


def load_helper(filename):
    spec = importlib.util.spec_from_file_location("lifecycle_" + filename, Path(__file__).with_name(filename + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_translation_observer_preserves_control_events_separately(monkeypatch):
    quality = load_helper("evaluate_translation_quality")
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")
    monkeypatch.setattr(ai, "local_ollama_json", lambda path, payload, timeout: (
        {"done": True, "done_reason": "unload"} if ai.is_ollama_control_request(payload) else
        {"done": True, "message": {"content": "Μετάφραση."}}))
    records = []
    with quality.observe_requests(records, lambda: None):
        ai.translate_segments(segments(), "el", "en")
    assert [item["kind"] for item in records] == ["inference", "inference", "control"]
    assert json.loads(records[-1]["response_json"])["done_reason"] == "unload"


def test_summary_coverage_distinguishes_same_time_segments_and_exact_fragments():
    evaluation = load_helper("evaluate_summary_quality")
    case = {"segments": [{"start": 1.5, "text": "First text. "}, {"start": 1.5, "text": "Second text."}]}
    chunks = [[{"source_index": 0, "start": 1.5, "text": "First "}],
              [{"source_index": 0, "start": 1.5, "text": "text. "},
               {"source_index": 1, "start": 1.5, "text": "Second text."}]]
    assert evaluation.source_coverage(case, chunks)
    bad = deepcopy(chunks)
    bad[1][1]["source_index"] = 0
    assert not evaluation.source_coverage(case, bad)
    bad = deepcopy(chunks)
    bad[1][0]["text"] = "text."
    assert not evaluation.source_coverage(case, bad)
    bad = deepcopy(chunks)
    bad[0][0]["source_index"] = -1
    assert not evaluation.source_coverage(case, bad)


def test_summary_observer_and_fresh_reload_exclude_control_from_inference_counts(monkeypatch, tmp_path):
    evaluation = load_helper("evaluate_summary_quality")
    case = {"id": "owned-case", "source_language": "en", "segments": segments()}
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({"schema_version": 1, "frozen": True, "corpus_version": "unit", "cases": [case]}))

    def transport(path, payload=None, timeout=1.5):
        if path == "/api/tags":
            return {"models": [{"name": "qwen3:4b", "digest": "a" * 64}]}
        if path == "/api/version":
            return {"version": "synthetic-runtime"}
        if ai.is_ollama_control_request(payload):
            return {"done": True, "done_reason": "unload"}
        system = payload["messages"][0]["content"]
        value = ({"notes": "Factual notes.", "chapter_title": "Topic"} if "key_points" not in system else
                 {"summary": "A synthetic result.", "key_points": ["A point"], "chapter_title": "Topic"})
        return {"done": True, "message": {"content": json.dumps(value)}}

    monkeypatch.setattr(ai, "local_ollama_json", transport)
    output = tmp_path / "report.json"
    assert evaluation.main(["--corpus", str(corpus), "--output", str(output)]) == 0
    case = json.loads(output.read_text())["cases"][0]
    assert case["control_request_count"] == 1
    assert case["inference_request_count"] == len(case["requests"]) - 1
    assert case["requests"][-1]["phase"] == "unload"
    assert case["checks"]["fresh_interpreter_matches"] is True
