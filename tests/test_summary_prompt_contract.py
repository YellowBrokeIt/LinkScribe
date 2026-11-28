"""Prompt filler removal preserves the actual summary protocol, not model quality."""
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path

import pytest

import enhancements


LITERAL_EXAMPLES = ('{"summary":"concise factual summary","key_points":["point"],'
                    '"chapter_title":"short topical title"}; '
                    '{"notes":"concise factual notes","chapter_title":"short topical title"}')


def capture_transport(monkeypatch, respond):
    """Drive the real app request builder with owned, synthetic responses only."""
    calls = []
    spec = importlib.util.spec_from_file_location(
        "summary_prompt_observer", Path(__file__).with_name("evaluate_summary_quality.py"))
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "unit-summary-protocol")
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_THREADS", "4")
    monkeypatch.delenv("LINKSCRIBE_OLLAMA_RETAIN_MODELS", raising=False)

    def transport(path, payload, *, timeout):
        assert path == "/api/chat"
        body = deepcopy(payload)
        if not body["messages"]:
            assert timeout == 5
            assert body == {"model": "unit-summary-protocol", "messages": [],
                            "stream": False, "keep_alive": 0}
            assert observer.summary_request_phase(body, control=True) == "unload"
            calls.append({"stage": "unload", "body": body})
            return {"done": True, "done_reason": "unload"}
        assert timeout == 240
        assert body["model"] == "unit-summary-protocol"
        assert body["stream"] is False and body["think"] is False
        assert body["options"] == {"temperature": 0, "num_ctx": 8192,
                                   "num_predict": 2048, "num_thread": 4}
        assert [message["role"] for message in body["messages"]] == ["system", "user"]
        assert len(body["messages"][1]["content"].encode("utf-8")) <= 3200
        system = body["messages"][0]["content"]
        if isinstance(body["format"], dict):
            stage = "direct" if "chapter_title" in body["format"]["properties"] else "final"
        elif system.startswith("Summarize a transcript excerpt factually."):
            stage = "notes"
        else:
            assert system.startswith("Condense these chronological notes,")
            stage = "reduce"
        assert observer.summary_request_phase(body, control=False) == {
            "direct": "direct", "notes": "map", "reduce": "reduce", "final": "synthesis"}[stage]
        calls.append({"stage": stage, "body": body})
        result = respond(stage, body)
        return {"done": True, "done_reason": "stop",
                "message": {"content": json.dumps(result, ensure_ascii=False)}}

    monkeypatch.setattr(enhancements, "local_ollama_json", transport)
    return calls


def assert_result_schema(schema, *, direct):
    properties = {"summary": {"type": "string", "minLength": 1},
                  "key_points": {"type": "array", "minItems": 1, "maxItems": 8,
                                 "items": {"type": "string", "minLength": 1}}}
    if direct:
        properties["chapter_title"] = {"type": "string", "minLength": 1}
    assert schema == {"type": "object", "properties": properties,
                      "required": list(properties), "additionalProperties": False}


@pytest.mark.parametrize("language,label", [("en", "English"), ("el", "Greek")])
def test_direct_schema_only_prompt_preserves_literal_source_and_transport(monkeypatch, language, label):
    source = [{"start": 0.5, "end": 4, "text": "Quoted source data: " + LITERAL_EXAMPLES,
               "speaker": "Speaker 1"},
              {"start": 4, "end": 8, "text": "Αυτές είναι κυριολεκτικές φράσεις.",
               "speaker": "Speaker 2"}]
    before = deepcopy(source)
    answer = {"summary": 'The source contains the phrase "concise factual summary".',
              "key_points": ['The literal word is "point".'], "chapter_title": "Quoted wording"}
    calls = capture_transport(monkeypatch, lambda stage, body: deepcopy(answer))
    result = enhancements.summarize_segments(source, language)
    assert [call["stage"] for call in calls] == ["direct", "unload"]
    body = calls[0]["body"]
    assert_result_schema(body["format"], direct=True)
    system, user = [message["content"] for message in body["messages"]]
    assert system.endswith("Return only JSON matching the supplied schema.")
    assert "JSON only:" not in system and "at most 8 concise key points" in system
    assert f"in {label}, the known source language" in system
    assert user == "[0.5s] " + source[0]["text"] + "\n[4.0s] " + source[1]["text"]
    assert LITERAL_EXAMPLES in user
    assert result == {"summary": answer["summary"], "key_points": answer["key_points"],
                      "chapters": [{"start": 0.5, "title": "Quoted wording"}]}
    assert source == before


