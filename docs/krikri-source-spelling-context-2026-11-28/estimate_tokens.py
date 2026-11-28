"""Reference-tokenizer estimates only; no native runtime or model is loaded."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import time

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:4])
signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("30-second tokenizer estimate limit")))
signal.alarm(30)

from tokenizers import Tokenizer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / "docs/krikri-compact-tag-screen-2026-11-28"
REFERENCE = Path("/workspace/scratch/94360995dd61/linkscribe-krikri-runtime/reference-tokenizer/tokenizer.json")
EXPECTED_SHA = "1b12728a215cde26d96f3add66a7a10f0e47147afbf2e677cc0a70ba49228ada"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started = time.monotonic()
    if sha(REFERENCE) != EXPECTED_SHA or REFERENCE.stat().st_size != 19508014:
        raise ValueError("Existing official tokenizer identity changed.")
    tokenizer = Tokenizer.from_file(str(REFERENCE))
    previous = json.loads((PRIOR / "prepare.json").read_bytes())["prompts"]
    requests = json.loads((HERE / "expected-requests.json").read_bytes())
    report = {"schema_version":1,"complete":False,"estimate_only_not_current_native_accounting":True,
              "tokenizer_sha256":EXPECTED_SHA,"tokenizer_source":"Pinned official publisher tokenizer already verified against selected GGUF",
              "runner_sha256":sha(Path(__file__)),"prior_native_prepare_sha256":sha(PRIOR / "prepare.json"),
              "new_request_sha256":sha(HERE / "expected-requests.json"),"prior_vectors_equal":[],"cases":[],
              "model_loads":0,"native_api_calls":0,"generation_calls":0,"new_downloads":0}

    def encode(rendered, native_add_special):
        # Reproduce the verified native BOS policy rather than assuming the
        # publisher tokenizer's optional postprocessor behaves like llama.cpp.
        ids = tokenizer.encode(rendered, add_special_tokens=False).ids
        if native_add_special:
            ids.insert(0, 128000)
        if not ids or ids[0] != 128000 or ids.count(128000) != 1:
            raise ValueError("The complete prompt lacks exactly one native BOS.")
        return ids

    try:
        for old, new in zip(previous, requests):
            if old["id"] != new["id"]:
                raise ValueError("Source order changed before token estimates.")
            native_tokens = encode(old["rendered_prompt"], old["tokenize_add_special"])
            if native_tokens != old["tokens"]:
                raise ValueError("Reference tokenizer does not reproduce a complete retained native token vector.")
            report["prior_vectors_equal"].append({"id":old["id"],"tokens":len(native_tokens),"entire_vector_equal":True})
            rendered = old["rendered_prompt"]
            for old_message, new_message in zip(old["request"]["messages"], new["request"]["messages"]):
                if old_message["role"] != new_message["role"] or rendered.count(old_message["content"]) != 1:
                    raise ValueError("Cannot replace exactly the two complete messages in the retained native wrapper.")
                rendered = rendered.replace(old_message["content"], new_message["content"], 1)
            tokens = encode(rendered, old["tokenize_add_special"])
            if len(tokens) + 2048 + 1 > 4096:
                raise ValueError("Estimated complete prompt plus full output budget and end reserve does not fit.")
            report["cases"].append({"id":new["id"],"retained_native_layout":old["layout"],
                                    "retained_wrapper_date_not_refreshed":True,"estimated_rendered_prompt":rendered,
                                    "estimated_tokens":tokens,"estimated_prompt_tokens":len(tokens),
                                    "context_tokens":4096,"maximum_output_tokens":2048,"end_token_reserve":1,
                                    "estimated_remaining_capacity":4096-len(tokens)-2048-1,
                                    "actual_native_preflight_still_required":True})
        report["tag_tokenizations"] = [{"tag":f"<x{i}/>","tokens":tokenizer.encode(f"<x{i}/>",add_special_tokens=False).ids}
                                       for i in range(6)]
        reserved = {128000,128001,128008,128009}
        if any(reserved.intersection(row["tokens"]) for row in report["tag_tokenizations"]):
            raise ValueError("A compact tag encodes to a native conversation boundary token.")
        report["complete"] = len(report["cases"]) == 6
    except Exception as error:
        report["error"] = {"type":type(error).__name__,"message":str(error)}
    finally:
        report["elapsed_seconds"] = time.monotonic()-started
        report["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        with (HERE / "token-estimates.json").open("x",encoding="utf-8") as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write("\n")
        print(json.dumps({"complete":report["complete"],"estimated_prompt_counts":[r["estimated_prompt_tokens"] for r in report["cases"]],
                          "prior_native_vectors_matched":len(report["prior_vectors_equal"]),"error":report.get("error"),
                          "model_loads":0,"generation_calls":0}))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
