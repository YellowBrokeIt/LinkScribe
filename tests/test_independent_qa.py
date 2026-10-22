"""Additional isolated QA: local paths, exports, safety and failure isolation.

These do not require internet, Whisper weights, a Hugging Face token, or Ollama.
"""
from __future__ import annotations

import io
import json
import sys
import time
import types
import zipfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app
import library
import enhancements
import runtime_check
from sources import parse_source


@pytest.fixture
def qa(monkeypatch, tmp_path):
    monkeypatch.setattr(app, 'DATA_DIR', tmp_path / 'jobs')
    monkeypatch.setattr(library, 'DB_FILE', tmp_path / 'library' / 'transcripts.sqlite3')
    monkeypatch.setattr(app.pool, 'submit', lambda func, *args: func(*args))
    app.jobs.clear(); app.batches.clear()
    yield TestClient(app.app), tmp_path
    app.jobs.clear(); app.batches.clear()


def _fake_result(job_id, source):
    target = app.jobs[job_id].workdir / 'audio.webm'
    target.write_bytes(b'synthetic-media')
    return target, 'Example / Video'


def _fake_recognition(path, language, size):
    return ([{'start': 0., 'end': 1.2, 'text': 'Bitcoin and cafés'},
             {'start': 1.2, 'end': 2.5, 'text': 'Ελληνικό κείμενο'}], 'en')


def _wire_fakes(monkeypatch):
    monkeypatch.setattr(app, '_download_source_audio', _fake_result)
    monkeypatch.setattr(app, '_recognize', _fake_recognition)
    monkeypatch.setattr(app, '_check_uploaded_duration', lambda path: None)
    monkeypatch.setattr(app, '_captions', lambda ident,lang: ([{'start': 0., 'end': 1., 'text': 'Subtitle'}], 'en'))


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/private','http://localhost/private','https://169.254.169.254/latest',
    'https://vimeo.com@127.0.0.1/1234567','https://vimeo.com.evil.test/1234567',
    'https://vimeo.com:8443/1234567','https://vimeo.com/123%2F456',
    'file:///etc/passwd','http://[::1]/', 'https://www.youtube.com/watch?v=XXXXXXXXXXX&evil=1\nnext',
    'https://youtube.com/watch?v=abc', 'http://vimeo.com/../123456',
    'https://www.dailymotion.com/playlist/xyz','https://vimeo.com/1234567/abcdef',
])
def test_qa_url_boundary_rejects_untrusted(url):
    with pytest.raises(ValueError): parse_source(url)


def test_qa_runtime_older_node_rejected(monkeypatch):
    # The evaluator's installed Node.js is v22.16.0, below October security floor.
    assert not runtime_check.node_version_supported((22,23,3))
    assert runtime_check.node_version_supported((22,23,4))
    assert not runtime_check.node_version_supported((24,22,0))
    assert runtime_check.node_version_supported((24,22,1))
    assert not runtime_check.node_version_supported((26,12,0))
    assert runtime_check.node_version_supported((26,12,1))
    assert not runtime_check.node_version_supported((28,0,0))
    assert not runtime_check.node_version_supported((20,99,99))
    monkeypatch.setattr(runtime_check.shutil,"which",lambda name:"/usr/bin/node" if name=="node" else None)
    monkeypatch.setattr(runtime_check,"_version_output",lambda name,exe:(22,16,0))
    assert runtime_check.runtime_details()["supported"] is False
    assert runtime_check.yt_dlp_js_options() == {}


def test_qa_api_rejects_host_origin_and_missing_permission(qa):
    client,_ = qa
    assert client.post('/api/link',data={'url':'https://vimeo.com/123456','consent':'true'},headers={'Host':'evil.invalid'}).status_code==400
    assert client.post('/api/link',data={'url':'https://vimeo.com/123456','consent':'true'},headers={'Origin':'https://evil.invalid'}).status_code==403
    assert client.post('/api/link',data={'url':'https://vimeo.com/123456'}).status_code==400
    assert client.post('/api/upload',files={'file':('x.exe',b'data')},data={'consent':'true'}).status_code==400
    assert client.get('/api/library/not-an-id').status_code==404
    assert client.get('/api/jobs/not-an-id/download/txt').status_code==404
    assert client.get('/').status_code==200
    assert client.get('/health').json()['status']=='ok'


