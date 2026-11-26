"""Regression tests for local AI boundaries and complete long summaries."""
from __future__ import annotations

from contextlib import contextmanager
import http.server
import json
import threading
import urllib.error

import pytest

import diagnostics
import enhancements


@pytest.fixture(autouse=True)
def reset_translation_override(monkeypatch):
    monkeypatch.delenv("LINKSCRIBE_TRANSLATION_MODEL", raising=False)


@contextmanager
def http_server(reply, port=0):
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append((self.command, self.path, body))
            status, headers, response = reply(self.path, body)
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        do_GET = respond
        do_POST = respond

    class Server(http.server.ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    with Server(("127.0.0.1", port), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield server.server_port, requests
        finally:
            server.shutdown()
            worker.join(timeout=3)


def json_reply(value, status=200):
    return lambda _path, _body: (status, {"Content-Type": "application/json"},
                                json.dumps(value).encode("utf-8"))


def test_local_transcript_never_uses_environment_proxy(monkeypatch):
    response = {"message": {"content": json.dumps({"translations": ["Καλημέρα!"]})}}
    with http_server(json_reply({})) as (proxy_port, proxy_calls):
        with http_server(json_reply(response), 11434) as (_port, calls):
            monkeypatch.setenv("LINKSCRIBE_OLLAMA_URL", "http://127.0.0.1:11434")
            monkeypatch.setenv("http_proxy", f"http://127.0.0.1:{proxy_port}")
            monkeypatch.setenv("HTTP_PROXY", f"http://127.0.0.1:{proxy_port}")
            monkeypatch.setenv("no_proxy", "")
            monkeypatch.setenv("NO_PROXY", "")
            result = enhancements.translate_segments([
                {"start": 1, "end": 2, "text": "Good morning!", "speaker": "Speaker 1"}
            ], "el")
    assert not proxy_calls
    assert len(calls) == 2 and all(call[1] == "/api/chat" for call in calls)
    assert not enhancements.is_ollama_control_request(json.loads(calls[0][2]))
    assert enhancements.is_ollama_control_request(json.loads(calls[1][2]))
    assert result == [{"start": 1, "end": 2, "text": "Καλημέρα!", "speaker": "Speaker 1"}]


def test_local_ollama_does_not_follow_redirects(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_URL", "http://127.0.0.1:11434")
    with http_server(json_reply({})) as (target_port, target_calls):
        def redirect(_path, _body):
            return 302, {"Location": f"http://127.0.0.1:{target_port}/unexpected"}, b""
        with http_server(redirect, 11434):
            with pytest.raises(urllib.error.HTTPError):
                enhancements.local_ollama_json("/api/tags")
            with pytest.raises(enhancements.EnhancementError, match="rejected"):
                enhancements._ollama({"messages": []})
    assert not target_calls


@pytest.mark.parametrize("raw", [[], {"message": None}, {"message": {"content": "bad JSON"}}])
def test_invalid_ollama_response_is_a_readable_failure(monkeypatch, raw):
    monkeypatch.setattr(enhancements, "local_ollama_json", lambda *_args, **_kw: raw)
    with pytest.raises(enhancements.EnhancementError, match="invalid JSON"):
        enhancements._ollama({"messages": []})


def test_ollama_missing_model_has_actionable_error(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b")
    def missing(*_args, **_kw):
        raise urllib.error.HTTPError("http://127.0.0.1:11434/api/chat", 404, "not found", {}, None)
    monkeypatch.setattr(enhancements, "local_ollama_json", missing)
    with pytest.raises(enhancements.EnhancementError, match="ollama pull qwen3:4b"):
        enhancements._ollama({"messages": []})


def test_ollama_truncated_response_is_not_a_success(monkeypatch):
    monkeypatch.setattr(enhancements, "local_ollama_json", lambda *_args, **_kw: {
        "done_reason": "length", "message": {"content": '{"summary":"partial"}'}})
    with pytest.raises(enhancements.EnhancementError, match="response limit"):
        enhancements._ollama({"messages": []})


def test_long_summary_keeps_every_note_during_reduction(monkeypatch):
    notes = []
    reductions = []
    def model(payload):
        system, user = [message["content"] for message in payload["messages"]]
        if "chapter_title" in system:
            note = f"MARKER_{len(notes)} " + "x" * 2000
            notes.append(note)
            return {"notes": note, "chapter_title": "Section"}
        if "Condense" in system:
            reductions.append(user)
            return {"notes": " ".join(f"MARKER_{i}" for i in range(4) if f"MARKER_{i}" in user)}
        return {"summary": user, "key_points": ["Four sections"]}
    monkeypatch.setattr(enhancements, "_ollama", model)
    segments = [{"start": i * 10, "end": i * 10 + 5, "text": str(i) + "x" * 2000}
                for i in range(4)]
    result = enhancements.summarize_segments(segments)
    assert all(f"MARKER_{i}" in result["summary"] for i in range(4))
    assert reductions
    assert all(len(request.encode("utf-8")) <= enhancements.MAX_SUMMARY_INPUT_BYTES
               for request in reductions)
    assert [chapter["start"] for chapter in result["chapters"]] == [0, 10, 20, 30]


@pytest.mark.parametrize("notes", ["", "   ", "x" * 5001])
def test_empty_or_overlong_excerpt_notes_are_rejected(monkeypatch, notes):
    monkeypatch.setattr(enhancements, "_ollama", lambda _payload: {
        "notes": notes, "chapter_title": "Chapter"})
    with pytest.raises(enhancements.EnhancementError, match="excerpt summary|oversized summary notes"):
        enhancements.summarize_segments([{"start": 0, "end": 1, "text": "Hello " * 800}])


@pytest.mark.parametrize("response", [[], {"models": None}, {"models": "not a list"}])
def test_diagnostics_handles_malformed_model_lists(monkeypatch, response):
    monkeypatch.setattr(diagnostics, "local_ollama_json", lambda *_args, **_kw: response)
    result = diagnostics.report()
    assert not result["ollama"]["available"]
    assert not result["ollama"]["model_available"]


def test_diagnostics_detects_missing_model_and_real_audio_package(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_SPEAKER_BACKEND", "pyannote")
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("HF_TOKEN", "dummy-token-never-in-output")
    monkeypatch.setattr(diagnostics, "local_ollama_json", lambda *_args, **_kw: {"models": []})
    monkeypatch.setattr(diagnostics.importlib.util, "find_spec",
                        lambda name: None if name == "pyannote.audio" else object())
    result = diagnostics.report()
    assert result["ollama"]["available"]
    assert not result["ollama"]["model_available"]
    assert not result["speakers_configured"]
    assert any("ollama pull qwen3:4b" in warning for warning in result["warnings"])
    assert "dummy-token-never-in-output" not in json.dumps(result)


def test_diagnostics_recognizes_implicit_latest_model_tag(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3")
    monkeypatch.setattr(diagnostics, "local_ollama_json", lambda *_args, **_kw: {
        "models": [{"name": "qwen3:latest"}]})
    assert diagnostics.report()["ollama"]["model_available"]


@pytest.mark.parametrize("models,summary_available,translation_available", [
    (["qwen3:4b", "translategemma:4b"], True, True),
    (["qwen3:4b"], True, False),
    (["translategemma:4b"], False, True),
    ([], False, False),
])
def test_diagnostics_reports_task_model_availability_independently(
        monkeypatch, models, summary_available, translation_available):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "translategemma:4b")
    monkeypatch.setattr(diagnostics, "local_ollama_json", lambda *_args, **_kw: {
        "models": [{"name": model} for model in models]})
    result = diagnostics.report()
    info = result["ollama"]
    assert info["available"] is True
    assert info["model_configured"] == "qwen3:4b"
    assert info["translation_model_configured"] == "translategemma:4b"
    assert info["translation_profile"] == "translategemma"
    assert info["model_available"] is summary_available
    assert info["translation_model_available"] is translation_available
    missing = [message for message in result["warnings"] if "model is missing" in message]
    assert len(missing) == int(not summary_available) + int(not translation_available)
    if not summary_available:
        assert any("summary model" in message and "ollama pull qwen3:4b" in message for message in missing)
    if not translation_available:
        assert any("translation model" in message and "ollama pull translategemma:4b" in message for message in missing)


def test_diagnostics_does_not_duplicate_missing_inherited_model_warning(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setattr(diagnostics, "local_ollama_json", lambda *_args, **_kw: {"models": []})
    result = diagnostics.report()
    assert not result["ollama"]["model_available"]
    assert not result["ollama"]["translation_model_available"]
    assert sum("ollama pull qwen3:4b" in warning for warning in result["warnings"]) == 1


@pytest.mark.parametrize("invalid_task", ["summary", "translation"])
def test_diagnostics_isolates_invalid_task_configuration(monkeypatch, invalid_task):
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", "" if invalid_task == "summary" else "qwen3:4b")
    monkeypatch.setenv("LINKSCRIBE_TRANSLATION_MODEL", "" if invalid_task == "translation" else "translategemma:4b")
    monkeypatch.setattr(diagnostics, "local_ollama_json", lambda *_args, **_kw: {
        "models": [{"name": "qwen3:4b"}, {"name": "translategemma:4b"}]})
    result = diagnostics.report()
    info = result["ollama"]
    assert info["available"] is True
    assert info["model_available"] is (invalid_task != "summary")
    assert info["translation_model_available"] is (invalid_task != "translation")
    assert f"{invalid_task}_error" in info
    assert any(warning.startswith(invalid_task.title() + ":") for warning in result["warnings"])
    assert not any("model is missing" in warning for warning in result["warnings"])
