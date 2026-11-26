"""Source-coverage and bounded-request regressions; no semantic model claims."""
from copy import deepcopy
import json
import re

import pytest

import enhancements


def test_short_source_has_one_direct_call_with_known_language(monkeypatch):
    source = [{"start": 0.5, "end": 4, "text": "Η Άνθη περιμένει ακόμη.", "speaker": "Speaker 1"},
              {"start": 4, "end": 7, "text": "Δεν έχει εγκρίνει την αλλαγή.", "speaker": "Speaker 2"}]
    original = deepcopy(source)
    calls = []

    def respond(payload):
        calls.append(deepcopy(payload))
        return {"summary": "Η αλλαγή δεν έχει εγκριθεί.", "key_points": ["Η Άνθη περιμένει."],
                "chapter_title": "Εκκρεμής αλλαγή"}

    monkeypatch.setattr(enhancements, "_ollama", respond)
    result = enhancements.summarize_segments(source, source_language="el-GR")
    assert len(calls) == 1
    system, user = [item["content"] for item in calls[0]["messages"]]
    assert "directly from this transcript" in system and "in Greek" in system
    assert "key_points" in system and "chapter_title" in system
    assert user == "[0.5s] Η Άνθη περιμένει ακόμη.\n[4.0s] Δεν έχει εγκρίνει την αλλαγή."
    assert result["chapters"] == [{"start": 0.5, "title": "Εκκρεμής αλλαγή"}]
    assert source == original


def test_oversized_unicode_segment_reaches_all_maps_without_new_times(monkeypatch):
    text = "\n\n".join(f"Ενότητα {index}: Ένα νέο σημείο 🙂 με διαφορετική λέξη {index}. " * 5
                        for index in range(24)) + "\nΤελική απόφαση: διατήρηση όλου του κειμένου.\n"
    source = [{"start": 12.25, "end": 430.5, "text": text, "speaker": "Speaker 4"}]
    original = deepcopy(source)
    chunks = enhancements._summary_source_chunks(source)
    assert len(chunks) > 1
    assert "".join(part["text"] for chunk in chunks for part in chunk) == text
    assert {part["source_index"] for chunk in chunks for part in chunk} == {0}
    assert all(part["start"] == 12.25 for chunk in chunks for part in chunk)
    calls = []

    def respond(payload):
        calls.append(deepcopy(payload))
        system, user = [item["content"] for item in payload["messages"]]
        if "chapter_title" in system:
            return {"notes": f"Τμήμα {len(calls)} διατηρήθηκε.", "chapter_title": "Ενότητα"}
        return {"summary": "Διατηρήθηκαν τα τμήματα.", "key_points": ["Η τελική απόφαση παραμένει."]}

    monkeypatch.setattr(enhancements, "_ollama", respond)
    result = enhancements.summarize_segments(source, source_language="el")
    maps = [call for call in calls if "chapter_title" in call["messages"][0]["content"]]
    assert [call["messages"][1]["content"] for call in maps] == [enhancements._summary_excerpt(c) for c in chunks]
    assert all(len(call["messages"][1]["content"].encode("utf-8")) <= enhancements.MAX_SUMMARY_INPUT_BYTES
               for call in calls)
    assert len(result["chapters"]) == 1 and result["chapters"][0]["start"] == 12.25
    assert source == original


def test_equal_timestamps_do_not_merge_source_identity():
    source = [{"start": 1, "end": 2, "text": " α " * 1300},
              {"start": 1, "end": 3, "text": "\nβ\n" * 1200}]
    chunks = enhancements._summary_source_chunks(source)
    for index, segment in enumerate(source):
        assert "".join(part["text"] for chunk in chunks for part in chunk
                       if part["source_index"] == index) == segment["text"]
    assert all(len(enhancements._summary_excerpt(chunk).encode("utf-8")) <= enhancements.MAX_SUMMARY_INPUT_BYTES
               for chunk in chunks)


