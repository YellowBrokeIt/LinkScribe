"""Synthetic retained-report mutations; never construct or invoke a model."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("offline_contract", ROOT / "audit_retained_result.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
binding = json.loads((ROOT / "bindings.json").read_text(encoding="utf-8"))
EVIDENCE = Path(binding["retained_evidence_directory"]) / "artifact"
plan = json.loads((ROOT / "source/original-hosted-plan.json").read_text(encoding="utf-8"))
report = json.loads((EVIDENCE / "speaker-app-report.json").read_text(encoding="utf-8"))
execution = json.loads((EVIDENCE / "execution.json").read_text(encoding="utf-8"))
samples = [json.loads(line) for line in (EVIDENCE / "resource-samples.jsonl").read_text(encoding="utf-8").splitlines()]
contract = audit.load_function(ROOT / "source/controller-f2.py", "completed_contract", constructor_correction=True)


def reject_report(mutation):
    candidate = deepcopy(report)
    mutation(candidate)
    try:
        contract(plan, candidate)
    except (ValueError, KeyError):
        return
    raise AssertionError("Synthetic invalid report was accepted")


def test_corrected_constructor_preserves_other_runtime_conditions():
    contract(plan, report)
    for field, value in (("cpu_threads", 4), ("cpu_threads", 8), ("num_workers", 2),
                         ("actual_device", "cuda"), ("actual_compute_type", "float32")):
        reject_report(lambda row, f=field, v=value: row["model_initializations"][0].__setitem__(f, v))
    reject_report(lambda row: row["model_initializations"].append(deepcopy(row["model_initializations"][0])))


def test_no_resource_input_or_decoder_gate_is_relaxed():
    reject_report(lambda row: row.__setitem__("complete", False))
    reject_report(lambda row: row.__setitem__("elapsed_seconds", plan["total_worker_seconds"] + 0.1))
    reject_report(lambda row: row.__setitem__("peak_process_rss_bytes", plan["rss_limit_bytes"] + 1))
    reject_report(lambda row: row["phases"][0].__setitem__("elapsed_seconds", plan["phase_seconds"]["initialization"] + 0.1))
    reject_report(lambda row: row["audio"].__setitem__("sha256", "0" * 64))
    reject_report(lambda row: row["actual_transcribe_calls"][0]["options"].__setitem__("word_timestamps", True))
    reject_report(lambda row: row["model_resolutions"][0].__setitem__("revision_directory", "unfrozen"))


def test_group_accounting_and_launch_scope_remain_required():
    audit.final_resources(plan, execution, samples)
    cases = [
        (lambda e, s: e.__setitem__("cpu_affinity", [0, 1, 2, 3, 4])),
        (lambda e, s: s[0].__setitem__("complete", False)),
        (lambda e, s: s[0].__setitem__("read_errors", [{"pid": 2324, "error": "permission"}])),
        (lambda e, s: e.__setitem__("sampled_group_peak_rss_bytes", 0)),
        (lambda e, s: e["cleanup"].__setitem__("live_group_members_after_cleanup", [2324])),
    ]
    for mutation in cases:
        e, s = deepcopy(execution), deepcopy(samples)
        mutation(e, s)
        try:
            audit.final_resources(plan, e, s)
        except ValueError:
            continue
        raise AssertionError("Synthetic invalid resource evidence was accepted")
