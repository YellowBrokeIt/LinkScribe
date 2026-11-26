"""CPU configuration must affect the real request and fail before inference."""
import pytest

import enhancements


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