def test_greek_notes_are_reduced_within_byte_budget_without_dropping_later_notes(monkeypatch):
    maps, reductions, all_calls = [], [], []

    def respond(payload):
        system, user = [item["content"] for item in payload["messages"]]
        all_calls.append(payload)
        if "chapter_title" in system:
            note = f"MARKER_{len(maps)} " + "α" * 1050
            maps.append(user)
            return {"notes": note, "chapter_title": "Μέρος"}
        if "Condense" in system:
            reductions.append(user)
            return {"notes": " ".join(re.findall(r"MARKER_\d+", user))}
        return {"summary": user, "key_points": ["Όλα τα μέρη."]}

    monkeypatch.setattr(enhancements, "_ollama", respond)
    source = [{"start": index * 10, "end": index * 10 + 5, "text": f"SOURCE_{index} " + "x" * 2100}
              for index in range(4)]
    result = enhancements.summarize_segments(source, source_language="el")
    assert len(maps) == 4 and reductions
    assert all(f"MARKER_{index}" in result["summary"] for index in range(4))
    assert all(len(call["messages"][1]["content"].encode("utf-8")) <= enhancements.MAX_SUMMARY_INPUT_BYTES
               for call in all_calls)
    assert all("in Greek" in call["messages"][0]["content"] for call in all_calls)
    assert [chapter["start"] for chapter in result["chapters"]] == [0, 10, 20, 30]


@pytest.mark.parametrize("start", [-0.1, -1, float("nan"), float("inf"), True, "0"])
def test_invalid_source_time_is_rejected_before_any_model_call(monkeypatch, start):
    calls = []
    monkeypatch.setattr(enhancements, "_ollama", lambda payload: calls.append(payload))
    with pytest.raises(enhancements.EnhancementError, match="source timestamps"):
        enhancements.summarize_segments([{"start": start, "text": "Source text"}])
    assert calls == []


def test_all_sources_are_validated_before_first_request(monkeypatch):
    calls = []
    monkeypatch.setattr(enhancements, "_ollama", lambda payload: calls.append(payload))
    with pytest.raises(enhancements.EnhancementError, match="invalid Unicode"):
        enhancements.summarize_segments([{"start": 0, "text": "Valid text"},
                                        {"start": 1, "text": "\ud800"}])
    assert calls == []


