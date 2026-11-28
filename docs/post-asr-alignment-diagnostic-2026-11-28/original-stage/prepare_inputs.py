"""Freeze existing complete audio and fixed output; never initialize ASR."""
from __future__ import annotations
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path('/workspace/scratch/94360995dd61/LinkScribe')
PRIOR = Path('/workspace/scratch/94360995dd61/post-asr-alignment-feasibility-2026-11-28')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', ORT_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false')
    import numpy as np
    from faster_whisper.audio import decode_audio
    from faster_whisper.tokenizer import Tokenizer as WhisperTokenizer
    from tokenizers import Tokenizer
    audit = json.loads((PRIOR / 'source-and-input-audit.json').read_text(encoding='utf-8'))
    contract = json.loads((PRIOR / 'native-api-contract.json').read_text(encoding='utf-8'))
    model = contract['existing_model']
    for name, identity in model['files_rehashed_without_loading'].items():
        assert sha(Path(model['path']) / name) == identity['sha256']
    tokenizer = Tokenizer.from_file(str(Path(model['path']) / 'tokenizer.json'))
    eot = tokenizer.token_to_id('<|endoftext|>')
    baseline = json.loads(Path(audit['official_baseline']['report_path']).read_text(encoding='utf-8'))
    raw = [event['segment'] for event in baseline['official_tail_protocol']['events'] if event['kind'] == 'asr_segment_created']
    cases = [{'id': 'official-tears-of-steel-stereo-full', 'language': 'en',
              'media_path': audit['official_baseline']['media_path'], 'media_sha256': audit['official_baseline']['media_sha256'],
              'raw_segments': raw, 'baseline_segments': baseline['cases'][0]['segments'],
              'token_scope': 'original native tokens and seek offsets',
              'expected_pcm_sha256': audit['official_baseline']['decoded_identity_is_historical_evidence_not_redecoded_today']['pcm_sha256']}]
    quiet = json.loads(Path(audit['quiet_controls']['report_path']).read_text(encoding='utf-8'))
    for old, bound in zip(quiet['cases'], audit['quiet_controls']['cases']):
        assert old['id'] == bound['id']
        source = []
        for index, segment in enumerate(old['segments']):
            ids = tokenizer.encode(segment['text'], add_special_tokens=False).ids
            assert tokenizer.decode(ids, skip_special_tokens=False) == segment['text']
            source.append({'id': index + 1, 'seek': 0, 'start': segment['start'], 'end': segment['end'], 'text': segment['text'], 'tokens': ids, 'words': None})
        cases.append({'id': old['id'], 'language': old['job_result']['language'],
                      'media_path': bound['audio_path'], 'media_sha256': bound['audio_sha256'],
                      'raw_segments': source, 'baseline_segments': old['segments'],
                      'token_scope': 'saved fixed text re-encoded; original native token segmentation not retained'})
    arrays = ROOT / 'arrays'
    arrays.mkdir(exist_ok=True)
    for case in cases:
        media = Path(case['media_path'])
        assert sha(media) == case['media_sha256']
        pcm = decode_audio(str(media), sampling_rate=16000)
        assert pcm.ndim == 1 and pcm.dtype == np.float32 and np.isfinite(pcm).all() and len(pcm) > 0
        pcm_hash = hashlib.sha256(pcm.tobytes()).hexdigest()
        if case.get('expected_pcm_sha256'):
            assert pcm_hash == case['expected_pcm_sha256']
        path = arrays / (case['id'] + '.npy')
        np.save(path, pcm, allow_pickle=False)
        case['array'] = {'path': str(path), 'npy_sha256': sha(path), 'pcm_sha256': pcm_hash,
                         'shape': list(pcm.shape), 'dtype': pcm.dtype.str, 'sample_count': len(pcm),
                         'sample_rate_hz': 16000, 'duration_seconds': len(pcm) / 16000,
                         'nonzero_sample_count': int(np.count_nonzero(pcm))}
        wt = WhisperTokenizer(tokenizer, True, task='transcribe', language=case['language'])
        case['start_sequence'] = wt.sot_sequence
        case['eot'] = eot
        windows = []
        for seek in dict.fromkeys(segment['seek'] for segment in case['raw_segments']):
            indices = [i for i, segment in enumerate(case['raw_segments']) if segment['seek'] == seek]
            flat, spans = [], []
            for index in indices:
                segment = case['raw_segments'][index]
                ids = [token for token in segment['tokens'] if token < eot]
                assert tokenizer.decode(ids, skip_special_tokens=False) == segment['text']
                spans.append({'segment_index': index, 'start': len(flat), 'end': len(flat) + len(ids)})
                flat.extend(ids)
            frames = min(3000, len(pcm) // 160 - seek)
            assert frames >= 2 and len(flat) > 0
            windows.append({'seek': seek, 'num_frames': frames, 'segment_indices': indices,
                            'text_tokens': flat, 'segment_token_spans': spans})
        case['windows'] = windows
        del pcm
    target = ROOT / 'input-cases.json'
    target.write_text(json.dumps({'schema_version': 1, 'reference_material_included': False, 'cases': cases}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    source = (REPO / 'app.py').read_text(encoding='utf-8')
    wanted = {'ReadableError', 'SubtitleTimingError', '_bounded_asr_interval', '_subtitle_interval_ms', '_millisecond_timecode', '_shown_text', '_render_subtitles'}
    functions = {node.name: ast.get_source_segment(source, node) for node in ast.parse(source).body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted}
    assert set(functions) == wanted
    policy = {'source_commit': '6de3faddf88bb5da8ea35d985b33ad26e55e249f', 'app_sha256': sha(REPO / 'app.py'), 'functions': functions,
              'scope': 'Exact source excerpts for isolated physical-bound/export projection; not a full application integration run.'}
    assert policy['app_sha256'] == 'b0ea2cf313a15697369a61beab15ae7017251476fc25ea7c77bdcbafe527dd47'
    (ROOT / 'production-timing-view.json').write_text(json.dumps(policy, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    record = {'model_initialized': False, 'model_inference': False, 'frontend_executed': False, 'audio_decoded': True,
              'complete_inputs': len(cases), 'windows': sum(len(case['windows']) for case in cases),
              'input_cases_sha256': sha(target), 'prepare_script_sha256': sha(Path(__file__)),
              'runtime_packages': {name: importlib.metadata.version(name) for name in ('faster-whisper', 'ctranslate2', 'numpy', 'av', 'tokenizers')}}
    (ROOT / 'input-preparation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