def test_notes_reduction_and_final_keep_complete_inputs_coordinates_and_unloads(monkeypatch):
    source = [{"start": index * 10 + 0.25, "end": index * 10 + 5.25,
               "text": f"SOURCE_{index} " + "x" * 2050 + " " + LITERAL_EXAMPLES,
               "speaker": "Speaker 3"} for index in range(4)]
    before = deepcopy(source)
    notes, reduced = [], []

    def respond(stage, body):
        if stage == "notes":
            note = f"NOTE_{len(notes)} " + "α" * 1100
            notes.append(note)
            return {"notes": note, "chapter_title": f"Section {len(notes)}"}
        if stage == "reduce":
            user = body["messages"][1]["content"]
            assert user in notes
            shortened = user.split()[0]
            reduced.append(shortened)
            return {"notes": shortened}
        assert stage == "final"
        return {"summary": "All supplied note markers are represented.",
                "key_points": ["The response is a protocol fixture."]}

    calls = capture_transport(monkeypatch, respond)
    result = enhancements.summarize_segments(source, "el")
    maps = [call["body"] for call in calls if call["stage"] == "notes"]
    reductions = [call["body"] for call in calls if call["stage"] == "reduce"]
    finals = [call["body"] for call in calls if call["stage"] == "final"]
    assert len(maps) == len(reductions) == 4 and len(finals) == 1
    assert [body["messages"][1]["content"] for body in maps] == [
        f"[{segment['start']:.1f}s] {segment['text']}" for segment in source]
    assert all(LITERAL_EXAMPLES in body["messages"][1]["content"] for body in maps)
    assert all(body["format"] == "json" and body["messages"][0]["content"].endswith(
        "Return only JSON with the string fields `notes` and `chapter_title`.") for body in maps)
    assert [body["messages"][1]["content"] for body in reductions] == notes
    assert finals[0]["messages"][1]["content"] == "\n\n".join(reduced)
    assert reduced == [f"NOTE_{index}" for index in range(4)]
    assert_result_schema(finals[0]["format"], direct=False)
    assert finals[0]["messages"][0]["content"].endswith("Return only JSON matching the supplied schema.")
    inference = [call for call in calls if call["stage"] != "unload"]
    assert all("in Greek, the known source language" in call["body"]["messages"][0]["content"]
               for call in inference)
    assert [chapter["start"] for chapter in result["chapters"]] == [segment["start"] for segment in source]
    assert source == before
    assert calls[-1]["stage"] == "unload"
    assert sum(call["stage"] == "unload" for call in calls) == math.ceil(len(inference) / 2)
    resident_responses = 0
    for call in calls:
        resident_responses = 0 if call["stage"] == "unload" else resident_responses + 1
        assert resident_responses <= 2


@pytest.mark.parametrize("failing_stage", ["direct", "notes", "final"])
def test_invalid_content_is_rejected_and_final_cleanup_still_occurs(monkeypatch, failing_stage):
    def respond(stage, body):
        if stage == failing_stage:
            return {"unexpected": "Invalid synthetic response"}
        assert stage == "notes"
        return {"notes": "A bounded source note.", "chapter_title": "Source section"}

    calls = capture_transport(monkeypatch, respond)
    source = ([{"start": 0.5, "text": "Short complete source."}] if failing_stage == "direct" else
              [{"start": index * 10 + 0.5, "text": "Complete source. " * 140} for index in range(2)])
    before = deepcopy(source)
    with pytest.raises(enhancements.EnhancementError, match="valid (excerpt summary|summary)"):
        enhancements.summarize_segments(source, "en")
    assert any(call["stage"] == failing_stage for call in calls)
    assert calls[-1]["stage"] == "unload"
    assert source == before
