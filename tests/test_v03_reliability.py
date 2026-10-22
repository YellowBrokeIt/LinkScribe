"""v0.3: restart safety, validated library backups and local diagnostics."""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app
import batch_store
import diagnostics
import library
import library_backup

VIMEO = "https://vimeo.com/12345671"
VIMEO2 = "https://vimeo.com/12345672"
VIMEO3 = "https://vimeo.com/12345673"


@pytest.fixture
def site(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "db" / "library.sqlite3")
    app.jobs.clear(); app.batches.clear()
    monkeypatch.setattr(app.pool, "submit", lambda fn, *args: fn(*args))
    yield TestClient(app.app)
    app.jobs.clear(); app.batches.clear()


def install_dummy_recognition(monkeypatch, reject=()):
    hits=[]
    def download(job_id, source):
        hits.append(source.url)
        if source.url in reject:
            raise app.ReadableError("Source refused access")
        target=app.jobs[job_id].workdir / "audio.wav"
        target.write_bytes(b"pretend audio")
        return target, "Sample"
    def recognize(path,language,model):
        return [{"start": 0.0, "end": 1.25, "text": "Example words spoken."}],"en"
    monkeypatch.setattr(app,"_download_source_audio",download)
    monkeypatch.setattr(app,"_recognize",recognize)
    return hits


def test_batch_journal_created_and_archive_survives_restart(site,monkeypatch):
    hits=install_dummy_recognition(monkeypatch)
    response=site.post("/api/batch",data={"urls":"\n".join([VIMEO,VIMEO2]),"consent":"true","mode":"audio"})
    assert response.status_code==200,response.text
    bid=response.json()["id"]
    assert len(hits)==2
    assert batch_store.get(bid)["status"]=="done"
    archive1=site.get(f"/api/batches/{bid}/download").content
    app.jobs.clear();app.batches.clear()
    assert site.get(f"/api/batches/{bid}").json()["status"]=="done"
    assert site.get(f"/api/batches/{bid}/download").content==archive1
    assert site.get("/api/batches").json()["items"][0]["total"]==2
    with zipfile.ZipFile(io.BytesIO(archive1)) as z:
        assert len([x for x in z.namelist() if x.endswith("/transcript.txt")])==2
        manifest=json.loads(z.read("batch-report.json"))
        assert manifest["completed"]==2 and manifest["failed"]==0


def test_interrupted_batch_resumes_without_redoing_saved_transcript(site,monkeypatch):
    hits=install_dummy_recognition(monkeypatch)
    monkeypatch.setattr(app.pool,"submit",lambda fn,*args:None)
    post=site.post("/api/batch",data={"urls":"\n".join([VIMEO,VIMEO2,VIMEO3]),"consent":"true","mode":"audio"})
    assert post.status_code==200
    bid=post.json()["id"]
    saved=batch_store.get(bid)
    first=saved["jobs"][0]["id"]
    # Simulate a crash after finishing library.save, before journal.mark_item.
    library.save(first,VIMEO,"Already processed","en","local_audio_ai",
                 [{"start": 0.,"end": 1.,"text": "Preserved result"}])
    batch_store.mark_item(first,"working")
    app.jobs.clear();app.batches.clear()
    monkeypatch.setattr(app.pool,"submit",lambda fn,*args:fn(*args))
    app._restore_pending_batches()
    progress=site.get(f"/api/batches/{bid}").json()
    assert progress["status"]=="done" and progress["completed"]==3
    assert len(hits)==2
    assert VIMEO not in hits
    assert library.get(first)["segments"][0]["text"]=="Preserved result"
    assert all(j["status"]=="done" for j in progress["jobs"])
    assert len(site.get("/api/library").json()["items"])==3
    # A second startup hook must not submit the same batch again.
    app._restore_pending_batches()
    assert len(hits)==2


def test_interrupted_batch_preserves_per_item_failure(site,monkeypatch):
    hits=install_dummy_recognition(monkeypatch)
    monkeypatch.setattr(app.pool,"submit",lambda fn,*args:None)
    bid=site.post("/api/batch",data={"urls":VIMEO+"\n"+VIMEO2,"consent":"true","mode":"audio"}).json()["id"]
    first=batch_store.get(bid)["jobs"][0]["id"]
    batch_store.mark_item(first,"error",error="Authorization required")
    app.jobs.clear();app.batches.clear()
    monkeypatch.setattr(app.pool,"submit",lambda fn,*args:fn(*args))
    app._restore_pending_batches()
    result=site.get(f"/api/batches/{bid}").json()
    assert result["failed"]==1 and result["completed"]==2
    assert hits==[VIMEO2]
    with zipfile.ZipFile(io.BytesIO(site.get(f"/api/batches/{bid}/download").content)) as z:
        manifest=json.loads(z.read("batch-report.json"))
        assert manifest["items"][0]["error"]=="Authorization required"


