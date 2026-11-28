"""Verify rejection-only syntax fix leaves all six prepared requests unchanged."""
import hashlib
import json
from pathlib import Path

from protection import build_protection

HERE = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
identities = {}
for name in ("marker-instruction.txt", "enhancements-context4096.py", "protection-inputs.json",
             "protected-source-cases.json", "expected-requests.json", "token-estimates.json", "development-cases.json"):
    if sha(HERE / name) != sha(HERE / "initial-protocol-review" / name):
        raise ValueError("Scanner revision changed a frozen input or estimate: " + name)
    identities[name] = sha(HERE / name)
cases = json.loads((HERE / "protection-inputs.json").read_text())["cases"]
checks = []
for case in cases:
    original = case["bundle"]
    actual = build_protection(original["source_segments"], case["raw_entities"], original["source_language"])
    if actual != original:
        raise ValueError("Scanner correction changed an original source map.")
    checks.append({"id":case["id"],"entire_protection_bundle_equal":True})
report = {"complete":True,"cases":checks,"unchanged_file_sha256":identities,
          "correction":"Reject residual/source opening and closing reserved prefixes, including spacing; no output repair.",
          "model_loads":0,"native_api_calls":0,"generation_calls":0,
          "runner_sha256":sha(Path(__file__))}
with (HERE / "syntax-revision-verification.json").open("x") as stream:
    json.dump(report,stream,indent=2);stream.write("\n")
print(json.dumps({"complete":True,"source_maps_unchanged":len(checks),"requests_and_token_estimates_unchanged":True}))
