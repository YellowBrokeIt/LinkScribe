"""New local tests for batch processing, source validation, library, and optional AI."""
from __future__ import annotations
import io
import json
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app as module
import enhancements
import library
from sources import parse_source

VALID_YT = "https://youtu.be/dQw4w9WgXcQ"
VALID_VIMEO = "https://vimeo.com/12345678"
VALID_DAILY = "https://www.dailymotion.com/video/x8abcd9"


@pytest.fixture(autouse=True)
def clean_local_state(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "data" / "library.sqlite3")
    module.jobs.clear(); module.batches.clear()
    yield
    module.jobs.clear(); module.batches.clear()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(module.pool,"submit",lambda func,*args:func(*args))
    return TestClient(module.app)


@pytest.mark.parametrize("raw,provider,canonical", [
    (VALID_YT,"youtube","https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("youtube.com/shorts/dQw4w9WgXcQ","youtube","https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    (VALID_VIMEO,"vimeo","https://vimeo.com/12345678"),
    ("https://player.vimeo.com/video/12345678","vimeo","https://vimeo.com/12345678"),
    (VALID_DAILY,"dailymotion","https://www.dailymotion.com/video/x8abcd9"),
    ("https://dai.ly/x8abcd9","dailymotion","https://www.dailymotion.com/video/x8abcd9"),
])
def test_canonical_sources(raw,provider,canonical):
    source=parse_source(raw)
    assert source.provider==provider and source.url==canonical


@pytest.mark.parametrize("raw",[
    "http://127.0.0.1/a","http://169.254.169.254/latest/meta-data/",
    "http://localhost", "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
    "https://user@vimeo.com/12345678", "https://vimeo.com:9999/12345678",
    "https://vimeo.com/12345678/other", "https://vimeo.com/channels/1234",
    "https://www.dailymotion.com/playlist/x7",
    "https://vimeo.com/12345678%2Fetc", "https://www.youtube.com/watch?v=dQw4w9WgXcQ\nhttp://bad",
])
def test_reject_untrusted_sources(raw):
    with pytest.raises(ValueError): parse_source(raw)


def fake_audio(job_id, source):
    if source.video_id=="12345679": raise module.ReadableError("Source unavailable")
    target=module.jobs[job_id].workdir/"audio.mp3"
    target.write_bytes(b"audio")
    return target,"Sample " + source.provider


def fake_recognize(path, language, model):
    return ([{"start":0.0,"end":2.2,"text":"Hello world"},
             {"start":2.2,"end":4.0,"text":"Welcome back"}],"en")


def fake_summary(segments):
    return {"summary":"A test conversation", "key_points":["Introductions"],
            "chapters":[{"start":0,"title":"Welcome"}]}


def install_fake_models(monkeypatch):
    monkeypatch.setattr(module,"_download_source_audio",fake_audio)
    monkeypatch.setattr(module,"_recognize",fake_recognize)
    monkeypatch.setattr(module,"assign_speakers",lambda path,segments:[{**s,"speaker":"Speaker 1"} for s in segments])
    monkeypatch.setattr(module,"translate_segments",lambda segments,target:[{**s,"text":"Γειά σου"} for s in segments])
    monkeypatch.setattr(module,"summarize_segments",fake_summary)


def test_all_enhancements_and_library_crud(client,monkeypatch):
    install_fake_models(monkeypatch)
    result=client.post("/api/link",data={"url":VALID_VIMEO,"mode":"audio","consent":"true",
                                          "speakers":"true","target_language":"el","summary":"true"})
    assert result.status_code==200,result.text
    job_id=result.json()["id"]
    details=client.get(f"/api/jobs/{job_id}").json()
    assert details["status"]=="done",details
    assert details["extras"]=={"translation_language":"el","summary":True,"speakers":True}
    assert details["library_id"]==job_id
    assert not (module.jobs[job_id].workdir/"audio.mp3").exists()
    transcript=client.get(f"/api/library/{job_id}").json()
    assert transcript["segments"][0]["speaker"]=="Speaker 1"
    assert transcript["translations"]["el"][0]["text"]=="Γειά σου"
    assert transcript["summary"]["chapters"][0]["start"]==0
    assert "Speaker 1:" in client.get(f"/api/jobs/{job_id}/download/srt").text
    assert "Γειά σου" in client.get(f"/api/jobs/{job_id}/download/translation_txt").text
    assert "Introductions" in client.get(f"/api/jobs/{job_id}/download/summary_md").text
    archive=zipfile.ZipFile(io.BytesIO(client.get(f"/api/library/{job_id}/download/zip").content))
    assert {"transcript.srt","translation_el.txt","summary.md","summary.json"}.issubset(archive.namelist())
    assert client.get("/api/library",params={"q":"Hello"}).json()["items"][0]["id"]==job_id
    data={"title":"Edited sample", "segments":[{"text":"Changed words","speaker":"Alice"},{"text":"Other speaker","speaker":"Bob"}]}
    assert client.put(f"/api/library/{job_id}",json=data).status_code==200
    updated=client.get(f"/api/library/{job_id}").json()
    assert updated["title"]=="Edited sample"
    assert updated["segments"][0]["start"]==0
    assert updated["segments"][1]["speaker"]=="Bob"
    assert updated["translations"]=={} and updated["summary"] is None
    assert "Changed words" in client.get(f"/api/library/{job_id}/download/txt").text
    assert "Changed words" in client.get(f"/api/jobs/{job_id}/download/txt").text
    assert client.get(f"/api/library/{job_id}/download/summary_md").status_code==404
    module.jobs.clear()  # Server restart: SQLite persists without job memory.
    assert "Changed words" in client.get(f"/api/library/{job_id}/download/txt").text
    assert client.delete(f"/api/library/{job_id}").status_code==200
    assert client.get(f"/api/library/{job_id}").status_code==404


def test_batch_is_one_queue_slot_and_continues_after_failure(client,monkeypatch):
    install_fake_models(monkeypatch)
    monkeypatch.setattr(module,"_captions",lambda ident,lang:([{"start":0,"end":1,"text":"Caption content"}],"en"))
    links="\n".join([VALID_YT,VALID_VIMEO,"https://vimeo.com/12345679",VALID_DAILY])
    result=client.post("/api/batch",data={"urls":links,"consent":"true","mode":"smart"})
    assert result.status_code==200,result.text
    batch_id=result.json()["id"]
    batch=client.get(f"/api/batches/{batch_id}").json()
    assert batch["total"]==4 and batch["completed"]==4 and batch["failed"]==1
    assert batch["status"]=="done"
    assert [s["status"] for s in batch["jobs"]]==["done","done","error","done"]
    packed=client.get(f"/api/batches/{batch_id}/download")
    assert packed.status_code==200
    with zipfile.ZipFile(io.BytesIO(packed.content)) as z:
        assert sum(name.endswith("transcript.txt") for name in z.namelist())==3
        assert not any("audio.mp3" in name for name in z.namelist())
    assert len(client.get("/api/library").json()["items"])==3


def test_batch_validation_and_speaker_caption_constraints(client):
    assert client.post("/api/batch",data={"urls":VALID_YT+"\n"+VALID_YT,"consent":"true"}).status_code==400
    urls="\n".join(f"https://vimeo.com/{i+1000000}" for i in range(21))
    assert client.post("/api/batch",data={"urls":urls,"consent":"true"}).status_code==400
    assert client.post("/api/link",data={"url":VALID_VIMEO,"mode":"captions","consent":"true"}).status_code==400
    assert client.post("/api/link",data={"url":VALID_YT,"mode":"captions","speakers":"true","consent":"true"}).status_code==400
    assert client.post("/api/batch",data={"urls":VALID_YT,"consent":"false"}).status_code==400
    assert client.post("/api/batch",data={"urls":VALID_YT,"consent":"true"},headers={"Origin":"https://bad.example"}).status_code==403
    assert client.get("/api/library",params={"q":"x"*201}).status_code==400


def test_unavailable_ollama_preserves_transcript(client,monkeypatch):
    install_fake_models(monkeypatch)
    def offline(*args):raise enhancements.EnhancementError("Local AI is not installed")
    monkeypatch.setattr(module,"translate_segments",offline)
    monkeypatch.setattr(module,"summarize_segments",offline)
    result=client.post("/api/link",data={"url":VALID_VIMEO,"mode":"audio","consent":"true","target_language":"el","summary":"true"})
    job=client.get(f"/api/jobs/{result.json()['id']}").json()
    assert job["status"]=="done" and len(job["warnings"])==2
    assert job["extras"]["translation_language"]=="" and not job["extras"]["summary"]
    assert client.get(f"/api/jobs/{job['id']}/download/txt").status_code==200


def test_library_edit_rejects_invalid_and_markup_preserved(client,monkeypatch):
    install_fake_models(monkeypatch)
    result=client.post("/api/link",data={"url":VALID_VIMEO,"mode":"audio","consent":"true"})
    id=result.json()["id"]
    assert client.put(f"/api/library/{id}",json={"title":"x","segments":[]}).status_code==400
    assert client.put(f"/api/library/{id}",json={"title":"x","segments":[{"text":"x"},{"text":""}]}).status_code==400
    assert client.put(f"/api/library/{id}",json={"title":"x","segments":[{"text":"abc","start":9000},{"text":"def"}]}).status_code==200
    assert client.get(f"/api/library/{id}").json()["segments"][0]["start"]==0.0
    assert client.get(f"/api/library/{id}/download/txt").text.startswith("abc")


def test_speaker_overlap_with_pyannote_object(monkeypatch,tmp_path):
    monkeypatch.setenv("HF_TOKEN","dummy-token")
    class Timeline:
        def itertracks(self,yield_label):
            assert yield_label
            yield SimpleNamespace(start=0,end=1.5),"track1","person_2"
            yield SimpleNamespace(start=1.5,end=4),"track2","person_1"
    monkeypatch.setattr(enhancements,"_diarization_pipeline",lambda token:lambda path:SimpleNamespace(exclusive_speaker_diarization=Timeline()))
    output=enhancements.assign_speakers(tmp_path/"sound.wav",[
        {"start":0,"end":1.4,"text":"first"},
        {"start":1.6,"end":3.8,"text":"second"}])
    assert [s["speaker"] for s in output]==["Speaker 1","Speaker 2"]


def test_translation_segments_preserve_timing_and_order(monkeypatch):
    calls=[]
    def model(payload):
        request=json.loads(payload["messages"][1]["content"].split("JSON input: ")[1])
        calls.append(len(request))
        return {"translations":["Γεια " + x["text"] for x in request]}
    monkeypatch.setattr(enhancements,"_ollama",model)
    segments=[{"start":i,"end":i+0.8,"text":f"phrase {i}","speaker":"Speaker 1"} for i in range(25)]
    result=enhancements.translate_segments(segments,"el")
    assert calls==[12,12,1]
    assert len(result)==25 and result[24]["text"]=="Γεια phrase 24"
    assert result[0]["speaker"]=="Speaker 1" and result[0]["start"]==0


def test_summarize_long_transcript_does_not_ignore_later_sections(monkeypatch):
    calls=[]
    def model(payload):
        system=payload["messages"][0]["content"]
        user=payload["messages"][1]["content"]
        calls.append(user)
        if "chapter_title" in system:return {"notes":"Notes " + user[-60:],"chapter_title":"Section"}
        if "Condense" in system:return {"notes":"condensed"}
        return {"summary":"All of the notes are summarized","key_points":["One"]}
    monkeypatch.setattr(enhancements,"_ollama",model)
    segments=[{"start":i*10,"end":i*10+5,"text":"Passage "+str(i)+" "+("x"*1000)} for i in range(15)]
    result=enhancements.summarize_segments(segments)
    assert len(result["chapters"])>=3
    assert len(calls)>=4
    assert any("Passage 14" in call for call in calls)
    assert all(chapter["start"] in {s["start"] for s in segments} for chapter in result["chapters"])


def test_expired_batch_children_not_deleted_until_batch_finishes(monkeypatch):
    job=module._new_job("test",batch_id="f"*32)
    batch=module.Batch(id="f"*32,workdir=module.DATA_DIR/"batches"/("f"*32),job_ids=[job.id],status="working")
    module.batches[batch.id]=batch
    module._set(job.id,finished_at=time.time()-module.JOB_TTL-10,status="done")
    module._cleanup_expired()
    assert job.id in module.jobs


def test_runtime_prefers_supported_deno_and_falls_back_to_supported_node(monkeypatch):
    import runtime_check
    class Result:
        returncode = 0
        def __init__(self, stdout): self.stdout = stdout

    def installed(**version_map):
        monkeypatch.setattr(runtime_check.shutil,"which",lambda name: f"/usr/bin/{name}" if name in version_map else None)
        monkeypatch.setattr(runtime_check.subprocess,"run",lambda args,**kwargs:Result(version_map[Path(args[0]).name]))

    installed(deno="deno 2.4.0\nv8 12.0\n",node="v24.22.1\n")
    assert runtime_check.runtime_details()["runtime"] == "deno"
    assert runtime_check.yt_dlp_js_options() == {}
    installed(deno="deno 2.2.9\n",node="v22.23.4\n")
    assert runtime_check.runtime_details()["runtime"] == "node"
    assert runtime_check.yt_dlp_js_options() == {"js_runtimes":{"node":{}}}
    installed(deno="deno 2.1.0\n",node="v20.0.0\n")
    assert runtime_check.runtime_details()["supported"] is False
    assert runtime_check.yt_dlp_js_options() == {}
    installed(node="v26.12.1\n")
    assert runtime_check.runtime_details()["runtime"] == "node"
    installed(deno="deno 2.3.0\n")
    assert runtime_check.runtime_details()["runtime"] == "deno"


def test_node_october_2026_patched_release_floors(monkeypatch):
    import runtime_check
    cases = [
        ((22, 23, 3), False), ((22, 23, 4), True), ((22, 24, 0), True),
        ((24, 22, 0), False), ((24, 22, 1), True), ((24, 23, 0), True),
        ((26, 12, 0), False), ((26, 12, 1), True), ((26, 13, 0), True),
        ((20, 99, 99), False), ((23, 99, 99), False), ((25, 99, 99), False),
        ((27, 0, 0), False), ((28, 0, 0), False),
    ]
    for version, expected in cases:
        assert runtime_check.node_version_supported(version) == expected, version

    class Result:
        returncode = 0
        def __init__(self, value): self.stdout = value

    versions = {"deno": "deno 2.2.0\n", "node": "v24.22.0\n"}
    monkeypatch.setattr(runtime_check.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(runtime_check.subprocess, "run", lambda args, **kwargs: Result(versions[Path(args[0]).name]))
    assert runtime_check.runtime_details()["runtime"] is None
    assert runtime_check.yt_dlp_js_options() == {}
    versions["node"] = "v24.22.1\n"
    assert runtime_check.runtime_details()["runtime"] == "node"
    assert runtime_check.yt_dlp_js_options() == {"js_runtimes": {"node": {}}}
    versions["deno"] = "deno 2.3.0\n"
    assert runtime_check.runtime_details()["runtime"] == "deno"
    assert runtime_check.yt_dlp_js_options() == {}
