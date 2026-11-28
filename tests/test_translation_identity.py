"""Regression coverage for the observed whole-transcript copy failure.

Model responses here are synthetic. These checks cannot establish translation
quality, but prevent an unchanged result from being advertised as a new language.
"""
from copy import deepcopy

import pytest

import enhancements as ai


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    for key in ("LINKSCRIBE_TRANSLATION_MODEL", "LINKSCRIBE_TRANSLATION_BACKEND",
                "LINKSCRIBE_OLLAMA_MODEL", "LINKSCRIBE_OLLAMA_RETAIN_MODELS"):
        monkeypatch.delenv(key, raising=False)


def source_segments():
    return [{"start": 1.5, "end": 3.2, "text": "The parcel has not arrived.", "speaker": "Speaker 1"},
            {"start": 3.2, "end": 5.6, "text": "Delivery is still pending.", "speaker": "Unknown speaker"}]


def json_reply(monkeypatch, texts):
    monkeypatch.setattr(ai, "_ollama", lambda _request: {"translations": texts})


@pytest.mark.parametrize("backend", ["json", "plain", "marian"])
def test_each_backend_rejects_a_whole_copy_without_changing_the_source(monkeypatch, backend):
    source = source_segments()
    before = deepcopy(source)
    if backend == "plain":
        monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "linkscribe-hy-mt3:7b")
        monkeypatch.setattr(ai, "_translate_plain_fragment", lambda text, *_: text)
    elif backend == "marian":
        import marian_translation
        monkeypatch.setenv("LINKSCRIBE_TRANSLATION_BACKEND", "marian")
        monkeypatch.setattr(marian_translation, "translate_segments", lambda segments, *_: deepcopy(segments))
    else:
        json_reply(monkeypatch, [item["text"] for item in source])
    with pytest.raises(ai.EnhancementError, match="No separate Greek translation.*unchanged"):
        ai.translate_segments(source, "el", "EN_us")
    assert source == before


def test_whitespace_changes_do_not_disguise_a_whole_copy(monkeypatch):
    source = source_segments()
    json_reply(monkeypatch, [item["text"].replace(" ", "\n\t  ") for item in source])
    with pytest.raises(ai.EnhancementError, match="unchanged"):
        ai.translate_segments(source, "el", "en")


def test_greek_to_english_copy_has_the_correct_target_warning(monkeypatch):
    source = [{"start": 0, "end": 2, "text": "Η παράδοση εκκρεμεί."}]
    json_reply(monkeypatch, [source[0]["text"]])
    with pytest.raises(ai.EnhancementError, match="No separate English translation"):
        ai.translate_segments(source, "en", "el")


def test_unchanged_names_alongside_translated_prose_are_retained(monkeypatch):
    source = [{"start": 0, "end": 1, "text": "Anna"},
              {"start": 1, "end": 3, "text": "Delivery is still pending."}]
    json_reply(monkeypatch, ["Anna", "Η παράδοση εκκρεμεί ακόμη."])
    result = ai.translate_segments(source, "el", "en")
    assert result == [{**source[0]}, {**source[1], "text": "Η παράδοση εκκρεμεί ακόμη."}]


def test_names_only_copy_reports_no_separate_result_without_judging_the_name(monkeypatch):
    source = [{"start": 0, "end": 1, "text": "Anna"}]
    json_reply(monkeypatch, ["Anna"])
    with pytest.raises(ai.EnhancementError, match="original transcript remains available") as error:
        ai.translate_segments(source, "el", "en")
    assert "wrong" not in str(error.value) and source[0]["text"] == "Anna"


def test_numbers_and_punctuation_can_legitimately_stay_identical(monkeypatch):
    source = [{"start": 0, "end": 1, "text": "24 / 100 — €39.60"}]
    json_reply(monkeypatch, [source[0]["text"]])
    assert ai.translate_segments(source, "el", "en") == source


def test_same_language_bypasses_inference_and_identity_warning(monkeypatch):
    monkeypatch.setattr(ai, "_ollama", lambda *_: pytest.fail("No translation was needed"))
    source = source_segments()
    assert ai.translate_segments(source, "en", "en") == source


def test_a_changed_response_is_not_certified_for_language_or_meaning(monkeypatch):
    # An English paraphrase is still wrong for Greek. The identity check makes
    # no claim to detect that broader semantic failure.
    source = source_segments()
    json_reply(monkeypatch, ["The package has not arrived.", "Delivery is still pending."])
    assert ai.translate_segments(source, "el", "en")[0]["text"] == "The package has not arrived."
