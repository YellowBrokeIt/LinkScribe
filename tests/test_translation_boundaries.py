"""Deterministic regression tests; model replies are synthetic, not quality QA."""
from __future__ import annotations

import copy
import json

import pytest

import enhancements as ai


@pytest.fixture(autouse=True)
def clean_translation_settings(monkeypatch):
    for name in ("LINKSCRIBE_TRANSLATION_MODEL", "LINKSCRIBE_TRANSLATION_BACKEND",
                 "LINKSCRIBE_OLLAMA_MODEL", "LINKSCRIBE_OLLAMA_URL",
                 "LINKSCRIBE_OLLAMA_THREADS", "LINKSCRIBE_OLLAMA_RETAIN_MODELS"):
        monkeypatch.delenv(name, raising=False)


def segment(text, index=0):
    return {"start": index + 0.125, "end": index + 0.875, "text": text,
            "speaker": f"Speaker {index + 1}", "extra": {"keep": True}}


def capture_echo(monkeypatch):
    calls = []

    def model(payload):
        user = payload["messages"][1]["content"]
        encoded = user.split("JSON input: ", 1)[1]
        items = json.loads(encoded)
        assert len(encoded.encode("utf-8")) <= 1000
        assert len(items) <= ai.MAX_TRANSLATION_BATCH_ITEMS
        assert [item["id"] for item in items] == list(range(len(items)))
        assert all(set(item) == {"id", "text"} for item in items)
        calls.append(items)
        return {"translations": [item["text"] for item in items]}

    monkeypatch.setattr(ai, "_ollama", model)
    return calls


@pytest.mark.parametrize("max_input_bytes", [1000, 1600])
@pytest.mark.parametrize("text", [
    "", "Hello", "a" * 2800, "a" * 20000,
    "Bitcoin is not a company. " * 400,
    "Το Bitcoin δεν είναι εταιρεία. " * 400,
    'He said "hello". C:\\clips\\video\n' * 300,
    "\t\r\n" * 2000,
    "😀₿🚀" * 2500,
    "α\u0301" * 4000,
    "\x01" * 1000,
])
def test_fragments_are_lossless_and_bounded(text, max_input_bytes):
    parts = list(ai._translation_fragments(text, max_input_bytes))
    assert "".join(parts) == text
    assert all(parts)
    assert all(len(ai._translation_json([part]).encode("utf-8"))
               <= max_input_bytes for part in parts)


@pytest.mark.parametrize("unit", ["a", "α", "🧪", '"', "\\", "\x01"])
@pytest.mark.parametrize("extra_byte", [0, 1])
def test_generic_wire_requests_respect_inclusive_1000_source_json_bytes(
        monkeypatch, unit, extra_byte):
    # Account independently for the source JSON's ID/key/escape overhead.
    # The outer HTTP JSON and instruction prefix intentionally have other sizes.
    def encode(text):
        return json.dumps([{"id": 0, "text": text}], ensure_ascii=False)

    overhead = len(encode("").encode("utf-8"))
    width = len(encode(unit).encode("utf-8")) - overhead
    count, remainder = divmod(1000 - overhead, width)
    text = unit * count + "a" * (remainder + extra_byte)
    assert len(encode(text).encode("utf-8")) == 1000 + extra_byte
    source = [segment(text)]
    before = copy.deepcopy(source)
    sent = []
    controls = []

    def respond(path, payload, timeout):
        if ai.is_ollama_control_request(payload):
            controls.append(payload)
            return {"done": True, "done_reason": "unload"}
        assert path == "/api/chat" and timeout == 240
        assert payload["options"]["num_predict"] == 2048
        encoded = payload["messages"][1]["content"].split("JSON input: ", 1)[1]
        assert len(encoded.encode("utf-8")) <= 1000
        items = json.loads(encoded)
        sent.append(items)
        return {"done": True, "message": {"content": json.dumps({
            "translations": ["synthetic translation" for _ in items]})}}

    monkeypatch.setattr(ai, "local_ollama_json", respond)
    result = ai.translate_segments(source, "el", "en")
    assert len(sent) == 1 + extra_byte and len(controls) == 1
    assert "".join(item["text"] for batch in sent for item in batch) == text
    assert source == before and len(result) == 1
    assert {k: v for k, v in result[0].items() if k != "text"} == {
        k: v for k, v in before[0].items() if k != "text"}


