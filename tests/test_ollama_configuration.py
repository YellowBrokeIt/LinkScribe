"""CPU configuration must affect the real request and fail before inference."""
import pytest

import enhancements


@pytest.fixture
def smoke_module():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("linkscribe_smoke_models", Path(__file__).with_name("smoke_real_ollama.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("setting,expected", [(None, None), ("", None), ("  ", None),
                                               ("1", 1), (" 4 ", 4), ("32", 32)])
def test_thread_configuration_reaches_actual_model_request(monkeypatch, setting, expected):
    if setting is None:
        monkeypatch.delenv("LINKSCRIBE_OLLAMA_THREADS", raising=False)
    else:
        monkeypatch.setenv("LINKSCRIBE_OLLAMA_THREADS", setting)
    requests = []

    def respond(path, payload, timeout):
        requests.append((path, payload, timeout))
        return {"done": True, "message": {"content": '{"translations":["Hello"]}'}}

    monkeypatch.setattr(enhancements, "local_ollama_json", respond)
    enhancements._ollama({"messages": [{"role": "user", "content": "test"}]})
    assert len(requests) == 1 and requests[0][0] == "/api/chat"
    options = requests[0][1]["options"]
    assert requests[0][1]["format"] == "json"
    assert options.get("num_thread") == expected
    if expected is None:
        assert "num_thread" not in options
    assert {k: options[k] for k in ("temperature", "num_ctx", "num_predict")} == {
        "temperature": 0, "num_ctx": 8192, "num_predict": 2048}


@pytest.mark.parametrize("setting", ["0", "-1", "33", "4.5", "four"])
def test_invalid_thread_configuration_fails_before_network(monkeypatch, setting):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_THREADS", setting)

    def unexpected(*args, **kwargs):
        pytest.fail("An invalid setting must not reach the model")

    monkeypatch.setattr(enhancements, "local_ollama_json", unexpected)
    with pytest.raises(enhancements.EnhancementError, match="LINKSCRIBE_OLLAMA_THREADS"):
        enhancements._ollama({"messages": []})


@pytest.mark.parametrize("texts", [["Hello"], ["Hello"] * 12, ["Hello"] * 13,
                                  ["A long transcript with natural word boundaries. " * 90]])
def test_translation_schema_matches_each_real_fragment_batch(monkeypatch, texts):
    import copy
    import json

    seen = []

    def respond(path, payload, timeout):
        items = json.loads(payload["messages"][-1]["content"].split("JSON input: ", 1)[1])
        schema = payload["format"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        assert schema["required"] == ["translations"]
        assert schema["properties"]["translations"] == {
            "type": "array", "items": {"type": "string"},
            "minItems": len(items), "maxItems": len(items)}
        seen.append(len(items))
        return {"done": True, "message": {"content": json.dumps({
            "translations": [item["text"] for item in items]})}}

    monkeypatch.setattr(enhancements, "local_ollama_json", respond)
    source = [{"start": i, "end": i + 1, "text": text, "speaker": "Speaker 1"}
              for i, text in enumerate(texts)]
    original = copy.deepcopy(source)
    result = enhancements.translate_segments(source, "el")
    assert source == original and len(result) == len(source)
    assert seen and sum(seen) >= len(texts)
    if len(texts) > 12 or len(texts[0]) > enhancements.MAX_TRANSLATION_INPUT_BYTES:
        assert len(seen) > 1


def test_smoke_identifies_both_task_models_with_digests(monkeypatch, smoke_module):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")
    monkeypatch.setattr(enhancements, "local_ollama_json", lambda *_args, **_kwargs: {
        "models": [{"name": "qwen3:4b", "digest": "a" * 64},
                   {"name": "translategemma:4b", "digest": "b" * 64}]})
    identities = smoke_module.model_identities()
    assert identities["summary"]["configured_model"] == "qwen3:4b"
    assert identities["summary"]["model"]["digest"] == "a" * 64
    assert identities["translation"]["configured_model"] == "translategemma:4b"
    assert identities["translation"]["model"]["digest"] == "b" * 64
    assert identities["translation"]["profile"] == "translategemma"


def test_smoke_refuses_to_claim_an_unidentified_translation_model(monkeypatch, smoke_module):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")
    monkeypatch.setattr(enhancements, "local_ollama_json", lambda *_args, **_kwargs: {
        "models": [{"name": "qwen3:4b", "digest": "a" * 64}]})
    with pytest.raises(AssertionError, match="translation model translategemma:4b"):
        smoke_module.model_identities()


@pytest.mark.parametrize("wrong_translation_model", [False, True])
def test_smoke_records_actual_task_routing_and_restores_wrappers(monkeypatch, smoke_module, wrong_translation_model):
    expected = {"translation": {"configured_model": "translategemma:4b"},
                "summary": {"configured_model": "qwen3:4b"}}
    network_calls = []

    def transport(path, payload=None, timeout=1.5):
        network_calls.append(payload)
        return {"done": True}

    def translate(*_args, **_kwargs):
        return enhancements.local_ollama_json("/api/chat", {
            "model": "qwen3:4b" if wrong_translation_model else "translategemma:4b",
            "options": {"num_thread": 4}, "messages": [{"role": "user", "content": "source"}]})

    def summarize(*_args, **_kwargs):
        return enhancements.local_ollama_json("/api/chat", {
            "model": "qwen3:4b", "options": {"num_thread": 4}, "format": "json", "think": False,
            "messages": [{"role": "user", "content": "summary source"}]})

    monkeypatch.setattr(enhancements, "local_ollama_json", transport)
    monkeypatch.setattr(smoke_module.app, "translate_segments", translate)
    monkeypatch.setattr(smoke_module.app, "summarize_segments", summarize)
    if wrong_translation_model:
        with pytest.raises(AssertionError):
            with smoke_module.observe_task_models(expected):
                smoke_module.app.translate_segments([], "el", source_language="en")
        assert network_calls == []
    else:
        with smoke_module.observe_task_models(expected) as actual:
            smoke_module.app.translate_segments([], "el", source_language="en")
            smoke_module.app.summarize_segments([])
        assert [entry["task"] for entry in actual] == ["translation", "summary"]
        assert [entry["model"] for entry in actual] == ["translategemma:4b", "qwen3:4b"]
        assert all(entry["options"]["num_thread"] == 4 for entry in actual)
        assert actual[0]["format"] is None and actual[1]["format"] == "json"
        assert len(network_calls) == 2
    assert enhancements.local_ollama_json is transport
    assert smoke_module.app.translate_segments is translate
    assert smoke_module.app.summarize_segments is summarize
