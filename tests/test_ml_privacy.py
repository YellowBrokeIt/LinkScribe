"""Model startup must opt out before the native runtime is initialized."""
import os
from pathlib import Path
import subprocess
import sys


def test_application_sets_early_model_runtime_opt_outs():
    # Use a fresh interpreter: checking an already-imported app cannot establish
    # that environment flags were present before the first native import.
    program = '''
import builtins, os
original = builtins.__import__
def checked(name, *args, **kwargs):
    if name.split('.')[0] in {'onnxruntime', 'faster_whisper', 'huggingface_hub'}:
        assert os.environ.get('ORT_DISABLE_TELEMETRY') == '1'
        assert os.environ.get('HF_HUB_DISABLE_TELEMETRY') == '1'
    return original(name, *args, **kwargs)
builtins.__import__ = checked
import app
assert os.environ['ORT_DISABLE_TELEMETRY'] == '1'
assert os.environ['HF_HUB_DISABLE_TELEMETRY'] == '1'
'''
    environment = dict(os.environ, ORT_DISABLE_TELEMETRY="0", HF_HUB_DISABLE_TELEMETRY="0")
    subprocess.run([sys.executable, "-c", program], cwd=Path(__file__).resolve().parents[1],
                   env=environment, check=True, capture_output=True, text=True, timeout=30)


def test_whisper_disables_runtime_events_before_constructing_model(monkeypatch):
    from types import SimpleNamespace
    import app

    order = []
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(
        disable_telemetry_events=lambda: order.append("opt-out")))
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(
        WhisperModel=lambda *args, **kwargs: order.append("model")))
    app._whisper_model.cache_clear()
    try:
        app._whisper_model("tiny")
        assert order == ["opt-out", "model"]
    finally:
        app._whisper_model.cache_clear()
