"""Visible exact-source PERSON spans for one bounded development preparation.

No model, reference answer, personal-name lexicon or case ID is an input here.
Only validated wrappers may be stripped; a changed inner name is rejected.
Exact span accounting does not certify the translated roles or meaning.
"""
from __future__ import annotations

import copy
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unicodedata

NORMALIZER_PATH = Path(__file__).resolve().parents[1] / "name-boundary-normalizer-2026-11-28/boundary_normalizer.py"
_spec = importlib.util.spec_from_file_location("frozen_source_boundary_normalizer", NORMALIZER_PATH)
_normalizer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_normalizer)

PREFIX = "<x"
PATTERN = re.compile(r"<x(?P<index>0|[1-9][0-9]{0,3})>(?P<source_text>.*?)</x(?P=index)>", re.DOTALL)
INSTRUCTION = ' Treat paired tags as exact-copy source spans. Copy every whole tagged span, including both tags and all text between them, exactly once, character for character, into the translation for its original input entry. Translate all surrounding ordinary text. Do not change the text inside a span, nest spans, or add, remove, split, or move a span to another entry.'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def reserved_present(text):
    # Comparison only. Preserve all source/output characters, including formats.
    folded = "".join(c for c in unicodedata.normalize("NFKC", text).casefold()
                     if unicodedata.category(c) != "Cf")
    # Reserve both opening and closing forms, even if a model inserts spacing.
    # This is rejection-only comparison; no source or output is rewritten.
    return bool(re.search(r"<\s*/?\s*x", folded))


def build_protection(segments, raw_entities, source_language):
    """Use exact actual raw source spans and the unchanged reviewed normalizer."""
    original = copy.deepcopy(segments)
    normalized = _normalizer.propose_person_boundaries(segments, raw_entities, source_language)
    source = "\n".join(item["text"] for item in segments)
    if any(reserved_present(item["text"]) for item in segments):
        raise ValueError("Original source collides with the reserved marker namespace.")
    if len(segments) > 9999 or len(normalized["proposals"]) > 9999:
        raise ValueError("The bounded marker identifier space is exceeded.")
    if any(item["status"] == "review_required_no_change" for item in normalized["proposals"]):
        raise ValueError("This source boundary requires unresolved review; no automatic protection.")
    spans = [{"start": p["proposed_span"]["start"], "end": p["proposed_span"]["end"]}
             for p in normalized["proposals"]]
    source_binding = digest({"source": source, "spans": spans})
    markers = []
    for occurrence, proposal in enumerate(normalized["proposals"]):
        segment_index = proposal["segment_index"]
        span = proposal["proposed_span"]
        opening_tag = f"{PREFIX}{occurrence}>"
        closing_tag = f"</x{occurrence}>"
        marker = opening_tag + span["text"] + closing_tag
        if marker in source:
            raise ValueError("Generated marker already occurs in the original source.")
        markers.append({"marker": marker, "marker_index": occurrence,
                        "opening_tag": opening_tag, "closing_tag": closing_tag,
                        "segment_index": segment_index,
                        "start": span["segment_start"], "end": span["segment_end"],
                        "source_text": span["text"], "global_start": span["start"],
                        "global_end": span["end"], "raw": copy.deepcopy(proposal["raw"]),
                        "normalizer_status": proposal["status"]})
    masked = copy.deepcopy(segments)
    for index, segment in enumerate(segments):
        selected = sorted((m for m in markers if m["segment_index"] == index), key=lambda m: m["start"])
        parts, cursor = [], 0
        for item in selected:
            start, end = item["start"], item["end"]
            if not cursor <= start < end <= len(segment["text"]) or segment["text"][start:end] != item["source_text"]:
                raise ValueError("Protected name is not an exact nonoverlapping original segment slice.")
            parts.extend((segment["text"][cursor:start], item["marker"]))
            cursor = end
        parts.append(segment["text"][cursor:])
        masked[index]["text"] = "".join(parts)
    bundle = {"schema_version": 1, "source_language": source_language, "source_segments": original,
              "source_segments_sha256": digest(original), "source_text_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "normalizer_result": normalized, "masked_segments": masked, "markers": markers,
              "source_binding_derivation": "SHA256 canonical exact source text and normalized source offsets; digest kept outside tags; original source name remains visible inside tags",
              "source_binding_sha256": source_binding,
              "representation": "visible_exact_source_name_inside_paired_tags",
              "restoration_policy": "strip_only_already_exact_validated_wrappers",
              "semantic_safety_certified": False, "independent_boundary_review_required": True}
    bundle["protection_binding_sha256"] = digest({"source_segments_sha256": bundle["source_segments_sha256"],
                                                  "masked_segments": masked, "markers": markers})
    # This source-only wrapper roundtrip is not a translated response.
    restored, _ = restore_segments(bundle, masked)
    if restored != original or segments != original:
        raise ValueError("Source-only wrapping fails exact text/metadata reversibility.")
    bundle["full_source_roundtrip_exact"] = True
    return bundle


