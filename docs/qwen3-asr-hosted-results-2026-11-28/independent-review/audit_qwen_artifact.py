#!/usr/bin/env python3
"""Read-only, stdlib audit of the retained hosted Qwen development artifact."""
from __future__ import annotations

import ast
import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
OUT = Path(__file__).resolve().parent
HOST = Path('/workspace/scratch/94360995dd61/qwen-hosted-7ee0c7f2-2026-11-28')
ART = HOST / 'artifact'
PLAN_PATH = ROOT / 'docs/qwen3-asr-hosted-env-followup-2026-11-28/plan.json'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_record(path: Path) -> dict:
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha(data)}


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def json_sha(value) -> str:
    return sha(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def npy_data(path: Path):
    raw = path.read_bytes()
    assert raw[:6] == b'\x93NUMPY'
    version = tuple(raw[6:8])
    assert version in [(1, 0), (2, 0)]
    width = 2 if version == (1, 0) else 4
    length = int.from_bytes(raw[8:8 + width], 'little')
    start = 8 + width + length
    header = ast.literal_eval(raw[8 + width:start].decode('latin1').strip())
    assert header['descr'] == '<f4' and header['fortran_order'] is False
    assert len(header['shape']) == 1
    data = raw[start:]
    assert len(data) == header['shape'][0] * 4
    assert all(math.isfinite(x[0]) for x in struct.iter_unpack('<f', data))
    return header, data


def byte_bpe_decode(tokens: list[str]) -> str:
    # Native reported ByteLevel token pieces -> exact UTF-8 bytes. This does not
    # load a tokenizer/model and does not independently derive IDs from weights.
    values = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256))
    characters = values.copy()
    n = 0
    for value in range(256):
        if value not in values:
            values.append(value)
            characters.append(256 + n)
            n += 1
    reverse = {chr(c): b for b, c in zip(values, characters)}
    return bytes(reverse[c] for c in ''.join(tokens)).decode('utf-8')