def test_batch_recovery_rejects_tampered_source(site,monkeypatch):
    install_dummy_recognition(monkeypatch)
    monkeypatch.setattr(app.pool,"submit",lambda fn,*args:None)
    bid=site.post("/api/batch",data={"urls":VIMEO,"mode":"audio","consent":"true"}).json()["id"]
    conn=library._connect()
    with conn:conn.execute("UPDATE batch_queue_items SET source=? WHERE batch_id=?",("http://127.0.0.1/admin",bid))
    conn.close()
    app.batches.clear();app.jobs.clear()
    app._restore_pending_batches()
    assert batch_store.get(bid)["status"]=="error"
    assert site.get("/api/library").json()["items"]==[]


def test_backup_restore_preserves_unicode_edited_text_summary_and_times(site):
    a="a"*32;b="b"*32
    segments=[{"start":0.0,"end":1.5,"text":"Γεια σου Bitcoin!","speaker":"Αλίκη"}]
    summary={"summary":"Greek Bitcoin summary","key_points":["☀"],"chapters":[{"start":0.0,"title":"Η αρχή"}]}
    translation={"en":[{"start":0.0,"end":1.5,"text":"Hello Bitcoin!"}]}
    library.save(a,"uploaded:Greek.wav","Ελληνικό βίντεο","el","local_audio_ai",segments,translation,summary)
    export=site.get("/api/library/backup")
    assert export.status_code==200
    assert export.headers["cache-control"]=="no-store"
    with zipfile.ZipFile(io.BytesIO(export.content)) as z:
        assert sorted(z.namelist())==["manifest.json","transcripts.json"]
        assert json.loads(z.read("manifest.json"))["records"]==1
    library.update(a,"newer live edit",[{**segments[0],"text":"Do not overwrite me"}])
    library.save(b,"uploaded:later.wav","Other","en","local_audio_ai",
                 [{"start":0.,"end":1.,"text":"Other text"}])
    restore=site.post("/api/library/restore",files={"file":("backup.zip",export.content,"application/zip")})
    assert restore.status_code==200,restore.text
    assert restore.json()["imported"]==0 and restore.json()["already_present"]==1
    assert library.get(a)["segments"][0]["text"]=="Do not overwrite me"
    library.delete(a)
    restore=site.post("/api/library/restore",files={"file":("backup.zip",export.content,"application/zip")})
    assert restore.json()["imported"]==1
    assert library.get(a)["segments"]==segments
    assert library.get(a)["summary"]==summary
    assert library.get(a)["translations"]==translation
    assert library.get(b) is not None


def altered_zip(baseline: bytes, mutate):
    with zipfile.ZipFile(io.BytesIO(baseline)) as archive:
        mapping={name:archive.read(name) for name in archive.namelist()}
    mutate(mapping)
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as dst:
        for name,data in mapping.items():dst.writestr(name,data)
    return out.getvalue()


def test_bad_backups_are_rejected_without_partial_restore(site):
    library.save("f"*32,"uploaded:file.wav","Safe","en","ai",
                 [{"start":0.,"end":1.,"text":"safe"}])
    baseline=site.get("/api/library/backup").content
    bad=[b"garbage"]
    bad.append(altered_zip(baseline,lambda m: m.__setitem__("transcripts.json",b'{}')))
    bad.append(altered_zip(baseline,lambda m: m.__setitem__("unexpected.py",b'print("hi")')))
    def inject(m):
        data=json.loads(m["transcripts.json"])
        data["records"].append({"id":"e"*32,"segments":[{"start":1,"end":0,"text":"bad"}]})
        m["transcripts.json"]=json.dumps(data).encode()
        meta=json.loads(m["manifest.json"])
        meta["records"]=2;meta["sha256"]=hashlib.sha256(m["transcripts.json"]).hexdigest()
        m["manifest.json"]=json.dumps(meta).encode()
    bad.append(altered_zip(baseline,inject))
    for corrupted in bad:
        result=site.post("/api/library/restore",files={"file":("bad.zip",corrupted,"application/zip")})
        assert result.status_code==400,result.text
        assert library.get("e"*32) is None
        assert library.get("f"*32)["title"]=="Safe"


def test_diagnostics_secret_absent_and_consistent(site,monkeypatch):
    monkeypatch.setenv("HF_TOKEN","secret-hf-test-value")
    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL","qwen3:4b")
    result=site.get("/api/diagnostics")
    assert result.status_code==200
    info=result.json()
    assert info["app"]=="LinkScribe" and info["version"]=="0.3.0"
    assert "python" in info and "js_runtime" in info
    assert "secret-hf-test-value" not in result.text
    assert info["ollama"]["available"] in {True,False}


def test_restoring_backup_blocks_cross_origin(site):
    response=site.post("/api/library/restore",files={"file":("fake.zip",b"content")},
                       headers={"Origin":"https://example.org"})
    assert response.status_code==403


def test_empty_library_backup_roundtrip(site):
    content=site.get("/api/library/backup").content
    result=site.post("/api/library/restore",files={"file":("empty.zip",content)})
    assert result.json()=={"ok":True,"total":0,"imported":0,"already_present":0}