@pytest.mark.parametrize("model,separator", [
    ("translategemma:4b", "\n\n\n"), ("linkscribe-hy-mt3:1.8b", "\n"),
])
def test_dedicated_adapters_keep_the_original_1600_byte_fragment_budget(
        monkeypatch, model, separator):
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", model)
    overhead = len(json.dumps([{"id": 0, "text": ""}]).encode("utf-8"))
    text = "a" * (1600 - overhead) + "b"
    parts = list(ai._translation_fragments(text))
    assert len(parts) == 2 and len(ai._translation_json([parts[0]]).encode("utf-8")) == 1600
    sent = []

    def respond(path, payload, timeout):
        if ai.is_ollama_control_request(payload):
            return {"done": True, "done_reason": "unload"}
        assert "format" not in payload and len(payload["messages"]) == 1
        assert timeout == 240 and payload["options"]["num_predict"] == 2048
        sent.append(payload["messages"][0]["content"].split(separator, 1)[1])
        return {"done": True, "message": {"content": "synthetic translation"}}

    monkeypatch.setattr(ai, "local_ollama_json", respond)
    source = [segment(text)]
    before = copy.deepcopy(source)
    result = ai.translate_segments(source, "el", "en")
    assert sent == parts and "".join(sent) == text
    assert source == before
    assert result == [{**before[0], "text": "synthetic translation synthetic translation"}]


@pytest.mark.parametrize("target", ["el", "en"])
@pytest.mark.parametrize("text", [
    "Bitcoin has no CEO. " * 600,
    "Η απομαγνητοφώνηση έχει χρονικές σημάνσεις. " * 400,
    'Quotes " and backslashes \\ and newlines\n' * 350,
    "😀" * 8000,
])
def test_long_segments_keep_all_content_and_original_metadata(monkeypatch, target, text):
    calls = capture_echo(monkeypatch)
    source = [segment(text)]
    before = copy.deepcopy(source)
    translated = ai.translate_segments(source, target)
    assert len(calls) > 1
    assert "".join(item["text"] for batch in calls for item in batch) == text
    assert len(translated) == 1
    assert source == before
    assert translated[0] is not source[0]
    assert {key: value for key, value in translated[0].items() if key != "text"} == {
        key: value for key, value in source[0].items() if key != "text"}
    assert translated[0]["text"] == " ".join(
        item["text"].strip() for batch in calls for item in batch)


def test_batch_item_limit_and_order(monkeypatch):
    calls = capture_echo(monkeypatch)
    source = [segment(f"item {i}", i) for i in range(25)]
    assert ai.translate_segments(source, "el") == source
    assert [len(batch) for batch in calls] == [12, 12, 1]


def test_serialized_budget_includes_escaping_and_id_overhead(monkeypatch):
    calls = capture_echo(monkeypatch)
    source = [segment('"\\' * 100, i) for i in range(20)]
    assert ai.translate_segments(source, "en") == source
    assert len(calls) > 2
    assert sum(map(len, calls)) == len(source)


def test_long_segment_between_short_segments_does_not_shift_timestamps(monkeypatch):
    capture_echo(monkeypatch)
    source = [segment("first", 0), segment("long text " * 1500, 1), segment("last", 2)]
    result = ai.translate_segments(source, "en")
    assert len(result) == 3
    assert result[0] == source[0] and result[-1] == source[-1]
    assert result[1]["start"] == source[1]["start"]
    assert result[1]["speaker"] == source[1]["speaker"]


@pytest.mark.parametrize("texts", [[], [""], [" \t\n"], [" " * 20000, ""]])
def test_empty_content_never_calls_model(monkeypatch, texts):
    calls = capture_echo(monkeypatch)
    source = [segment(text, i) for i, text in enumerate(texts)]
    assert ai.translate_segments(source, "en") == source
    assert calls == []


def test_empty_segments_between_content_preserve_count(monkeypatch):
    calls = capture_echo(monkeypatch)
    source = [segment(text, i) for i, text in enumerate(["one", "", "\n", "two"])]
    assert ai.translate_segments(source, "en") == source
    assert [item["text"] for batch in calls for item in batch] == ["one", "two"]


@pytest.mark.parametrize("bad", [None, "text", {}, [None], [{}],
                                 [{"text": 3}], [{"text": False}], [{"text": "\ud800"}]])