def test_oversized_unicode_notes_are_not_silently_clipped(monkeypatch):
    monkeypatch.setattr(enhancements, "_ollama", lambda payload: {
        "notes": "α" * (enhancements.MAX_SUMMARY_INPUT_BYTES // 2 + 1),
        "chapter_title": "Ενότητα"})
    with pytest.raises(enhancements.EnhancementError, match="oversized summary notes"):
        enhancements.summarize_segments([{"start": 0, "end": 10, "text": "x" * 5000}], "el")


def test_overlong_final_point_is_rejected_instead_of_losing_its_ending(monkeypatch):
    monkeypatch.setattr(enhancements, "_ollama", lambda payload: {
        "summary": "A concise result.", "key_points": ["x" * 901], "chapter_title": "Section"})
    with pytest.raises(enhancements.EnhancementError, match="valid summary"):
        enhancements.summarize_segments([{"start": 0, "text": "Short source."}], "en")


def test_valid_large_contractions_can_fit_after_multiple_bounded_reductions(monkeypatch):
    requests = []
    source_calls = 0
    reduction_sizes = []

    def respond(payload):
        nonlocal source_calls
        system, user = [item["content"] for item in payload["messages"]]
        requests.append(payload)
        if "chapter_title" in system:
            note = f"MARKER_{source_calls} " + "x" * 2000
            source_calls += 1
            return {"notes": note, "chapter_title": "Section"}
        if "Condense" in system:
            markers = " ".join(re.findall(r"MARKER_\d+", user))
            # A useful contraction above the former arbitrary 1200-byte limit.
            note = markers + " " + "x" * (1500 - len(markers) - 1)
            reduction_sizes.append(len(note.encode("utf-8")))
            return {"notes": note}
        return {"summary": user, "key_points": ["All original note markers remain."]}

    monkeypatch.setattr(enhancements, "_ollama", respond)
    source = [{"start": index * 10, "end": index * 10 + 5, "text": f"SOURCE_{index} " + "x" * 2100}
              for index in range(4)]
    result = enhancements.summarize_segments(source, "en")
    assert reduction_sizes and all(size == 1500 for size in reduction_sizes)
    assert len(reduction_sizes) > 4  # More than one reduction round was needed.
    assert all(f"MARKER_{index}" in result["summary"] for index in range(4))
    assert all(len(call["messages"][1]["content"].encode("utf-8")) <= enhancements.MAX_SUMMARY_INPUT_BYTES
               for call in requests)


def test_nonshrinking_reducer_stops_without_unbounded_retry(monkeypatch):
    phases = []

    def respond(payload):
        system, user = [item["content"] for item in payload["messages"]]
        if "chapter_title" in system:
            phases.append("map")
            return {"notes": "α" * 1050, "chapter_title": "Ενότητα"}
        assert "Condense" in system
        phases.append("reduce")
        return {"notes": user}

    monkeypatch.setattr(enhancements, "_ollama", respond)
    source = [{"start": index * 10, "end": index * 10 + 5, "text": "x" * 2100}
              for index in range(4)]
    with pytest.raises(enhancements.EnhancementError, match="fit all transcript notes"):
        enhancements.summarize_segments(source, "el")
    assert phases == ["map"] * 4 + ["reduce"] * 4


@pytest.mark.parametrize("long_source", [False, True])
def test_actual_direct_and_final_requests_bound_key_points_in_schema(monkeypatch, long_source):
    requests = []

    def local_response(path, payload, *, timeout):
        requests.append(deepcopy(payload))
        assert path == "/api/chat"
        if not payload["messages"]:
            assert payload["keep_alive"] == 0
            return {"done": True, "done_reason": "unload", "message": {"content": ""}}
        assert timeout == 240
        assert payload["options"]["num_predict"] == 2048
        system = payload["messages"][0]["content"]
        if "chapter_title" in system and "key_points" not in system:
            result = {"notes": "The stated task remains pending.", "chapter_title": "Pending task"}
        else:
            result = {"summary": "The task remains pending.", "key_points": ["It is not completed."]}
            if not long_source:
                result["chapter_title"] = "Pending task"
        return {"done": True, "done_reason": "stop", "message": {"content": json.dumps(result)}}

    monkeypatch.setattr(enhancements, "local_ollama_json", local_response)
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "unit-summary")
    source = ([{"start": index * 10, "end": index * 10 + 5, "text": "Source words. " * 160}
               for index in range(2)] if long_source else [{"start": 0, "text": "The task is still pending."}])
    result = enhancements.summarize_segments(source, "en")
    inference = [payload for payload in requests if payload["messages"]]
    final = inference[-1]
    schema = final["format"]
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert schema["properties"]["key_points"] == {
        "type": "array", "minItems": 1, "maxItems": 8,
        "items": {"type": "string", "minLength": 1}}
    expected_fields = {"summary", "key_points"} | ({"chapter_title"} if not long_source else set())
    assert set(schema["required"]) == set(schema["properties"]) == expected_fields
    assert "at most 8 concise key points" in final["messages"][0]["content"]
    assert all(payload["format"] == "json" for payload in inference[:-1])
    assert result["key_points"] == ["It is not completed."]


@pytest.mark.parametrize("count", [0, 8, 9])
def test_final_key_point_count_matches_contract_without_clipping(count):
    response = {"summary": "The original facts remain available.",
                "key_points": [f"Complete point {index}." for index in range(count)]}
    original = deepcopy(response)
    if count == 8:
        result = enhancements._summary_result(response, [{"start": 0, "title": "Section"}])
        assert result["key_points"] == response["key_points"]
    else:
        with pytest.raises(enhancements.EnhancementError, match="valid summary"):
            enhancements._summary_result(response, [{"start": 0, "title": "Section"}])
    assert response == original
