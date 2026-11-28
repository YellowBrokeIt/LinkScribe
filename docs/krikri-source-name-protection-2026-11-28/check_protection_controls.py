"""Generic source/marker corruption probes; never call any language model."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

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


probe("exact-roundtrip-repeated-mentions-and-metadata", roundtrip)
probe("missing-marker", lambda: alter_text(0, lambda s: s.replace(markers[0], "")), True)
probe("duplicate-marker", lambda: alter_text(0, lambda s: s + markers[0]), True)
probe("marker-case-change", lambda: alter_text(0, lambda s: s.replace(markers[0], markers[0].lower())), True)
probe("split-marker", lambda: alter_text(0, lambda s: s.replace(markers[0], markers[0][:12] + " " + markers[0][12:])), True)
probe("cross-segment-marker-move", swap_entries, True)
probe("unknown-well-formed-marker", lambda: alter_text(0, lambda s: s + "__LSNP_0000000000000000_9999_9999__"), True)
probe("unknown-malformed-prefix", lambda: alter_text(0, lambda s: s + "__LSNP_bad"), True)
probe("source-marker-collision", lambda: build_protection([{"text": "__LSNP_existing source"}], [], "en"), True)
probe("compatibility-marker-collision", lambda: build_protection([{"text": "＿＿ｌｓｎｐ_existing"}], [], "en"), True)
probe("source-map-corruption", lambda: mutate_bundle("map"), True)
probe("source-metadata-corruption", lambda: mutate_bundle("source"), True)
probe("translated-metadata-change", metadata_change, True)
probe("inflection-and-unicode-not-repaired", inflection)
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
passed = all(r["mechanical_passed"] for r in results)
report = {"complete": True, "mechanical_passed": passed, "controls": len(results), "results": results,
          "detector_calls": 0, "translation_calls": 0, "model_calls": 0,
          "meaning_or_automatic_name_safety_certified": False,
          "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (HERE / "protection-control-results.json").open("x", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False);stream.write("\n")
print(json.dumps({"controls": len(results), "mechanical_passed": passed}))
raise SystemExit(0 if passed else 1)