def main():
    plan = load(PLAN_PATH)
    report = load(ART / 'recognizer-report.json')
    execution = load(ART / 'execution.json')
    prepared = load(ART / 'input-preparation.json')
    downloaded = load(ART / 'model-download.json')
    preflight = load(ART / 'preflight.json')
    binding = load(OUT / 'source-and-criteria-before-output.json')
    followup = load(OUT / 'hosted-env-followup-binding.json')
    plan_sha = sha(PLAN_PATH.read_bytes())
    assert plan_sha == followup['followup_plan_sha256'] == report['plan_sha256'] == execution['plan_sha256'] == preflight['plan_sha256']
    assert sha((OUT / 'source-and-criteria-before-output.json').read_bytes()) == followup['original_source_criteria_binding_sha256']
    assert plan['cases'] == binding['cases']
    assert report['commit'] == preflight['github_sha'] == '7ee0c7f2ac319d817ae9861a1d632a56ed62908e'
    assert report['helper_sha256'] == preflight['helper_sha256'] == 'f578d2b534506e42f8636d45bd5d43d2fea64902961ad265f62b82b3a5d0fc8f'
    for item in plan['source_files']:
        raw = (ROOT / item['path']).read_bytes()
        assert len(raw) == item['bytes'] and sha(raw) == item['sha256']
    assert report['complete'] and report['structural_pass']
    assert report['model_initialized'] and report['model_initializations'] == 1
    assert report['pinned_sources_and_model_files_unchanged']
    assert report['runtime_versions'] == plan['runtime_versions']
    assert report['declared_generation_policy'] == plan['generation']
    assert report['model_config']['dtype'] == 'float32'
    assert report['actual_torch']['cuda_version'] is None
    assert report['actual_torch']['intra_threads'] == 4
    assert report['actual_torch']['inter_threads'] == 1
    assert len(report['cpu_affinity']) <= plan['max_cpu_threads']
    assert report['cpu_affinity'] == execution['cpu_affinity']
    assert report['source_language_argument'] is None and report['target_language_argument'] is None
    assert report['references_supplied_to_decoder'] is False
    assert report['timestamps_produced'] is False and report['app_integration'] is False
    assert report['fresh_validation'] is False and report['python_network_attempts'] == []
    assert prepared['complete'] and prepared['speech_model_initialized'] is False
    assert downloaded['complete'] and downloaded['model_initialized'] is False
    assert downloaded['model_id'] == plan['model_id']
    assert downloaded['revision'] == plan['model_revision']
    model_files = load(ROOT / plan['model_files_path'])
    expected_files = {f['filename']: f for f in model_files['files']}
    assert set(expected_files) == {f['filename'] for f in downloaded['files']}
    for item in downloaded['files']:
        expected = expected_files[item['filename']]
        assert item['status'] == 'verified' and item['attempt'] == 1
        assert item['bytes'] == expected['bytes'] and item['sha256'] == expected['sha256']
        assert item['url_without_query'] == expected['immutable_url']
    assert (ART / 'pip-check.txt').read_text().strip() == 'No broken requirements found.'
    ordered = [x['id'] for x in plan['cases']]
    assert ordered == [x['id'] for x in prepared['cases']] == [x['id'] for x in report['cases']]
    assert set(ordered) == {x.stem for x in (ART / 'token-progress').glob('*.json')}
    audit_cases = []
    for expected, prep, case in zip(plan['cases'], prepared['cases'], report['cases']):
        cid = case['id']
        assert case['attempt'] == prep['attempt'] == 1
        assert case['sample_count'] == prep['sample_count'] == expected['sample_count']
        assert prep['sample_rate_hz'] == expected['sample_rate_hz'] == 16000
        assert prep['full_untrimmed_recording'] and prep['status'] == 'pass'
        wave = ART / 'inputs' / f'{cid}.wav'
        array = ART / 'inputs' / f'{cid}.npy'
        assert sha(wave.read_bytes()) == prep['original_audio_sha256'] == prep['download']['sha256'] == expected['audio_sha256']
        assert len(wave.read_bytes()) == prep['download']['bytes']
        assert sha(array.read_bytes()) == prep['array_sha256']
        header, pcm = npy_data(array)
        assert header['shape'] == (expected['sample_count'],)
        assert sha(pcm) == case['pcm_sha256'] == prep['pcm_sha256'] == expected['pcm_sha256']
        features = case['features']
        assert features['full_input_pcm_sha256'] == expected['pcm_sha256']
        assert case['feature_extractor_calls'] == case['audio_encoder_input_calls'] == 1
        nframes = expected['sample_count'] // 160
        padded = ((nframes + 99) // 100) * 100
        assert features['shape'] == [1, 128, padded] and features['dtype'] == '<f4'
        assert features['valid_frames'] == nframes and features['padded_frames'] == padded
        assert features['mask'] == [[1] * nframes + [0] * (padded - nframes)]
        assert features['actual_options'] == {'sampling_rate': 16000, 'truncation': False, 'padding': True, 'return_attention_mask': True, 'n_window': 50}
        inputs = case['model_inputs']
        placeholders = inputs['audio_placeholder_count']
        assert placeholders == features['audio_placeholder_tokens'] == inputs['input_ids'].count(151676)
        assert inputs['attention_mask'] == [[1] * len(inputs['input_ids'])]
        expected_prompt = ('<|im_start|>system\n<|im_end|>\n<|im_start|>user\n<|audio_start|>'
                           + '<|audio_pad|>' * placeholders
                           + '<|audio_end|><|im_end|>\n<|im_start|>assistant\n')
        assert inputs['rendered_native_prompt'] == expected_prompt
        sequence, generated = case['raw_sequence_ids'], case['raw_generated_ids']
        progress_path = ART / 'token-progress' / f'{cid}.json'
        progress = load(progress_path)
        assert progress['case_id'] == cid and progress['streamer_end_called']
        assert progress['token_ids_including_prompt'] == sequence == inputs['input_ids'] + generated
        assert 0 < len(generated) < plan['generation']['max_new_tokens']
        assert generated[-1] in plan['generation']['eos_token_id']
        assert not set(generated[:-1]) & set(plan['generation']['eos_token_id'])
        assert len(generated) == len(case['raw_generated_tokens'])
        decoded = byte_bpe_decode(case['raw_generated_tokens'])
        assert decoded == case['raw_decoded_with_special_tokens']
        eos = case['raw_generated_tokens'][-1]
        assert eos in ['<|im_end|>', '<|endoftext|>']
        assert decoded[:-len(eos)] == case['raw_decoded_without_terminal_eos']
        content = case['raw_decoded_without_terminal_eos']
        assert content.count('<asr_text>') == 1
        prefix, raw_text = content.split('<asr_text>')
        language = 'Greek' if cid.startswith('fleurs-el_') else 'English'
        assert prefix == f'language {language}'
        assert raw_text == case['raw_transcript_without_repetition_repair']
        assert case['native_parsed_result'] == {'language': language, 'transcription': raw_text}
        assert case['native_parser_rewrites_raw_transcript'] is False
        assert all(value is True for value in case['checks'].values())
        assert all(value is True for value in case['completion_checks'].values())
        assert case['structural_status'] == 'pass'
        assert case['elapsed_seconds'] < plan['per_case_seconds']
        assert case['recorded_process_peak_rss_bytes'] < plan['rss_limit_bytes']
        audit_cases.append({'id': cid, 'wav_sha256': sha(wave.read_bytes()), 'array_sha256': sha(array.read_bytes()),
                            'pcm_sha256': sha(pcm), 'sample_count': expected['sample_count'],
                            'valid_mel_frames': nframes, 'padded_mel_frames': padded,
                            'full_features_reported_sha256': features['sha256'],
                            'audio_placeholder_count': placeholders, 'prompt_token_count': len(inputs['input_ids']),
                            'generated_token_count_including_eos': len(generated), 'terminal_eos_id': generated[-1],
                            'sequence_ids_json_sha256': json_sha(sequence), 'generated_ids_json_sha256': json_sha(generated),
                            'token_progress_sha256': sha(progress_path.read_bytes()),
                            'raw_transcript_utf8_sha256': sha(raw_text.encode()),
                            'raw_case_json_sha256': json_sha(case), 'elapsed_seconds': case['elapsed_seconds'],
                            'full_input_native_token_eos_parser_audit': 'pass'})
    assert execution['returncode'] == 0 and execution['stop_reason'] is None
    assert execution['owned_worker_exited'] and execution['cleanup']['leader_exited']
    assert execution['cleanup']['live_group_members_after_cleanup'] == []
    assert report['recorded_limits_pass']
    assert report['initialization_seconds'] < plan['startup_seconds']
    assert report['elapsed_seconds'] < plan['total_worker_seconds']
    assert report['recorded_process_peak_rss_bytes'] < plan['rss_limit_bytes']
    assert execution['sampled_group_peak_rss_bytes'] < plan['rss_limit_bytes']
    archive = HOST / 'qwen-native-7ee0c7f2.zip'
    assert len(archive.read_bytes()) == 4148654
    assert sha(archive.read_bytes()) == '3f5d7635edb1caed673e046e631fee82561f3524c29bbc517b8b0182224ffd1f'
    output = {'schema_version': 1, 'scope': 'Read-only independent retained-evidence audit; no model or tokenizer execution.',
              'status': 'pass', 'run_id': 46099257439, 'job_id': 140837721855, 'artifact_id': 15244707388,
              'commit': report['commit'], 'plan_sha256': plan_sha, 'artifact_zip': file_record(archive),
              'report': file_record(ART / 'recognizer-report.json'), 'execution': file_record(ART / 'execution.json'),
              'source_binding': file_record(OUT / 'source-and-criteria-before-output.json'),
              'followup_binding': file_record(OUT / 'hosted-env-followup-binding.json'), 'cases': audit_cases,
              'model_files_reported_verified': len(downloaded['files']),
              'model_verification_scope': 'Hosted recorded full-file hashes match the immutable predeclared inventory. Large model/tokenizer files were not included in the artifact and were not downloaded again by the reviewer.',
              'feature_verification_scope': 'Archived full PCM arrays and masks/counts audited. Feature hashes and the single actual encoder-forward binding come from the frozen instrumented worker; feature tensors were not archived for independent recomputation.',
              'resource_scope': {'worker_seconds': report['elapsed_seconds'], 'controller_seconds': execution['elapsed_seconds'],
                                 'initialization_seconds': report['initialization_seconds'],
                                 'longest_case_seconds': max(x['elapsed_seconds'] for x in report['cases']),
                                 'sampled_group_peak_rss_bytes': execution['sampled_group_peak_rss_bytes'],
                                 'recorded_process_peak_rss_bytes': report['recorded_process_peak_rss_bytes'],
                                 'rss_limit_bytes': plan['rss_limit_bytes'], 'sampling_seconds_declared': plan['resource_sampling_seconds'],
                                 'time_series_archived': False, 'owned_process_group_clean': True,
                                 'limitation': 'Retained controller aggregate and OS process high-water records satisfy the frozen gate. No monitor sample time series exists here to recompute the aggregate independently. This is an isolated short-clip worker measurement, not whole-app or long-audio validation.'},
              'evidence_manifest': [file_record(x) for x in sorted(ART.rglob('*')) if x.is_file()]}
    target = OUT / 'output-binding-audit.json'
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'path': str(target), 'sha256': sha(target.read_bytes()), 'status': output['status'],
                      'case_count': len(audit_cases), 'generated_tokens': [x['generated_token_count_including_eos'] for x in audit_cases],
                      'resource_scope': output['resource_scope']}, indent=2))


if __name__ == '__main__':
    main()
