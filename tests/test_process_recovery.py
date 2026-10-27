"""Kill and restart a real process at the transcript/journal commit boundary.

Only the source downloader and recognizer are synthetic. The application
lifecycle, worker thread, SQLite commits, process death and exports are real.
No media provider, external network or speech model is used by this test.
"""
from __future__ import annotations

from contextlib import contextmanager
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import zipfile


SOURCES = [f"https://vimeo.com/{12345671 + index}" for index in range(3)]
ROOT = Path(__file__).resolve().parents[1]


def _worker(phase: str, directory: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    import app
    import library

    app.DATA_DIR = directory / "jobs"
    library.DB_FILE = directory / "library.sqlite3"
    checkpoint = directory / "checkpoint.json"

    def download(job_id, source):
        with (directory / "download-calls.jsonl").open("a", encoding="utf-8") as calls:
            calls.write(json.dumps(source.url) + "\n")
        target = app.jobs[job_id].workdir / "audio.wav"
        target.write_bytes(b"synthetic media; never passed to a real decoder")
        return target, f"Synthetic {source.video_id}"

    def recognize(_path, _language, _model):
        return [{"start": 0.0, "end": 1.25, "text": "Synthetic speech about Bitcoin."}], "en"

    app._download_source_audio = download
    app._recognize = recognize

    if phase == "crash":
        original_save = library.save

        def save_then_pause(identifier, *args, **kwargs):
            original_save(identifier, *args, **kwargs)
            job = app.jobs[identifier]
            temporary = checkpoint.with_suffix(".tmp")
            temporary.write_text(json.dumps({"job_id": identifier, "batch_id": job.batch_id}), encoding="utf-8")
            temporary.replace(checkpoint)
            # The parent kills this process here: the transcript transaction
            # committed, but neither worker cleanup nor journal acknowledgement ran.
            threading.Event().wait(60)
            raise AssertionError("Parent did not terminate the crash worker")

        library.save = save_then_pause

    with TestClient(app.app) as client:
        if phase == "crash":
            response = client.post("/api/batch", data={
                "urls": "\n".join(SOURCES), "mode": "audio", "model": "tiny", "consent": "true"})
            assert response.status_code == 200, response.text
            threading.Event().wait(60)
            raise AssertionError("Crash worker unexpectedly survived")

        batch_id = json.loads(checkpoint.read_text(encoding="utf-8"))["batch_id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            response = client.get(f"/api/batches/{batch_id}")
            assert response.status_code == 200, response.text
            status = response.json()
            if status["status"] in {"done", "error"}:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Batch recovery did not complete within 20 seconds")
        assert status["status"] == "done", status
        downloaded = client.get(f"/api/batches/{batch_id}/download")
        assert downloaded.status_code == 200, downloaded.text
        (directory / "recovered.zip").write_bytes(downloaded.content)
        (directory / "result.json").write_text(json.dumps(status), encoding="utf-8")


@contextmanager
def _process(directory: Path, phase: str):
    log = directory / f"{phase}.log"
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve()), "--worker", phase, str(directory)],
            cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
        )
        try:
            yield process, log
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)


def test_process_crash_after_save_recovers_without_duplicate_transcription(tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    with _process(tmp_path, "crash") as (process, log):
        deadline = time.monotonic() + 25
        while not checkpoint.exists():
            assert process.poll() is None, log.read_text(encoding="utf-8")
            assert time.monotonic() < deadline, "Crash checkpoint timed out\n" + log.read_text(encoding="utf-8")
            time.sleep(0.05)
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        process.kill()
        process.wait(timeout=5)
        assert process.returncode != 0

    # Confirm the actual persisted tear point, not just a mock's expectations.
    with sqlite3.connect(tmp_path / "library.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0] == 1
        assert connection.execute("SELECT status FROM batch_queue_items WHERE job_id=?",
                                  (saved["job_id"],)).fetchone()[0] == "working"
    assert (tmp_path / "jobs" / saved["job_id"] / "audio.wav").exists()

    with _process(tmp_path, "restart") as (process, log):
        try:
            process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            raise AssertionError("Restart process timed out\n" + log.read_text(encoding="utf-8")) from None
        assert process.returncode == 0, log.read_text(encoding="utf-8")

    calls = [json.loads(line) for line in (tmp_path / "download-calls.jsonl").read_text().splitlines()]
    assert calls == SOURCES, "The saved first item must not be downloaded/transcribed twice"
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert result["completed"] == 3 and result["failed"] == 0
    assert all(item["status"] == "done" for item in result["jobs"])
    assert not list((tmp_path / "jobs").glob("*/audio.*")), "Crash leftovers must be cleaned after restart"
    with sqlite3.connect(tmp_path / "library.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0] == 3
        assert connection.execute("SELECT status FROM batch_queue WHERE id=?",
                                  (saved["batch_id"],)).fetchone()[0] == "done"
    with zipfile.ZipFile(io.BytesIO((tmp_path / "recovered.zip").read_bytes())) as archive:
        names = archive.namelist()
        assert len([name for name in names if name.endswith("/transcript.txt")]) == 3
        assert not any("audio.wav" in name for name in names)
        manifest = json.loads(archive.read("batch-report.json"))
        assert manifest["completed"] == 3 and manifest["failed"] == 0
        assert [item["source"] for item in manifest["items"]] == SOURCES


if __name__ == "__main__":
    assert len(sys.argv) == 4 and sys.argv[1] == "--worker"
    _worker(sys.argv[2], Path(sys.argv[3]))