def test_qa_single_upload_all_exports_and_restart(qa, monkeypatch):
    client,_ = qa
    _wire_fakes(monkeypatch)
    resp=client.post('/api/upload',files={'file':('../recording.WAV', b'good-data','audio/wav')},data={'consent':'true','model':'tiny'})
    assert resp.status_code==200,resp.text
    job_id=resp.json()['id']
    status=client.get(f'/api/jobs/{job_id}').json()
    assert status['status']=='done'
    assert status['language']=='en' and status['segments']==2
    assert not list(app.jobs[job_id].workdir.glob('input.*'))
    assert client.get('/api/library',params={'q':'café'}).json()['items'][0]['id']==job_id
    with zipfile.ZipFile(io.BytesIO(client.get(f'/api/library/{job_id}/download/zip').content)) as z:
        assert set(z.namelist())=={'transcript.txt','transcript.srt','transcript.vtt','transcript.json'}
        assert 'WEBVTT' in z.read('transcript.vtt').decode()
        assert '00:00:01,200' in z.read('transcript.srt').decode()
        assert 'Ελληνικό κείμενο' in z.read('transcript.txt').decode()
    assert client.put(f'/api/library/{job_id}',json={'title':'Νέα καταγραφή','segments':[
        {'text':'Ένα νέο κείμενο','speaker':'Αλίκη'}, {'text':'Other words','speaker':'Bob'}]}).status_code==200
    app.jobs.clear()
    assert 'Αλίκη: Ένα νέο κείμενο' in client.get(f'/api/library/{job_id}/download/txt').text
    assert client.get('/api/library',params={'q':'Νέα'}).json()['items'][0]['id']==job_id
    assert client.delete(f'/api/library/{job_id}').status_code==200
    assert client.get(f'/api/library/{job_id}/download/zip').status_code==404


def test_qa_20_link_batch_and_report(qa, monkeypatch):
    client,_=qa
    _wire_fakes(monkeypatch)
    sources=[f'https://vimeo.com/{i+1234567}' for i in range(20)]
    resp=client.post('/api/batch',data={'urls':'\n'.join(sources),'consent':'true','mode':'audio'})
    assert resp.status_code==200, resp.text
    result=client.get(f"/api/batches/{resp.json()['id']}").json()
    assert result['total']==20 and result['completed']==20 and result['failed']==0
    assert result['status']=='done'
    assert len(client.get('/api/library',params={'limit':100}).json()['items'])==20
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/batches/{result['id']}/download").content)) as z:
        assert len([name for name in z.namelist() if name.endswith('transcript.txt')])==20
        manifest=json.loads(z.read('batch-report.json'))
        assert manifest['total']==20 and manifest['failed']==0 and len(manifest['items'])==20


def test_qa_queue_limit_considers_batches_one_slot(qa, monkeypatch):
    client,_=qa
    monkeypatch.setattr(app.pool,'submit',lambda *args:None)
    for i in range(8):
        resp=client.post('/api/link',data={'url':f'https://vimeo.com/{10000000+i}','consent':'true','mode':'audio'})
        assert resp.status_code==200
    assert client.post('/api/link',data={'url':'https://vimeo.com/99999999','consent':'true','mode':'audio'}).status_code==429
    assert client.post('/api/batch',data={'urls':'https://vimeo.com/99999999','consent':'true','mode':'audio'}).status_code==429
    assert len(app.jobs)==8


def test_qa_undo_stale_extras_and_json_injection(qa,monkeypatch):
    client,_=qa
    _wire_fakes(monkeypatch)
    # This must be inert TEXT in the UI, not an executable fragment.
    malicious='<img src=x onerror=alert(document.cookie)>'
    job=client.post('/api/link',data={'url':'https://vimeo.com/1234567','mode':'audio','consent':'true'}).json()['id']
    record=client.get(f'/api/library/{job}').json()
    edit=client.put(f'/api/library/{job}',json={'title':'<script>alert(1)</script>','segments':[
        {'text':malicious, 'speaker':'<svg onload=alert(1)>'}, {'text':'normal','speaker':''}]})
    assert edit.status_code==200
    result=client.get(f'/api/library/{job}').json()
    assert result['title']=='<script>alert(1)</script>'
    assert result['segments'][0]['text']==malicious
    assert result['segments'][0]['start']==record['segments'][0]['start']
    assert client.get(f'/api/library/{job}/download/txt').status_code==200
    # Search wildcards must be treated as literals and never become full-table matches.
    assert not client.get('/api/library',params={'q':'%'}).json()['items']
    assert not client.get('/api/library',params={'q':'_'}).json()['items']


