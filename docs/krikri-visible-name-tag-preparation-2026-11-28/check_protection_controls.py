"""Generic source/marker corruption probes; never call any language model."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unicodedata

from protection import build_protection, restore_segments, strict_response_strings

HERE = Path(__file__).resolve().parent
results = []


def probe(name, action, reject=False, semantic_limit=None):
    try:
        value = action()
        results.append({"id": name, "mechanical_passed": not reject, "observed": value,
                        "semantic_limit": semantic_limit})
    except Exception as error:
        results.append({"id": name, "mechanical_passed": reject and isinstance(error, (ValueError, guard.EnhancementError)),
                        "observed_error": {"type": type(error).__name__, "message": str(error)},
                        "semantic_limit": semantic_limit})


spec = importlib.util.spec_from_file_location("unchanged_guard_control", HERE / "enhancements-production.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
segments = [{"start": 0.25, "end": 3.5, "speaker": "Speaker A", "text": "Η Δανάη μίλησε στη Δανάη."},
            {"start": 3.5, "end": 6.0, "speaker": "Speaker B", "text": "Ο Πέτρος άκουσε."}]
source = "\n".join(s["text"] for s in segments)
raw = []
for start, text in ((source.index("Δανάη"), "Δανάη"), (source.rindex("Δανάη"), "Δανάη"),
                    (source.index("Πέτρος"), "Πέτρος")):
    raw.append({"start": start, "end": start + len(text), "text": text, "label": "person", "score": 0.91})
bundle = build_protection(segments, raw, "el")
markers = [item["marker"] for item in bundle["markers"]]


def roundtrip():
    restored, audit = restore_segments(bundle, bundle["masked_segments"])
    assert restored == segments and len(set(markers)) == 3
    assert bundle["masked_segments"][0]["text"].startswith("Η " + markers[0])
    return {"metadata_and_text_exact": True, "distinct_markers_for_repeated_name": True, "article_unmasked": True}


def alter_text(index, transform):
    value = copy.deepcopy(bundle["masked_segments"])
    value[index]["text"] = transform(value[index]["text"])
    return restore_segments(bundle, value)


def swap_entries():
    value = copy.deepcopy(bundle["masked_segments"])
    a, b = value[0]["text"], value[1]["text"]
    value[0]["text"] = a.replace(markers[0], markers[2])
    value[1]["text"] = b.replace(markers[2], markers[0])
    return restore_segments(bundle, value)


def mutate_bundle(field):
    value = copy.deepcopy(bundle)
    if field == "map":
        value["markers"][0]["source_text"] = "Διονύσης"
    else:
        value["source_segments"][0]["speaker"] = "Other"
    return restore_segments(value, value["masked_segments"])


def metadata_change():
    value = copy.deepcopy(bundle["masked_segments"]);value[0]["end"] = 9.0
    return restore_segments(bundle, value)


def inflection():
    s = [{"start": 0, "end": 1, "text": "της Δανα\u0301ης"}]
    r = [{"start": 0, "end": len(s[0]["text"]), "text": s[0]["text"], "label": "person", "score": 0.9}]
    b = build_protection(s, r, "el");restored, _ = restore_segments(b, b["masked_segments"])
    assert restored == s and b["markers"][0]["source_text"] == "Δανα\u0301ης"
    return {"exact_decomposed_inflection_retained": True}


def normalize_inner_name():
    s = [{"start": 0, "end": 1, "text": "της Δανα\u0301ης"}]
    r = [{"start": 0, "end": len(s[0]["text"]), "text": s[0]["text"], "label": "person", "score": 0.9}]
    b = build_protection(s, r, "el")
    value = copy.deepcopy(b["masked_segments"])
    value[0]["text"] = unicodedata.normalize("NFC", value[0]["text"])
    return restore_segments(b, value)


def apostrophe_and_prefixes():
    text = "Jean-Luc O’Rourke spoke."
    name = "Jean-Luc O’Rourke"
    s = [{"text": text, "speaker": "A", "start": 2.0, "end": 4.0}]
    r = [{"start": 0, "end": len(name), "text": name, "label": "person", "score": 0.9}]
    b = build_protection(s, r, "en")
    restored, _ = restore_segments(b, b["masked_segments"])
    assert restored == s and b["markers"][0]["source_text"] == name
    return {"multiword_hyphen_and_curly_apostrophe_unchanged": True}


def guard_rejects_foreign():
    restored, _ = alter_text(0, lambda s: s + " שלום")
    return guard._translation_result(segments, restored, "el", "en")


def actor_swap_limit():
    text = "Η Δανάη μίλησε στον Πέτρο."
    people = [{"start": text.index(name), "end": text.index(name) + len(name), "text": name,
               "label": "person", "score": 0.91} for name in ("Δανάη", "Πέτρο")]
    example = build_protection([{"text": text}], people, "el")
    tokens = [item["marker"] for item in example["markers"]]
    value = [{"text": tokens[1] + " spoke to " + tokens[0] + "."}]
    restored, _ = restore_segments(example, value)
    return {"markers_each_once_in_same_entry": True, "meaning_not_certified": True,
            "restored_text": restored[0]["text"]}


def ordinary_pronoun_limit():
    text = "Η Δανάη μίλησε. Εκείνη έφυγε."
    name = "Δανάη"
    people = [{"start": text.index(name), "end": text.index(name) + len(name),
               "text": name, "label": "person", "score": 0.91}]
    example = build_protection([{"text": text}], people, "el")
    token = example["markers"][0]["marker"]
    restored, _ = restore_segments(example, [{"text": token + " spoke. He left."}])
    return {"whole_name_copied_exactly": True, "meaning_not_certified": True,
            "restored_text": restored[0]["text"]}


probe("exact-roundtrip-repeated-mentions-and-metadata", roundtrip)
probe("missing-marker", lambda: alter_text(0, lambda s: s.replace(markers[0], "")), True)
probe("duplicate-marker", lambda: alter_text(0, lambda s: s + markers[0]), True)
probe("marker-case-change", lambda: alter_text(0, lambda s: s.replace(markers[0], markers[0].upper())), True)
probe("split-marker", lambda: alter_text(0, lambda s: s.replace(markers[0], markers[0][:2] + " " + markers[0][2:])), True)
probe("cross-segment-marker-move", swap_entries, True)
probe("unknown-well-formed-marker", lambda: alter_text(0, lambda s: s + "<x9999>Dana</x9999>"), True)
probe("unknown-malformed-prefix", lambda: alter_text(0, lambda s: s + "<xbroken>"), True)
probe("extra-closing-tag-after-valid-marker", lambda: alter_text(0, lambda s: s + " </x0>"), True)
probe("extra-spaced-closing-tag-after-valid-marker", lambda: alter_text(0, lambda s: s + " < / x0 >"), True)
probe("source-marker-collision", lambda: build_protection([{"text": "<x0/> pre-existing source"}], [], "en"), True)
probe("source-closing-tag-collision", lambda: build_protection([{"text": "</x0> pre-existing source"}], [], "en"), True)
probe("source-spaced-opening-tag-collision", lambda: build_protection([{"text": "< x0 /> pre-existing source"}], [], "en"), True)
probe("compatibility-marker-collision", lambda: build_protection([{"text": "＜Ｘ０／＞ pre-existing source"}], [], "en"), True)
probe("source-visible-pair-collision", lambda: build_protection([{"text": "<x0>Dana</x0>"}], [], "en"), True)
probe("source-format-separated-closing-collision", lambda: build_protection([{"text": "<\u200b/\u200bx0>"}], [], "en"), True)
probe("source-map-corruption", lambda: mutate_bundle("map"), True)
probe("source-metadata-corruption", lambda: mutate_bundle("source"), True)
probe("translated-metadata-change", metadata_change, True)
probe("inflection-and-unicode-not-repaired", inflection)
probe("inner-unicode-normalization-rejected", normalize_inner_name, True)
probe("apostrophe-hyphen-and-multiword-name-exact", apostrophe_and_prefixes)
probe("empty-entity-list", lambda: build_protection([{"text": "No personal names here."}], [], "en")["full_source_roundtrip_exact"])
probe("strict-json-valid", lambda: strict_response_strings('{"translations":["one","two"]}', 2))
probe("strict-json-extra-property", lambda: strict_response_strings('{"translations":["one"],"extra":1}', 1), True)
probe("strict-json-duplicate-property", lambda: strict_response_strings('{"translations":["one"],"translations":["two"]}', 1), True)
probe("strict-json-wrong-count", lambda: strict_response_strings('{"translations":["one"]}', 2), True)
probe("strict-json-wrong-type", lambda: strict_response_strings('{"translations":[1]}', 1), True)
probe("strict-json-prose-wrapper", lambda: strict_response_strings('Answer: {"translations":["one"]}', 1), True)
probe("restored-production-script-guard", guard_rejects_foreign, True)
probe("restored-production-copy-guard", lambda: guard._translation_result(segments, restore_segments(bundle, bundle["masked_segments"])[0], "el", "en"), True)
probe("within-segment-role-order-not-certified", actor_swap_limit, semantic_limit="Once-only marker accounting cannot certify who acts on whom; independent meaning review remains mandatory.")
probe("ordinary-pronoun-not-certified", ordinary_pronoun_limit,
      semantic_limit="An unchanged visible name does not certify pronouns or grammatical agreement outside the span.")

# Only output wrappers may be removed. Every modified inner source string fails,
# including changes that a human might consider an acceptable transliteration.
probe("localized-inner-name-rejected-not-restored", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0>Danae</x0>")), True)
probe("inner-case-change-rejected", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0>δανάη</x0>")), True)
probe("inner-whitespace-change-rejected", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0> Δανάη </x0>")), True)
probe("empty-inner-name-rejected", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0></x0>")), True)
probe("inner-name-repetition-rejected", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0>Δανάη Δανάη</x0>")), True)
probe("missing-closing-wrapper", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0>Δανάη")), True)
probe("wrong-closing-index", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0>Δανάη</x7>")), True)
probe("nested-pair-rejected", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0><x8>Δανάη</x8></x0>")), True)
probe("crossing-pairs-rejected", lambda: alter_text(0, lambda s: s.replace(markers[0], "<x0><x8>Δανάη</x0></x8>")), True)
probe("stray-opening-prefix", lambda: alter_text(0, lambda s: s + " <x"), True)
probe("escaped-pair-not-decoded-or-repaired", lambda: alter_text(0, lambda s: s.replace(markers[0], "&lt;x0&gt;Δανάη&lt;/x0&gt;")), True)
probe("tag-attribute-not-accepted", lambda: alter_text(0, lambda s: s.replace(markers[0], '<x0 role="name">Δανάη</x0>')), True)
probe("unwrapped-extra-name-not-certified", lambda: alter_text(0, lambda s: s + " Δανάη"),
      semantic_limit="Additional unwrapped ordinary prose, including a copied name, remains a semantic addition despite intact whole-span accounting.")

def source_bound_maps():
    alternate = build_protection([{"text": "Δανάη"}],
                                 [{"start": 0, "end": 5, "text": "Δανάη", "label": "person", "score": 0.91}], "el")
    assert alternate["markers"][0]["marker"] == bundle["markers"][0]["marker"]
    assert alternate["source_binding_sha256"] != bundle["source_binding_sha256"]
    assert alternate["protection_binding_sha256"] != bundle["protection_binding_sha256"]
    return {"tags_are_request_local": True, "same_name_pair_can_recur_in_different_requests": True,
            "source_map_identity_bound_outside_tag": True,
            "cross_request_semantic_identity_not_certified_by_tag_alone": True}

probe("request-local-tags-external-source-map-binding", source_bound_maps,
      semantic_limit="Compact occurrence tags can repeat across requests; the wrapper must bind each actual request to its exact source/map. Marker strings alone do not authenticate cross-request meaning.")

passed = all(r["mechanical_passed"] for r in results)
report = {"complete": True, "mechanical_passed": passed, "controls": len(results), "results": results,
          "detector_calls": 0, "translation_calls": 0, "model_calls": 0,
          "meaning_or_automatic_name_safety_certified": False,
          "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (HERE / "protection-control-results.json").open("x", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False);stream.write("\n")
print(json.dumps({"controls": len(results), "mechanical_passed": passed}))
raise SystemExit(0 if passed else 1)
