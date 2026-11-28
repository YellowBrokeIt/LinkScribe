"""Resource accounting must compare simultaneous samples, not separate peaks."""
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from smoke_full_local_workflow import ProcessMemory, installed_model, listening_endpoint, update_peaks


def test_combined_peak_is_concurrent_and_duplicate_pid_is_counted_once():
    state = {"sample_count": 0, "pss_available_for_every_sample": True}
    first = [{"pid": 1, "rss_bytes": 100, "pss_bytes": 80}, {"pid": 2, "rss_bytes": 20, "pss_bytes": 10}]
    update_peaks(state, [*first, first[0]], 0)
    update_peaks(state, [{"pid": 1, "rss_bytes": 80, "pss_bytes": 60},
                         {"pid": 2, "rss_bytes": 30, "pss_bytes": 25}], 1)
    assert state["peak_rss_sample"]["rss_bytes"] == 120  # Not 100+30 or duplicated PID 1.
    assert state["peak_pss_sample"]["pss_bytes"] == 90
    assert state["sample_count"] == 2


def test_partial_pss_is_not_reported_as_complete_process_tree_memory():
    state = {"sample_count": 0, "pss_available_for_every_sample": True}
    update_peaks(state, [{"pid": 1, "rss_bytes": 100, "pss_bytes": 80},
                         {"pid": 2, "rss_bytes": 20, "pss_bytes": None}], 0)
    assert state["peak_rss_sample"]["rss_bytes"] == 120
    assert state["pss_available_for_every_sample"] is False
    assert state.get("peak_pss_sample") is None


def test_model_identity_accepts_exact_or_latest_but_never_missing_digest():
    tags = {"models": [{"name": "qwen3:latest", "digest": "summary"},
                       {"name": "translategemma:4b", "digest": "translation"}]}
    assert installed_model(tags, "qwen3")["digest"] == "summary"
    assert installed_model(tags, "translategemma:4b")["digest"] == "translation"
    with pytest.raises(ValueError, match="not installed"):
        installed_model(tags, "translategemma:12b")
    with pytest.raises(ValueError, match="digest"):
        installed_model({"models": [{"name": "qwen3:latest"}]}, "qwen3")


def test_wrong_daemon_listener_cannot_support_combined_memory_claim():
    listener = SimpleNamespace(status="LISTEN", laddr=SimpleNamespace(ip="127.0.0.1", port=11435))
    with pytest.raises(ValueError, match="not listening"):
        listening_endpoint([listener], "http://127.0.0.1:11434")
    listener.laddr.port = 11434
    assert listening_endpoint([listener], "http://127.0.0.1:11434") == [{"address": "127.0.0.1", "port": 11434}]
    listener.laddr.ip = "192.168.1.10"
    with pytest.raises(ValueError, match="not listening"):
        listening_endpoint([listener], "http://127.0.0.1:11434")


def test_unstopped_sampler_cannot_publish_complete_final_memory():
    sampler = object.__new__(ProcessMemory)
    sampler.stopped = threading.Event()
    sampler.lock = threading.Lock()
    sampler.accept_samples = True
    sampler.state = {"sample_count": 1, "endpoint_verified": True,
                     "errors": [], "pss_available_for_every_sample": True}
    sampler.thread = SimpleNamespace(join=lambda timeout: None, is_alive=lambda: True)
    sampler.stop()
    assert sampler.accept_samples is False
    assert sampler.snapshot()["measurement_complete"] is False
    assert "did not stop" in sampler.state["errors"][0]