def strict_response_strings(content, count):
    """Reject duplicate/extra properties and malformed native translation JSON."""
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Native translation JSON repeats a property.")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Nonstandard JSON constant: " + value)

    if not isinstance(content, str):
        raise ValueError("The native final content is not text.")
    value = json.loads(content, object_pairs_hook=object_pairs, parse_constant=invalid_constant)
    if not isinstance(value, dict) or set(value) != {"translations"}:
        raise ValueError("Native JSON must contain only the translations property.")
    strings = value["translations"]
    if not isinstance(strings, list) or len(strings) != count or any(not isinstance(t, str) or not t.strip() for t in strings):
        raise ValueError("Native translation array has an invalid count or text value.")
    for text in strings:
        text.encode("utf-8")
    return strings


def restore_segments(bundle, translated_segments):
    """Validate whole source-exact pairs, then strip only their wrappers.

    A mismatched inner name never falls back to the name in the source map.
    The returned name bytes come from the already validated response itself.
    """
    original = bundle["source_segments"]
    if digest(original) != bundle["source_segments_sha256"]:
        raise ValueError("Original source metadata changed before restoration.")
    if digest({"source_segments_sha256": bundle["source_segments_sha256"],
               "masked_segments": bundle["masked_segments"], "markers": bundle["markers"]}) != bundle["protection_binding_sha256"]:
        raise ValueError("Protection map or masked source changed before restoration.")
    if not isinstance(translated_segments, list) or len(translated_segments) != len(original):
        raise ValueError("Translated segment count changed before restoration.")
    all_markers = [item["marker"] for item in bundle["markers"]]
    all_indices = [item["marker_index"] for item in bundle["markers"]]
    if len(set(all_markers)) != len(all_markers) or len(set(all_indices)) != len(all_indices):
        raise ValueError("Protection map contains duplicate spans or tag identifiers.")
    restored = []
    audit = []
    for index, (before, translated) in enumerate(zip(original, translated_segments)):
        if (not isinstance(translated, dict) or not isinstance(translated.get("text"), str) or
                {k: v for k, v in translated.items() if k != "text"} != {k: v for k, v in before.items() if k != "text"}):
            raise ValueError("Translated segment metadata/schema changed before restoration.")
        text = translated["text"]
        expected = [item for item in bundle["markers"] if item["segment_index"] == index]
        by_marker = {item["marker"]: item for item in expected}
        matches = list(PATTERN.finditer(text))
        observed = [match.group(0) for match in matches]
        if Counter(observed) != Counter(by_marker.keys()):
            raise ValueError("A whole tagged source span is missing, changed, duplicated, nested, unknown or in the wrong source segment.")
        residue = PATTERN.sub("", text)
        if reserved_present(residue):
            raise ValueError("Translated text contains a malformed or unrecognized marker prefix.")
        replacements = []

        def replace(match):
            item = by_marker[match.group(0)]
            source_slice = before["text"][item["start"]:item["end"]]
            if (source_slice != item["source_text"] or match.group("source_text") != source_slice
                    or match.group("index") != str(item["marker_index"])
                    or match.group(0) != item["opening_tag"] + source_slice + item["closing_tag"]
                    or reserved_present(match.group("source_text"))):
                raise ValueError("Tagged response text is not its exact original source slice and wrapper.")
            replacements.append(item["marker"])
            # No source-map replacement, spelling normalization or output repair.
            return match.group("source_text")

        value = PATTERN.sub(replace, text)
        if Counter(replacements) != Counter(by_marker.keys()) or reserved_present(value):
            raise ValueError("Restoration failed exact once-only marker accounting.")
        restored.append({**copy.deepcopy(before), "text": value})
        audit.append({"segment_index": index, "expected_markers": list(by_marker),
                      "observed_markers": observed, "restored_markers": replacements,
                      "exact_same_segment_once_only": True, "metadata_preserved": True,
                      "inner_source_spelling_exact": True, "wrapper_only_removal": True,
                      "changed_inner_text_repaired": False})
    return restored, audit
