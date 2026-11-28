"""Pure failure/durability checks for the live-summary resource wrapper."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import measure_summary_memory as monitor


def make_proc(tmp_path, membership="/tenant/job"):
    proc = tmp_path / "proc"
    process = proc / "42"
    process.mkdir(parents=True)
    mount = tmp_path / "cgroup mount"
    mount.mkdir()
    (process / "cgroup").write_text("0::" + membership + "\n")
    escaped = str(mount).replace(" ", "\\040")
    (process / "mountinfo").write_text(f"1 2 0:1 /tenant {escaped} rw - cgroup2 cgroup rw\n")
    return proc, mount


def test_cgroup_resolution_uses_membership_mount_root_and_escaped_mount(tmp_path):
    proc, mount = make_proc(tmp_path)
    assert monitor.cgroup_event_paths(42, proc) == [
        mount / "job/memory.events", mount / "job/memory.events.local"]
    (proc / "42/cgroup").write_text("0::/other/job\n")
    assert monitor.cgroup_event_paths(42, proc) == []
    (proc / "42/cgroup").write_text("4:memory:/tenant/job\n")
    assert monitor.cgroup_event_paths(42, proc) == []


def test_missing_oom_evidence_is_unavailable_instead_of_zero(tmp_path):
    proc, mount = make_proc(tmp_path)
    result = monitor.oom_snapshot([42, 42], proc)
    assert result["files"] == {}
    assert len(result["unavailable"]) == 3
    (proc / "vmstat").write_text("pgfault 99\noom_kill 7\n")
    group = mount / "job"
    group.mkdir()
    (group / "memory.events").write_text("high 3\noom 2\noom_kill 1\n")
    result = monitor.oom_snapshot([42], proc)
    assert result["files"][str(proc / "vmstat")] == {
        "scope": "host_global", "counters": {"oom_kill": 7}}
    assert result["files"][str(group / "memory.events")] == {
        "scope": "process_cgroup", "counters": {"oom": 2, "oom_kill": 1}}
    assert len(result["unavailable"]) == 1  # Local file absence stays explicit.


def test_oom_deltas_never_synthesize_missing_counters_and_mark_resets():
    before = {"files": {"host": {"scope": "host_global", "counters": {"oom_kill": 7}},
                        "gone": {"scope": "process_cgroup", "counters": {"oom": 2}}}}
    after = {"files": {"host": {"scope": "host_global", "counters": {"oom_kill": 1}}}}
    assert monitor.oom_deltas(before, after) == {
        "host": {"scope": "host_global", "counters": {"oom_kill": -6},
                 "counter_reset_or_scope_change": True}}


def test_invalid_checkpoint_preserves_previous_bytes_and_removes_temporary(tmp_path):
    output = tmp_path / "report.json"
    monitor.checkpoint(output, {"complete": False, "text": "\ud800"})
    before = output.read_bytes()
    assert json.loads(before)["text"] == "\ud800"
    with pytest.raises(ValueError):
        monitor.checkpoint(output, {"bad": float("nan")})
    assert output.read_bytes() == before
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("change", [
    {"complete": False}, {"evaluator_exit_code": 1}, {"summary_report_complete": False},
    {"source_unchanged": False}, {"corpus_unchanged": False},
    {"memory": {"measurement_complete": False}}, {"memory_budget_passed": False},
    {"error": {"type": "TimeoutError"}}, {"cleanup_errors": ["Sampler did not stop"]},
])
def test_process_or_evidence_failures_cannot_be_accepted(change):
    report = {"complete": True, "evaluator_exit_code": 0, "summary_report_complete": True,
              "source_unchanged": True, "corpus_unchanged": True,
              "memory": {"measurement_complete": True}, "memory_budget_passed": True}
    assert monitor.accepted(report) is True
    report.update(change)
    assert monitor.accepted(report) is False


def test_endpoint_setup_failure_retains_incomplete_report_and_stops_sampler(monkeypatch, tmp_path):
    events = []

    class Sampler:
        def __init__(self, pid):
            events.append(("pid", pid))

        def start(self):
            events.append("start")

        def verify_endpoint(self, url):
            raise ValueError("The daemon does not own this endpoint")

        def stop(self):
            events.append("stop")

        def snapshot(self):
            return {"measurement_complete": False, "peak_combined_rss_mib": 3}

    monkeypatch.setattr(monitor, "ProcessMemory", Sampler)
    monkeypatch.setattr(monitor, "oom_snapshot", lambda *_: {"files": {}, "unavailable": ["synthetic"]})
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda *_a, **_k: pytest.fail("No evaluator after bad setup"))
    output = tmp_path / "memory.json"
    assert monitor.main(["--output", str(output), "--summary-output", str(tmp_path / "summary.json"),
                         "--ollama-pid", "42"]) == 1
    report = json.loads(output.read_text())
    assert events == [("pid", 42), "start", "stop"]
    assert report["complete"] is False and report["passed"] is False
    assert report["error"]["type"] == "ValueError" and report["cleanup_errors"] == []


def test_interruption_keeps_periodic_checkpoint_and_terminates_only_owned_child(monkeypatch, tmp_path):
    output, summary = tmp_path / "memory.json", tmp_path / "summary.json"
    events = []
    child = SimpleNamespace(pid=333, returncode=None, poll=lambda: None)

    class Sampler:
        def __init__(self, pid):
            self.state = {}
            self.psutil = SimpleNamespace(virtual_memory=lambda: SimpleNamespace(total=100))
            self.daemon = SimpleNamespace(environ=lambda: {"secret": "never-record", "LLAMA_ARG_CACHE_RAM": "0"})

        def start(self):
            events.append("start")

        def verify_endpoint(self, url):
            events.append("verified")

        def stop(self):
            events.append("stop")

        def snapshot(self):
            return {"measurement_complete": "stop" in events, "peak_combined_rss_mib": 17}

    def interrupt(seconds):
        partial = json.loads(output.read_text())
        assert partial["complete"] is False and partial["evaluator_pid"] == child.pid
        assert partial["memory"]["peak_combined_rss_mib"] == 17
        raise KeyboardInterrupt()

    def terminate(actual, _):
        assert actual is child
        events.append("terminate-evaluator")
        child.returncode = -15

    monkeypatch.setattr(monitor, "ProcessMemory", Sampler)
    monkeypatch.setattr(monitor, "oom_snapshot", lambda *_: {"files": {}, "unavailable": ["synthetic"]})
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda *_a, **_k: child)
    monkeypatch.setattr(monitor.time, "sleep", interrupt)
    monkeypatch.setattr(monitor, "terminate_child", terminate)
    assert monitor.main(["--output", str(output), "--summary-output", str(summary), "--ollama-pid", "42"]) == 1
    report = json.loads(output.read_text())
    assert events == ["start", "verified", "terminate-evaluator", "stop"]
    assert report["error"]["type"] == "KeyboardInterrupt"
    assert report["complete"] is False and report["passed"] is False
    assert report["evaluator_exit_code"] == -15
    assert "secret" not in json.dumps(report)
