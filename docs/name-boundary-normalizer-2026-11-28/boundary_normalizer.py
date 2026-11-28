"""Propose source-exact PERSON boundaries; never rewrite source or certify names.

This experimental pure function has no model, corpus, expected-name or translation
access. A lexical article match is a proposal requiring independent source review.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import unicodedata

import regex

VERSION = 1
# Modern Greek definite-article paradigm, including the documented τη/την forms.
# This is a grammatical inventory, not a list of personal names.
ARTICLE_FORMS = ("ο", "η", "το", "του", "της", "τον", "την", "τη", "οι", "τα", "των", "τους", "τις")
ARTICLE_KEYS = frozenset(unicodedata.normalize("NFC", form).casefold() for form in ARTICLE_FORMS)


def _key(value):
    return unicodedata.normalize("NFC", value).casefold()


def _source(segments):
    if not isinstance(segments, list) or not segments:
        raise ValueError("Expected original source segments.")
    if any(not isinstance(segment, dict) or not isinstance(segment.get("text"), str) for segment in segments):
        raise ValueError("Invalid original source segment schema.")
    text = "\n".join(segment["text"] for segment in segments)
    offsets = []
    cursor = 0
    for index, segment in enumerate(segments):
        end = cursor + len(segment["text"])
        offsets.append({"segment_index": index, "start": cursor, "end": end})
        cursor = end + 1
    return text, offsets


def _validated(raw_entities, text, segments):
    if not isinstance(raw_entities, list):
        raise ValueError("Expected native raw entity list.")
    boundaries = {0, len(text)}
    for match in regex.finditer(r"\X", text):
        boundaries.update((match.start(), match.end()))
    mapped = []
    for raw in raw_entities:
        if not isinstance(raw, dict) or set(raw) != {"start", "end", "text", "label", "score"}:
            raise ValueError("Unexpected raw entity schema.")
        start, end, score = raw["start"], raw["end"], raw["score"]
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
                or start not in boundaries or end not in boundaries or raw["text"] != text[start:end]
                or raw["label"] != "person" or type(score) not in {int, float}
                or not math.isfinite(score) or not 0.5 <= score <= 1):
            raise ValueError("Raw source-span, label or score integrity failed.")
        parents = [segment for segment in segments if segment["start"] <= start and end <= segment["end"]]
        if len(parents) != 1:
            raise ValueError("A raw person span crosses an original source segment boundary.")
        mapped.append((raw, parents[0]))
    ordered = sorted(mapped, key=lambda value: (value[0]["start"], value[0]["end"]))
    if any(left[0]["end"] > right[0]["start"] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("Raw person spans overlap.")
    return mapped


def propose_person_boundaries(segments, raw_entities, source_language):
    """Return proposals with original raw spans; do not mutate either input.

    Offsets are Python Unicode codepoint offsets in the exact LF-joined source.
    A changed proposal is never an automatic assertion that a prefix was an
    article: actual names and unpunctuated initials can have the same spelling.
    """
    before = json.dumps({"segments": segments, "raw_entities": raw_entities}, ensure_ascii=False,
                        sort_keys=True, separators=(",", ":"), allow_nan=False)
    text, offsets = _source(segments)
    validated = _validated(raw_entities, text, offsets)  # Validate the whole batch before proposing anything.
    results = []
    for raw, parent in validated:
        start, end = raw["start"], raw["end"]
        result = {"raw": copy.deepcopy(raw), "segment_index": parent["segment_index"],
                  "proposed_span": {"start": start, "end": end, "text": text[start:end],
                                    "segment_start": start - parent["start"], "segment_end": end - parent["start"]},
                  "raw_score": raw["score"], "score_scope": "original model span; no normalized-span score",
                  "status": "unchanged", "reason": None, "removed_from_protection": None,
                  "requires_independent_boundary_review": True}
        value = raw["text"]
        if source_language != "el":
            result["reason"] = "source_language_outside_greek_rule"
        elif not value or value[0].isspace() or value[-1].isspace():
            result.update(status="review_required_no_change", reason="raw_outer_whitespace")
        else:
            boundary = next((index for index, character in enumerate(value) if character.isspace()), None)
            if boundary is None:
                result["reason"] = "raw_single_token_span"
            elif _key(value[:boundary]) not in ARTICLE_KEYS:
                result["reason"] = "no_exact_standalone_definite_article"
            else:
                next_word = boundary
                while next_word < len(value) and value[next_word].isspace():
                    next_word += 1
                separator = value[boundary:next_word]
                remainder = value[next_word:]
                preceding = text[start - 1] if start > parent["start"] else ""
                if preceding and (preceding.isalnum() or unicodedata.category(preceding).startswith("M")
                                  or preceding in "_'’ʼ-‐‑"):
                    result.update(status="review_required_no_change", reason="raw_start_inside_word_or_name_prefix")
                elif any(character != "\t" and unicodedata.category(character) != "Zs" for character in separator):
                    result.update(status="review_required_no_change", reason="nonhorizontal_separator")
                elif not remainder or not unicodedata.category(remainder[0]).startswith("L"):
                    result.update(status="review_required_no_change", reason="empty_or_punctuated_name_onset")
                elif _key(remainder.split(maxsplit=1)[0]) in ARTICLE_KEYS:
                    result.update(status="review_required_no_change", reason="stacked_or_ambiguous_article_like_tokens")
                else:
                    proposed_start = start + next_word
                    removed = text[start:proposed_start]
                    if not parent["start"] <= start < proposed_start < end <= parent["end"]:
                        raise ValueError("Proposed boundary would leave its original source segment.")
                    if text[proposed_start:end] != remainder or removed + remainder != raw["text"]:
                        raise ValueError("Proposed source-slice reconstruction failed.")
                    result.update(status="proposed_remove_definite_article", reason="exact_article_form_and_horizontal_separator",
                                  proposed_span={"start": proposed_start, "end": end, "text": remainder,
                                                 "segment_start": proposed_start - parent["start"],
                                                 "segment_end": end - parent["start"]},
                                  removed_from_protection={"start": start, "end": proposed_start, "text": removed,
                                                           "remains_ordinary_source_text": True},
                                  semantic_limit="Article-like names and undotted initials remain ambiguous; proposal does not certify name identity.")
        results.append(result)
    after = json.dumps({"segments": segments, "raw_entities": raw_entities}, ensure_ascii=False,
                       sort_keys=True, separators=(",", ":"), allow_nan=False)
    if before != after:
        raise ValueError("Normalizer mutated original source, metadata or native predictions.")
    return {"version": VERSION, "source_language": source_language,
            "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source_segments": copy.deepcopy(segments), "source_unchanged": True,
            "raw_entity_count": len(raw_entities), "proposals": results,
            "automatic_name_safety_certified": False, "translation_or_masking_performed": False}
