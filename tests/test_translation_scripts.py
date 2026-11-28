"""Observed script-corruption regressions, not a semantic quality evaluator.

The model replies are controlled here. Actual candidate outputs and independent
meaning reviews remain in the separately frozen development evidence.
"""
from copy import deepcopy

import pytest

import enhancements as ai


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    for key in ("LINKSCRIBE_TRANSLATION_MODEL", "LINKSCRIBE_TRANSLATION_BACKEND",
                "LINKSCRIBE_OLLAMA_MODEL", "LINKSCRIBE_OLLAMA_RETAIN_MODELS"):
        monkeypatch.delenv(key, raising=False)


def translate(monkeypatch, text, translated, target="el", source="en"):
    segments = [{"start": 1.5, "end": 3.2, "text": text, "speaker": "Speaker 1"}]
    before = deepcopy(segments)
    monkeypatch.setattr(ai, "_ollama", lambda _request: {"translations": [translated]})
    try:
        return ai.translate_segments(segments, target, source)
    finally:
        assert segments == before


@pytest.mark.parametrize("injected", ["اقتباس", "скобки", "براکت"])
def test_rejects_new_foreign_words_in_greek_prose(monkeypatch, injected):
    with pytest.raises(ai.EnhancementError, match="unexpected writing system"):
        translate(monkeypatch, "A quotation requires permission.",
                  f"Η {injected} απαιτεί άδεια.")


def test_rejects_new_foreign_words_in_english_prose(monkeypatch):
    with pytest.raises(ai.EnhancementError, match="original transcript remains available"):
        translate(monkeypatch, "Οι μετρήσεις δεν άλλαξαν.",
                  "The измерения have not changed.", "en", "el")


@pytest.mark.parametrize("backend", ["plain", "marian"])
def test_alternative_backends_use_the_same_result_guard(monkeypatch, backend):
    source = [{"start": 0, "end": 1, "text": "A quotation requires permission."}]
    before = deepcopy(source)
    if backend == "plain":
        monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "linkscribe-hy-mt3:7b")
        monkeypatch.setattr(ai, "_translate_plain_fragment", lambda *_: "Η اقتباس απαιτεί άδεια.")
    else:
        import marian_translation
        monkeypatch.setenv("LINKSCRIBE_TRANSLATION_BACKEND", "marian")
        monkeypatch.setattr(marian_translation, "translate_segments", lambda *_:
                            [{**source[0], "text": "Η اقتباس απαιτεί άδεια."}])
    with pytest.raises(ai.EnhancementError, match="unexpected writing system"):
        ai.translate_segments(source, "el", "en")
    assert source == before


def test_preserves_exact_foreign_names_and_quoted_words(monkeypatch):
    text = 'Ирина wrote "你好" for مُنى.'
    translated = 'Η Ирина έγραψε «你好» για τη مُنى.'
    result = translate(monkeypatch, text, translated)
    assert result == [{"start": 1.5, "end": 3.2, "text": translated, "speaker": "Speaker 1"}]


def test_an_existing_alphabet_does_not_allow_unrelated_words(monkeypatch):
    with pytest.raises(ai.EnhancementError, match="unexpected writing system"):
        translate(monkeypatch, 'Ирина wrote the readings.', 'Η Ирина έγραψε τις измерения.')


def test_part_of_a_source_name_is_not_a_preserved_complete_run(monkeypatch):
    with pytest.raises(ai.EnhancementError, match="unexpected writing system"):
        translate(monkeypatch, "Ирина arrived.", "Η рина έφτασε.")


def test_unicode_equivalent_preserved_text_is_not_rewritten(monkeypatch):
    # Decomposed Cyrillic Й is canonically equivalent; output stays verbatim.
    translated = "Η И\u0306рина έφτασε."
    result = translate(monkeypatch, "Йрина arrived.", translated)
    assert result[0]["text"] == translated


def test_technical_latin_greek_symbols_and_numbers_remain_allowed(monkeypatch):
    translated = "Το RZ-58 έδειξε −5,4 °C· µ = 2, 𝐀 = 3, ℝ, 10 m². ✓"
    assert translate(monkeypatch, "The RZ-58 reading and symbols are recorded.",
                     translated)[0]["text"] == translated


@pytest.mark.parametrize("translated", [
    "Ισχύει ο κανόνας του LʼHôpital.",
    "Το όνομα Hawaiʻi διατηρείται.",
    "Η ένδειξη είναι ℵ₀ και η δεύτερη ℶ₁· ℷ και ℸ είναι σύμβολα.",
])
def test_name_apostrophes_and_hebrew_derived_math_are_not_foreign_prose(monkeypatch, translated):
    assert translate(monkeypatch, "The rule, name and notation are recorded.",
                     translated)[0]["text"] == translated


def test_actual_hebrew_letters_are_not_exempted_as_math_symbols(monkeypatch):
    with pytest.raises(ai.EnhancementError, match="unexpected writing system"):
        translate(monkeypatch, "The readings were copied.", "Οι מדידות αντιγράφηκαν.")


def test_existing_foreign_word_may_move_between_source_segments(monkeypatch):
    source = [{"start": 0, "end": 1, "text": "Ирина:"},
              {"start": 1, "end": 2, "text": "She arrived."}]
    monkeypatch.setattr(ai, "_ollama", lambda _request:
                        {"translations": ["Η επισκέπτρια:", "Η Ирина έφτασε."]})
    assert ai.translate_segments(source, "el", "en")[1]["text"] == "Η Ирина έφτασε."


def test_latin_greek_prose_still_requires_independent_language_and_meaning_review(monkeypatch):
    # This guard does not certify English paraphrase as Greek or correct a role.
    result = translate(monkeypatch, "Markos borrowed it.", "Markos gave it.")
    assert result[0]["text"] == "Markos gave it."