def test_qa_provider_download_uses_canonical_only(qa, monkeypatch):
    client,_=qa
    calls=[]
    class StubDownloader:
        def __init__(self,options):
            assert options.get('noplaylist') is True
            assert options.get('max_filesize')==app.MAX_BYTES
            calls.append(('options',options))
            self.options=options
        def __enter__(self):return self
        def __exit__(self,*args): pass
        def extract_info(self,url,download=False):
            calls.append(('extract',url,download))
            return {'title':'Example','duration':10,'filesize':300}
        def download(self,urls):
            calls.append(('download',urls))
            Path(self.options['outtmpl'].replace('%(ext)s','webm')).write_bytes(b'webm fake')
    monkeypatch.setitem(sys.modules,'yt_dlp',SimpleNamespace(YoutubeDL=StubDownloader))
    job=app._new_job('https://vimeo.com/1234567')
    audio,title=app._download_source_audio(job.id,parse_source('http://www.vimeo.com/1234567?stuff=ignored'))
    assert title=='Example' and audio.is_file()
    assert ('extract','https://vimeo.com/1234567',False) in calls
    assert ('download',['https://vimeo.com/1234567']) in calls


def test_qa_provider_rejects_oversized_and_long(qa, monkeypatch):
    client,_=qa
    for field,value in [('duration',app.MAX_SECONDS+1),('filesize',app.MAX_BYTES+1)]:
        class Downloader:
            def __init__(self,options):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def extract_info(self,url,download=False):return {field:value,'title':'Huge'}
            def download(self,urls):raise AssertionError('must not download oversized media')
        monkeypatch.setitem(sys.modules,'yt_dlp',SimpleNamespace(YoutubeDL=Downloader))
        job=app._new_job('https://vimeo.com/1234567')
        with pytest.raises(app.ReadableError):app._download_source_audio(job.id,parse_source('https://vimeo.com/1234567'))


def test_qa_expired_job_still_saved_in_database(qa,monkeypatch):
    client,_=qa
    _wire_fakes(monkeypatch)
    job_id=client.post('/api/link',data={'url':'https://vimeo.com/1234567','mode':'audio','consent':'true'}).json()['id']
    app.jobs[job_id].finished_at=time.time()-app.JOB_TTL-15
    assert client.get(f'/api/jobs/{job_id}').status_code==404
    assert client.get(f'/api/library/{job_id}').status_code==200
    assert client.get(f'/api/library/{job_id}/download/vtt').status_code==200


def test_qa_empty_upload_rejected_and_does_not_keep_jobs(qa):
    client,_=qa
    response=client.post('/api/upload',data={'consent':'true'},files={'file':('empty.mp3',b'', 'audio/mpeg')})
    assert response.status_code==400
    assert app.jobs=={}



def test_qa_ollama_real_local_http_contract_and_nonlocal_refusal(monkeypatch):
    """Exercise actual JSON HTTP POST/response without downloading a language model."""
    import http.server
    import socketserver
    import threading
    requests=[]
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            assert self.path=='/api/chat'
            length=int(self.headers['Content-Length'])
            message=json.loads(self.rfile.read(length))
            requests.append(message)
            result={'message':{'content':json.dumps({'translations':['Γεια!']})}}
            payload=json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
    class Server(socketserver.TCPServer):
        allow_reuse_address=True
    with Server(('127.0.0.1',11434),Handler) as server:
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            monkeypatch.setenv('LINKSCRIBE_OLLAMA_URL','http://127.0.0.1:11434')
            translated=enhancements.translate_segments([{'start':0,'end':1,'text':'Hello!'}],'el')
            assert translated==[{'start':0,'end':1,'text':'Γεια!'}]
            assert len(requests)==1 and requests[0]['stream'] is False
            assert requests[0]['format']=='json' and requests[0]['model']
        finally:
            server.shutdown()
            worker.join(timeout=3)
    monkeypatch.setenv('LINKSCRIBE_OLLAMA_URL','http://203.0.113.5:11434')
    with pytest.raises(enhancements.EnhancementError):
        enhancements.translate_segments([{'start':0,'end':1,'text':'Hello'}],'el')


def test_qa_pyannote_real_annotation_speaker_overlap(monkeypatch, tmp_path):
    """Use real pyannote Annotation geometry without loading its gated model."""
    try:
        from pyannote.core import Annotation, Segment
    except ImportError:
        pytest.skip('Optional pyannote is not installed in base dependencies')
    annotation=Annotation(uri='qa-sound')
    annotation[Segment(0.0,1.0)]='bob'
    annotation[Segment(1.05,2.5)]='alice'
    monkeypatch.setenv('HF_TOKEN','qa-not-real')
    monkeypatch.setattr(enhancements,'_diarization_pipeline',lambda token:lambda path:SimpleNamespace(exclusive_speaker_diarization=annotation))
    segments=[{'start':0.0,'end':1.0,'text':'Good morning'}, {'start':1.1,'end':2.1,'text':'Hello there'}]
    labeled=enhancements.assign_speakers(tmp_path/'not-needed.wav',segments)
    assert [s['speaker'] for s in labeled]==['Speaker 1','Speaker 2']
    assert labeled[0]['text']=='Good morning' and labeled[1]['start']==1.1
