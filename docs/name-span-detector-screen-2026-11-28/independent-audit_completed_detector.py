"""Read-only audit of the completed, once-only detector screen; no model imports."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/workspace/scratch/94360995dd61')
EVIDENCE = BASE / 'LinkScribe/docs/name-span-detector-screen-2026-11-28'
RESEARCH = BASE / 'LinkScribe/docs/name-span-protection-research-2026-11-28'
OUT = BASE / 'name-span-independent-review-2026-11-28'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    annotation_path = OUT / 'source-person-annotations-before-output.json'
    annotations = read(annotation_path)
    freeze = read(EVIDENCE / 'inference-freeze.json')
    execution = read(EVIDENCE / 'execution.json')
    resources = read(EVIDENCE / 'infer-resources.json')
    prepared = read(EVIDENCE / 'prepare.json')
    sources = read(RESEARCH / 'original-six-source-only.json')['cases']
    annotated = {c['id']: c for c in annotations['cases']}
    preparation = {c['id']: c for c in prepared['sources']}
    original = {c['id']: c for c in sources}
    assert digest(annotation_path) == '9a26e6f9eec232ae65f539a7d049c44d8a58cfd966d07c02005d5b933cacdae6'
    assert freeze['independent_source_only_annotation_sha256'] == digest(annotation_path)
    assert datetime.fromisoformat(annotations['frozen_at']) < datetime.fromisoformat(freeze['frozen_at']) < datetime.fromisoformat(execution['started_at'])
    assert all(digest(Path(p)) == h for p, h in freeze['files_sha256'].items())
    assert execution['plan_sha256'] == freeze['plan_sha256'] == digest(RESEARCH / 'detector-screen-plan.json')
    assert execution['complete'] and execution['translation_calls'] == 0
    assert resources['phase_freeze_sha256'] == digest(EVIDENCE / 'inference-freeze.json')
    assert resources['phase_report_sha256'] == digest(EVIDENCE / 'execution.json')
    assert resources['phase_report_complete'] and resources['translation_calls'] == 0
    assert resources['worker_sha256'] == digest(EVIDENCE / 'native_worker.py')
    assert resources['observer_sha256'] == digest(EVIDENCE / 'run_phase.py')
    assert execution['actual_model_files_sha256'] == prepared['actual_model_files_sha256']
    init = execution['initialization']
    assert init['strict_load_records'] == [{'class': 'UniEncoderSpanModel', 'strict': True, 'state_key_count': 224, 'missing_keys': [], 'unexpected_keys': []}]
    assert init['backbone_class'] == 'transformers.models.deberta_v2.modeling_deberta_v2.DebertaV2Model'
    assert init['parameter_count'] == prepared['checkpoint']['f32_elements'] == 288949504
    assert init['device'] == 'cpu' and init['dtype'] == 'float32'
    assert init['torch_threads'] == 4 and init['torch_interop_threads'] == 1
    assert init['offline_network_audit_enforced'] is True
    ids = [c['id'] for c in sources]
    assert [c['id'] for c in execution['cases']] == ids
    cases = []
    for entry in execution['cases']:
        path = EVIDENCE / entry['report']
        assert digest(path) == entry['sha256']
        d = read(path)
        c = original[d['id']]
        a = annotated[d['id']]
        s = d['source']
        assert d['complete'] and entry['complete']
        assert d['detector_calls'] == entry['detector_calls'] == 1 and d['translation_calls'] == 0
        assert d['profile'] == freeze['native_profile']
        assert d['plan_sha256'] == freeze['plan_sha256'] and d['inference_freeze_sha256'] == digest(EVIDENCE / 'inference-freeze.json')
        assert s == preparation[d['id']]
        text = '\n'.join(segment['text'] for segment in c['segments'])
        assert s['source_segments'] == c['segments']
        assert text == s['source_text'] == a['joined_source']
        assert hashlib.sha256(text.encode('utf-8')).hexdigest() == s['source_text_sha256'] == a['joined_utf8_sha256']
        offsets = []
        pos = 0
        for index, segment in enumerate(c['segments']):
            offsets.append({'segment_index': index, 'start': pos, 'end': pos + len(segment['text'])})
            pos += len(segment['text']) + 1
        assert offsets == s['segment_offsets'] == a['segment_map']
        words = s['native_words']
        assert all(text[w['start']:w['end']] == w['text'] for w in words)
        assert ''.join(w['text'] for w in words) == ''.join(text.split())
        assert s['source_word_count'] == len(words) <= 384
        assert s['encoded_token_count'] == len(s['arrays']['input_ids'][0]) <= 512
        assert s['truncation'] is False and s['all_original_source_words_represented'] is True
        prefix = s['prompt_word_count']
        assert prefix == 3
        expected_mask = []
        seen = set()
        for word_id in s['word_ids']:
            value = 0
            if word_id is not None and word_id >= prefix and word_id not in seen:
                value = word_id - prefix + 1
            expected_mask.append(value)
            seen.add(word_id)
        assert s['arrays']['words_mask'] == [expected_mask]
        assert set(expected_mask) == set(range(len(words) + 1))
        assert s['arrays']['attention_mask'] == [[1] * s['encoded_token_count']]
        obs = d['forward_observations']
        assert [o['stage'] for o in obs] == ['native_span_model', 'actual_deberta_encoder']
        for o in obs:
            for key in ['input_ids', 'attention_mask']:
                assert o[key] == s['arrays'][key] == s['native_collator']['arrays'][key]
        for key in ['words_mask', 'text_lengths']:
            assert obs[0][key] == s['native_collator']['arrays'][key]
        assert obs[0]['tokens'] == [[w['text'] for w in words]]
        assert obs[0]['class_mapping'] == {'1': 'person'} and obs[0]['class_mapping_type'] == 'dict'
        raw = d['raw_entities']
        for r in raw:
            assert set(r) == {'start', 'end', 'text', 'label', 'score'}
            assert type(r['start']) is int and type(r['end']) is int
            assert 0 <= r['start'] < r['end'] <= len(text)
            assert r['text'] == text[r['start']:r['end']] and r['label'] == 'person'
            assert type(r['score']) in (int, float) and math.isfinite(r['score']) and .5 <= r['score'] <= 1
        sorted_raw = sorted(raw, key=lambda r: (r['start'], r['end']))
        assert all(a['end'] <= b['start'] for a, b in zip(sorted_raw, sorted_raw[1:]))
        normalized = []
        for r in sorted_raw:
            matches = [o for o in offsets if o['start'] <= r['start'] < r['end'] <= o['end']]
            assert len(matches) == 1
            o = matches[0]
            normalized.append({**r, 'segment_index': o['segment_index'], 'segment_start': r['start'] - o['start'], 'segment_end': r['end'] - o['start']})
        assert normalized == d['validated_source_spans']
        expected = [(m['joined_start'], m['joined_end'], m['text'], m['label']) for m in a['expected_exact_mentions']]
        actual = [(r['start'], r['end'], r['text'], r['label']) for r in sorted_raw]
        cases.append({
            'id': d['id'], 'report_sha256': digest(path),
            'source_text_sha256': s['source_text_sha256'],
            'raw_entities_canonical_sha256': hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'source_words': len(words), 'encoded_tokens': s['encoded_token_count'],
            'native_span_forwards': 1, 'actual_encoder_forwards': 1,
            'full_input_and_protocol_checks_passed': True,
            'raw_entities': raw, 'expected_exact_mentions': a['expected_exact_mentions'],
            'exact_matches': len(set(expected) & set(actual)),
            'expected_mentions': len(expected), 'returned_mentions': len(actual),
            'missing_exact_spans': [x for x in expected if x not in actual],
            'unexpected_exact_spans': [x for x in actual if x not in expected],
            'exact_span_case_passed': actual == expected,
            'worker_case_seconds': d['elapsed_seconds'],
        })
    sample_path = EVIDENCE / resources['samples_file']
    assert digest(sample_path) == resources['samples_sha256']
    samples = [json.loads(line) for line in sample_path.read_text(encoding='utf-8').splitlines()]
    assert len(samples) == resources['sample_count'] == 169
    assert all(a['elapsed_seconds'] <= b['elapsed_seconds'] for a, b in zip(samples, samples[1:]))
    for s in samples:
        assert len({p['pid'] for p in s['processes']}) == len(s['processes'])
        for key in ['rss_bytes', 'pss_bytes']:
            assert s[key] == sum(p[key] for p in s['processes'])
    assert max(samples, key=lambda s: s['rss_bytes']) == resources['peak_rss_sample']
    assert max(samples, key=lambda s: s['pss_bytes']) == resources['peak_pss_sample']
    assert resources['measurement_complete'] and resources['measurement_errors'] == []
    assert resources['passed'] and resources['complete'] and resources['worker_exit_code'] == 0 and resources['owned_processes_stopped']
    assert resources['cpu_affinity'] == [0, 1, 2, 3]
    assert resources['peak_rss_sample']['rss_bytes'] < resources['limits']['rss_bytes'] == 6144 * 1024**2
    assert resources['elapsed_seconds'] < resources['limits']['total_seconds'] == 600
    events = resources['events']
    assert events[0]['event'] == 'initialized' and events[0]['observed_elapsed_seconds'] < 180
    starts = [e for e in events if e['event'] == 'case_start']
    completes = [e for e in events if e['event'] == 'case_complete']
    assert [e['id'] for e in starts] == [e['id'] for e in completes] == ids
    for start, complete, case in zip(starts, completes, cases):
        assert 0 < complete['observed_elapsed_seconds'] - start['observed_elapsed_seconds'] < 60
        assert complete['sha256'] == case['report_sha256']
    bound_files = ['inference-freeze.json', 'execution.json', 'infer-resources.json', 'infer-samples.jsonl', 'prepare.json', 'native_worker.py', 'run_phase.py']
    audit = {
        'schema_version': 1, 'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'method': 'Independent standard-library audit of retained JSON, full source, both actual forward observations, sample sums, frozen hashes and private pre-output annotation. No model imports, reruns or production changes.',
        'files_sha256': {name: digest(EVIDENCE / name) for name in bound_files},
        'independent_annotation_sha256': digest(annotation_path),
        'all_frozen_file_hashes_verified': len(freeze['files_sha256']),
        'protocol_passed': True, 'cases': cases,
        'resource_audit': {
            'complete_samples': len(samples), 'sample_sums_and_peaks_verified': True,
            'peak_rss_bytes': resources['peak_rss_sample']['rss_bytes'],
            'peak_pss_bytes': resources['peak_pss_sample']['pss_bytes'],
            'controller_seconds': resources['elapsed_seconds'], 'worker_seconds': execution['elapsed_seconds'],
            'initialization_observed_seconds': events[0]['observed_elapsed_seconds'],
            'worker_exit_code': 0, 'owned_processes_stopped': True,
            'scope_limit': 'External 100 ms sampling of the owned process tree; not an OS high-water or whole-app memory approval.'
        },
        'translation_calls': 0, 'unused_validation_accessed': False,
        'exact_span_case_passes': sum(c['exact_span_case_passed'] for c in cases),
        'exact_span_matches': sum(c['exact_matches'] for c in cases),
        'required_mentions': sum(c['expected_mentions'] for c in cases),
        'semantic_gate_passed': False,
    }
    path = OUT / 'completed-output-protocol-audit.json'
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'path': str(path), 'sha256': digest(path), 'protocol_passed': True, 'exact_span_case_passes': audit['exact_span_case_passes'], 'exact_span_matches': audit['exact_span_matches'], 'required_mentions': audit['required_mentions']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