def test_invalid_source_fails_before_inference(monkeypatch, bad):
    calls = capture_echo(monkeypatch)
    with pytest.raises(ai.EnhancementError):
        ai.translate_segments(bad, "en")
    assert not calls


def test_invalid_later_source_does_not_trigger_earlier_requests(monkeypatch):
    calls = capture_echo(monkeypatch)
    source = [segment("valid" * 5000), {"text": None}]
    with pytest.raises(ai.EnhancementError, match="contain text"):
        ai.translate_segments(source, "el")
    assert not calls


@pytest.mark.parametrize("target", ["de", "", None, [], 1])
def test_invalid_target_has_readable_error(monkeypatch, target):
    calls = capture_echo(monkeypatch)
    with pytest.raises(ai.EnhancementError, match="English or Greek"):
        ai.translate_segments([segment("Hello")], target)
    assert not calls


@pytest.mark.parametrize("response", [
    None, [], {}, {"translations": None}, {"translations": "text"},
    {"translations": []}, {"translations": ["a", "b"]},
    {"translations": [None]}, {"translations": [1]},
    {"translations": [{"text": "hello"}]}, {"translations": [""]},
    {"translations": [" \n\t"]},
])
def test_malformed_translations_do_not_change_original(monkeypatch, response):
    source = [segment("Original")]
    before = copy.deepcopy(source)
    monkeypatch.setattr(ai, "_ollama", lambda _payload: response)
    with pytest.raises(ai.EnhancementError, match="expected number"):
        ai.translate_segments(source, "el")
    assert source == before


@pytest.mark.parametrize("text", ["x" * 16385, "α" * 8193, "\ud800"])
def test_oversized_or_invalid_unicode_output_rejected(monkeypatch, text):
    monkeypatch.setattr(ai, "_ollama", lambda _payload: {"translations": [text]})
    with pytest.raises(ai.EnhancementError, match="oversized|Unicode"):
        ai.translate_segments([segment("Original")], "el")


def test_output_byte_boundary_is_inclusive(monkeypatch):
    text = "α" * (ai.MAX_TRANSLATION_OUTPUT_BYTES // 2)
    monkeypatch.setattr(ai, "_ollama", lambda _payload: {"translations": [text]})
    assert ai.translate_segments([segment("Original")], "el")[0]["text"] == text


def test_later_model_failure_leaves_all_originals_untouched(monkeypatch):
    source = [segment("content " * 1500)]
    before = copy.deepcopy(source)
    calls = []

    def model(payload):
        calls.append(payload)
        if len(calls) > 1:
            raise ai.EnhancementError("synthetic model failure")
        return {"translations": ["first fragment"]}

    monkeypatch.setattr(ai, "_ollama", model)
    with pytest.raises(ai.EnhancementError, match="synthetic model failure"):
        ai.translate_segments(source, "el")
    assert len(calls) == 2
    assert source == before


@pytest.mark.parametrize("content", [
    '{"translations":["first"],"translations":["second"]}',
    '{"notes":{"x":1,"x":2}}',
    '{"summary": NaN}', '{"summary": Infinity}', '{"summary": -Infinity}',
    '[]', 'null', 'true', '42', '"plain text"', '{"unfinished":',
    '[' * 2000 + ']' * 2000,
])
def test_ambiguous_or_non_object_model_json_is_rejected(monkeypatch, content):
    monkeypatch.setattr(ai, "local_ollama_json", lambda *_args, **_kwargs: {
        "done": True, "message": {"content": content}})
    with pytest.raises(ai.EnhancementError, match="invalid JSON"):
        ai._ollama({"messages": []})


@pytest.mark.parametrize("done", [False, None, 0, 1, "true"])
def test_explicit_incomplete_response_rejected(monkeypatch, done):
    monkeypatch.setattr(ai, "local_ollama_json", lambda *_args, **_kwargs: {
        "done": done, "message": {"content": '{"translations":["partial"]}'}})
    with pytest.raises(ai.EnhancementError, match="incomplete"):
        ai._ollama({"messages": []})


def test_complete_json_response_still_supported(monkeypatch):
    expected = {"translations": ["Καλημέρα, Bitcoin!"]}
    monkeypatch.setattr(ai, "local_ollama_json", lambda *_args, **_kwargs: {
        "done": True, "done_reason": "stop", "message": {"content": json.dumps(expected)}})
    assert ai._ollama({"messages": []}) == expected
