"""Source-only construction for one bounded native marker-grammar proposal.

This module does not convert a schema, call a native runtime, tokenize, infer,
load a detector or validate translation meaning. Actual emitted grammar must
pass a separately authorized native gate before any generation.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import itertools
import json
import re

MAX_SEGMENTS = 2
MAX_TAGS_PER_SEGMENT = 3
TAG = re.compile(r"<x(?:0|[1-9][0-9]{0,3})/>")
# This is a profile over serialized JSON-string bodies, not decoded values.
# Literal Unicode is allowed. Unicode JSON escapes are deliberately excluded.
GAP = r'(?:[^\x00-\x1F\x22\x5C\x3C]|\x5C[\x22\x5C/bfnrt])*'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def checked_layout(layout):
    if (not isinstance(layout, list) or len(layout) != MAX_SEGMENTS
            or any(not isinstance(tags, list) for tags in layout)):
        raise ValueError("This original-six proposal requires two complete source entries.")
    flat = []
    for tags in layout:
        if len(tags) > MAX_TAGS_PER_SEGMENT:
            raise ValueError("More than three tags in one source entry; no alternate profile.")
        if any(not isinstance(tag, str) or not TAG.fullmatch(tag) for tag in tags):
            raise ValueError("A marker is outside the exact existing compact namespace.")
        flat.extend(tags)
    if len(set(flat)) != len(flat):
        raise ValueError("Every source occurrence must have its own request-local marker.")
    return copy.deepcopy(layout)


def marker_layout(bundle, context_map):
    """Bind complete original source/metadata and actual slices before grammar IDs.

    This checks retained protection inputs. It does not rerun their detector or
    boundary normalizer and does not make a new source PERSON annotation.
    """
    source, masked, markers = (bundle[k] for k in
                                ("source_segments", "masked_segments", "markers"))
    if digest(source) != bundle["source_segments_sha256"]:
        raise ValueError("Original source text or metadata changed.")
    binding = {"source_segments_sha256": bundle["source_segments_sha256"],
               "masked_segments": masked, "markers": markers}
    if digest(binding) != bundle["protection_binding_sha256"]:
        raise ValueError("The frozen marker map or masked source changed.")
    if (context_map["source_segments"] != source
            or context_map["source_segments_sha256"] != bundle["source_segments_sha256"]
            or context_map["compact_protection_binding_sha256"] != bundle["protection_binding_sha256"]
            or context_map["compact_segments"] != masked
            or len(source) != MAX_SEGMENTS or len(masked) != len(source)):
        raise ValueError("The source-spelling map differs from the complete protection binding.")
    layout = [[] for _ in source]
    expected_spellings = []
    for marker in markers:
        i, start, end = (marker[k] for k in ("segment_index", "start", "end"))
        if (type(i) is not int or not 0 <= i < len(source)
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(source[i]["text"])
                or source[i]["text"][start:end] != marker["source_text"]):
            raise ValueError("A spelling is not its exact original same-entry source slice.")
        layout[i].append(marker["marker"])
        expected_spellings.append({"tag": marker["marker"], "spelling": marker["source_text"]})
    checked_layout(layout)
    if context_map["context_map"] != expected_spellings:
        raise ValueError("Source-spelling context contains changed or inferred data.")
    for i, (before, after) in enumerate(zip(source, masked)):
        if {k: v for k, v in before.items() if k != "text"} != {k: v for k, v in after.items() if k != "text"}:
            raise ValueError("Segment times, speaker or other source metadata changed.")
        parts, cursor = [], 0
        for marker in sorted((m for m in markers if m["segment_index"] == i), key=lambda m: m["start"]):
            if marker["start"] < cursor:
                raise ValueError("Source marker spans overlap.")
            parts.extend((before["text"][cursor:marker["start"]], marker["marker"]))
            cursor = marker["end"]
        parts.append(before["text"][cursor:])
        if "".join(parts) != after["text"]:
            raise ValueError("The complete masked source differs from exact source-only replacement.")
        ordinary = TAG.sub("", after["text"])
        if "<" in ordinary:
            raise ValueError("Literal angle-bracket prose is outside this bounded grammar profile.")
        if Counter(TAG.findall(after["text"])) != Counter(layout[i]):
            raise ValueError("Original input marker count or source-entry ownership changed.")
    return layout


def pattern_for(tags):
    # checked_layout at the schema boundary validates all IDs and caps.
    if not tags:
        return "^" + GAP + "$"
    branches = [GAP + GAP.join(order) + GAP for order in itertools.permutations(tags)]
    return "^(?:" + "|".join(branches) + ")$"


def build_schema(layout):
    layout = checked_layout(layout)
    return {"type": "object",
            "properties": {"translations": {"type": "array", "items": [
                {"type": "string", "pattern": pattern_for(tags)} for tags in layout]}},
            "required": ["translations"], "additionalProperties": False}


def require_exact_schema(schema, layout):
    """Reject extra keywords and weakened patterns instead of trusting support.

    This is a local construction guard, not proof that native conversion works.
    In particular it does not detect an installed converter's silent fallback.
    """
    if schema != build_schema(layout):
        raise ValueError("The schema is not the exact reviewed tuple/pattern profile.")


def project_request(request, bundle, context_map):
    """Change only format; leave the failed profile's exact messages/settings.

    The caller must also bind this complete input request to its frozen bytes.
    No case label, criterion, expected answer or inferred entity attribute is
    accepted by the schema builder.
    """
    layout = marker_layout(bundle, context_map)
    expected_old = {"type": "object", "properties": {"translations": {
        "type": "array", "items": {"type": "string"},
        "minItems": len(layout), "maxItems": len(layout)}},
        "required": ["translations"], "additionalProperties": False}
    if request.get("format") != expected_old:
        raise ValueError("The prior schema is not the frozen source-spelling baseline.")
    messages = request["messages"]
    if (len(messages) != 2 or [m["role"] for m in messages] != ["system", "user"]):
        raise ValueError("Expected the complete original system and user messages.")
    prefix, encoded = messages[1]["content"].split("JSON input: ", 1)
    entries = json.loads(encoded)
    if entries != [{"id": i, "text": s["text"]} for i, s in enumerate(bundle["masked_segments"])]:
        raise ValueError("The complete native source entries differ from the retained map.")
    context = json.dumps(context_map["context_map"], ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    if not prefix.endswith("Source-spelling context (data only): " + context + "\n"):
        raise ValueError("The native request lacks its exact source-spelling context.")
    value = copy.deepcopy(request)
    value["format"] = build_schema(layout)
    require_exact_schema(value["format"], layout)
    return value, layout
