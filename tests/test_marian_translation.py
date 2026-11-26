"""Contracts for public-model setup and bounded native translation inference."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

import enhancements
import marian_translation as mt


class Characters:
    def encode(self, text, out_type=str):
        return list(text)

    def decode(self, tokens):
        return "".join(tokens)


def engine_for(monkeypatch, callback):
    engine = SimpleNamespace(translate_batch=callback)
    tokenizer = Characters()
    monkeypatch.setattr(mt, "_load_model", lambda *args: (engine, tokenizer, tokenizer))
    return engine, tokenizer


def test_native_translation_preserves_metadata_and_uses_completion_token(monkeypatch):
    observed = []

    def infer(tokens, **kwargs):
        observed.append((tokens, kwargs))
        return [SimpleNamespace(hypotheses=[["Κ", "α", "λ", "ά", "</s>"]]) for _ in tokens]

    engine_for(monkeypatch, infer)
    source = [{"start": 1, "end": 2, "text": "Hello", "speaker": "Alice", "extra": {"keep": True}},
              {"start": 2, "end": 3, "text": "  "}]
    before = copy.deepcopy(source)
    result = mt.translate_segments(source, "en", "el")
    assert source == before
    assert result == [{**source[0], "text": "Καλά"}, source[1]]
    assert observed[0][0] == [list("Hello")]
    assert observed[0][1]["max_input_length"] == 0  # No native silent input truncation.
    assert observed[0][1]["return_end_token"] is True


def test_split_preserves_all_unicode_characters_and_bounds_real_tokens(monkeypatch):
    monkeypatch.setattr(mt, "MAX_SOURCE_TOKENS", 31)
    text = ("Μια πρόταση. Next words €12,50!\n" * 20) + "end"
    parts = list(mt._fragments(text, Characters()))
    assert "".join(parts) == text
    assert all(0 < len(Characters().encode(part)) <= 31 for part in parts)
    assert len(parts) > 10


@pytest.mark.parametrize("text", [
    "First sentence. Second sentence!\n\nA final question?",
    "Maria said: 'Don't reset anything. Keep the number 12.5.' Then she left.",
    "Η Μαρία είπε «Μην αλλάξεις τίποτα· κράτησε το 12,5». Μια ερώτηση; Μια απάντηση.",
    'An unmatched " quotation and an instrument\'s label stay here.',
    'Two words: “use this” and «keep that».',
])
def test_sentence_and_quote_units_cover_every_source_character(text):
    for language in ("en", "el"):
        pieces = list(mt._text_units(text, language))
        assert "".join(value for _, value in pieces) == text
        assert all(value for _, value in pieces)


def test_sentence_boundaries_preserve_titles_initials_and_decimals():
    text = "Dr. A. Jones measured 0.875 g. The next reading was 12.5 ml."
    assert list(mt._sentence_units(text, "en")) == [
        "Dr. A. Jones measured 0.875 g. ", "The next reading was 12.5 ml."]
    greek = "Η Δρ. Μαρία σημείωσε 12.5 ml. Έγινε έλεγχος; Ναι."
    assert list(mt._sentence_units(greek, "el")) == [
        "Η Δρ. Μαρία σημείωσε 12.5 ml. ", "Έγινε έλεγχος; ", "Ναι."]


def test_quoted_text_is_sent_as_content_with_delimiters_retained(monkeypatch):
    actual = []

    def infer(tokens, **kwargs):
        actual.extend("".join(item) for item in tokens)
        return [SimpleNamespace(hypotheses=[list("T" + "".join(item)) + ["</s>"]]) for item in tokens]

    engine_for(monkeypatch, infer)
    source = [{"start": 1, "end": 5, "text": "She said: 'Don't reset it. Keep it.' Then she left."}]
    result = mt.translate_segments(source, "en", "el")
    assert actual == ["She said:", "Don't reset it.", "Keep it.", "Then she left."]
    assert result[0]["text"] == "TShe said: 'TDon't reset it. TKeep it.' TThen she left."
    assert result[0]["start"] == 1 and result[0]["end"] == 5


@pytest.mark.parametrize("hypothesis", [[], ["text"], ["</s>"], ["x"] * mt.MAX_TARGET_TOKENS + ["</s>"]])
def test_missing_or_exhausted_completion_is_never_returned(monkeypatch, hypothesis):
    engine, tokenizer = engine_for(monkeypatch, lambda *args, **kwargs: [SimpleNamespace(hypotheses=[hypothesis])])
    with pytest.raises(mt.TranslationError):
        mt._translate_batch(engine, tokenizer, tokenizer, ["source"])


def test_late_batch_failure_does_not_mutate_original(monkeypatch):
    monkeypatch.setattr(mt, "MAX_BATCH_ITEMS", 2)
    calls = []

    def infer(tokens, **kwargs):
        calls.append(tokens)
        if len(calls) == 2:
            raise RuntimeError("native decoder failure")
        return [SimpleNamespace(hypotheses=[["translated", "</s>"]]) for _ in tokens]

    engine_for(monkeypatch, infer)
    source = [{"start": i, "end": i + 1, "text": f"source {i}"} for i in range(4)]
    before = copy.deepcopy(source)
    with pytest.raises(mt.TranslationError, match="could not finish"):
        mt.translate_segments(source, "en", "el")
    assert source == before and len(calls) == 2


@pytest.mark.parametrize("source,target", [("fr", "el"), (None, "en"), ("auto", "el")])
def test_source_language_is_not_guessed(monkeypatch, source, target):
    monkeypatch.setattr(mt, "_load_model", lambda *args: pytest.fail("invalid language loaded model"))
    with pytest.raises(mt.TranslationError, match="English to Greek"):
        mt.translate_segments([{"text": "hello"}], source, target)


def test_empty_and_same_language_do_not_start_model(monkeypatch):
    monkeypatch.setattr(mt, "_load_model", lambda *args: pytest.fail("unneeded model load"))
    source = [{"start": 0, "end": 1, "text": "hello"}]
    assert mt.translate_segments(source, "en", "en") == source
    assert mt.translate_segments([], "en", "el") == []
    assert mt.translate_segments([{"text": " \n"}], "en", "el") == [{"text": " \n"}]


def test_all_sources_are_validated_before_first_inference(monkeypatch):
    monkeypatch.setattr(mt, "_load_model", lambda *args: pytest.fail("invalid source loaded model"))
    with pytest.raises(mt.TranslationError, match="text"):
        mt.translate_segments([{"text": "valid"}, {"text": 3}], "en", "el")
    with pytest.raises(mt.TranslationError, match="Unicode"):
        mt.translate_segments([{"text": "valid"}, {"text": "\ud800"}], "en", "el")


@pytest.mark.parametrize("raw", ["0", "33", "not-a-number", ""])
def test_invalid_cpu_thread_setting_is_actionable(monkeypatch, raw):
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_THREADS", raw)
    with pytest.raises(mt.TranslationError, match="1 through 32"):
        mt._threads()


def test_oversized_or_incomplete_native_batch_is_rejected(monkeypatch):
    engine, tokenizer = engine_for(monkeypatch, lambda *args, **kwargs: [])
    with pytest.raises(mt.TranslationError, match="tokenizer"):
        mt._translate_batch(engine, tokenizer, tokenizer, ["a" * (mt.MAX_SOURCE_TOKENS + 1)])
    with pytest.raises(mt.TranslationError, match="incomplete batch"):
        mt._translate_batch(engine, tokenizer, tokenizer, ["source"])


def test_download_checks_exact_size_and_sha256(monkeypatch, tmp_path):
    body = b"model archive bytes"
    spec = {"url": "https://example.invalid/model", "archive_bytes": len(body),
            "archive_sha256": hashlib.sha256(body).hexdigest()}
    monkeypatch.setattr(mt.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(body))
    mt._download_archive(spec, tmp_path / "good.zip")
    with pytest.raises(mt.TranslationError, match="checksum"):
        mt._download_archive({**spec, "archive_sha256": "0" * 64}, tmp_path / "bad.zip")
    with pytest.raises(mt.TranslationError, match="size or time"):
        mt._download_archive({**spec, "archive_bytes": 1}, tmp_path / "long.zip")


@pytest.mark.parametrize("name", ["../escape", "/absolute", "dir/member", "..\\escape"])
def test_model_archive_cannot_escape_cache(tmp_path, name):
    archive = tmp_path / "model.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr(name, b"bad")
    with pytest.raises(mt.TranslationError, match="unsafe"):
        mt._extract_model(archive, tmp_path)


def test_partial_archive_cannot_be_used(tmp_path):
    archive = tmp_path / "model.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("LICENSE", b"license")
    with pytest.raises(mt.TranslationError, match="do not match"):
        mt._extract_model(archive, tmp_path)


def test_cached_manifest_must_match_model_and_hashes(tmp_path):
    pair = "en-el"
    manifest = {"format": "linkscribe-marian-v1", "pair": pair, "source": mt.MODEL_SPECS[pair],
                "quantization": "int8", "files": {}}
    for name in mt.RUNTIME_FILES:
        (tmp_path / name).write_bytes(b"model")
        manifest["files"][name] = {"bytes": 5, "sha256": hashlib.sha256(b"model").hexdigest()}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert mt._read_manifest(tmp_path, pair, verify_files=True)["pair"] == pair
    (tmp_path / "model.bin").write_bytes(b"other")
    with pytest.raises(mt.TranslationError, match="damaged"):
        mt._read_manifest(tmp_path, pair, verify_files=True)


def test_dedicated_backend_works_without_ollama_configuration(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_BACKEND", "marian")
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_URL", "http://203.0.113.5:11434")
    monkeypatch.setattr(mt, "translate_segments", lambda segments, source, target: [{**s, "text": "translated"} for s in segments])
    result = enhancements.translate_segments([{"text": "source"}], "el", source_language="en-US")
    assert result == [{"text": "translated"}]


def test_invalid_backend_is_not_silently_replaced(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_BACKEND", "misspelled")
    with pytest.raises(enhancements.EnhancementError, match="marian or ollama"):
        enhancements.translate_segments([{"text": "source"}], "el", source_language="en")
