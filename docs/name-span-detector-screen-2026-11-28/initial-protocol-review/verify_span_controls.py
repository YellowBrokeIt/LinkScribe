"""Exercise span corruption rejection in the declared existing detector interpreter."""
import copy
import json
from common import HERE, save, sha, utc
from native_worker import validate_entities

output = HERE / "span-control-probes.json"
if output.exists():
    raise ValueError("Refusing to overwrite the declared-interpreter span probes.")
source = {"source_text": "Zoë saw Zoë.", "segment_offsets": [{"segment_index": 0, "start": 0, "end": 12}]}
raw = [{"start": 0, "end": 3, "text": "Zoë", "label": "person", "score": .9},
       {"start": 8, "end": 11, "text": "Zoë", "label": "person", "score": .8}]
spans = validate_entities(raw, source)
results = [{"control": "distinct_repeated_source_occurrences", "passed": len(spans) == 2 and spans[1]["segment_start"] == 8}]
wrong_text = copy.deepcopy(raw); wrong_text[0]["text"] = "Zoe"
wrong_label = copy.deepcopy(raw); wrong_label[0]["label"] = "organization"
wrong_score = copy.deepcopy(raw); wrong_score[0]["score"] = float("nan")
probes = [("nonexact_source", wrong_text, source), ("wrong_label", wrong_label, source),
          ("nonfinite_score", wrong_score, source), ("overlap", [raw[0], raw[0]], source),
          ("cross_segment", [{"start":0,"end":7,"text":"One\nTwo","label":"person","score":.9}],
           {"source_text":"One\nTwo","segment_offsets":[{"segment_index":0,"start":0,"end":3},{"segment_index":1,"start":4,"end":7}]}),
          ("partial_grapheme", [{"start":0,"end":3,"text":"Zoe","label":"person","score":.9}],
           {"source_text":"Zoe\u0308","segment_offsets":[{"segment_index":0,"start":0,"end":4}]})]
for name, entities, text in probes:
    try:
        validate_entities(entities, text)
    except ValueError:
        rejected = True
    else:
        rejected = False
    results.append({"control":name,"passed":rejected})
report={"created_at":utc(),"passed":all(item["passed"] for item in results),"results":results,
        "model_imports":0,"detector_calls":0,"translation_calls":0,"original_cases_used":False,
        "worker_sha256":sha(HERE/'native_worker.py'),"script_sha256":sha(__file__),
        "scope":"Source-span integrity only; no detector accuracy claim."}
save(output,report)
print(json.dumps({"passed":report['passed'],"controls":len(results)}))
raise SystemExit(int(not report['passed']))
