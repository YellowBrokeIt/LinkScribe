"""Independent audit of retained projection results; no model execution."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re

ROOT = Path('/workspace/scratch/94360995dd61')
HERE = Path(__file__).resolve().parent
NEW = ROOT / 'post-asr-local-projection-2026-11-28'
OLD = ROOT / 'post-asr-alignment-diagnostic-2026-11-28'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def milliseconds(value):
    hours, minutes, seconds = value.replace(',', '.').split(':')
    whole, fraction = seconds.split('.')
    return ((int(hours) * 60 + int(minutes)) * 60 + int(whole)) * 1000 + int(fraction)


def timed_export(path):
    result = []
    for block in re.split(r'\n\s*\n', path.read_text().strip()):
        lines = block.splitlines()
        index = next((i for i, line in enumerate(lines) if ' --> ' in line), None)
        if index is None:
            continue
        start, end = lines[index].split(' --> ')
        result.append({'start_ms': milliseconds(start), 'end_ms': milliseconds(end),
                       'text': '\n'.join(lines[index + 1:])})
    return result


def main():
    output = HERE / 'independent-output-audit.json'
    if output.exists():
        raise ValueError('Refusing to overwrite an independent output audit')
    errors = []
    def check(condition, label):
        if not condition:
            errors.append(label)
    identities = {
        NEW / 'plan.json': 'bff98950f7e5e042ea3dade24252f5bfacfd44698c6af78b59b65a15201c8840',
        NEW / 'replay_projection.py': '12a41231e30150afec3efca132e69cb3e50071c46c6560eb5c9c9fba35d1487c',
        NEW / 'results/report.json': '4d281171afc29b8e9ee32b87598e7147d55ca047bc879aac84522c6711d56c6c',
        NEW / 'raw-results-manifest.json': '800e38acbece870726ac414d5bd3d837540a2fd9e6383c5127b5ef8299bd3afa',
        ROOT / 'post-asr-alignment-root-review-2026-11-28/audit_outputs.py': '71873e0838a7033e1b0e4d0c43d24c15d6faf56c67640f704264abe1769e5063',
    }
    for path, expected in identities.items():
        check(sha(path) == expected, f'Identity changed: {path}')
    plan = read(NEW / 'plan.json')
    for item in plan['pinned_files']:
        path = Path(item['path'])
        check(sha(path) == item['sha256'] and path.stat().st_size == item['bytes'], f'Pinned input changed: {path}')
    manifest = read(NEW / 'raw-results-manifest.json')
    for item in manifest['files']:
        path = NEW / item['path']
        check(sha(path) == item['sha256'] and path.stat().st_size == item['bytes'], f'Frozen raw output changed: {path}')
    old_manifest = read(OLD / 'raw-results-manifest.json')
    for item in old_manifest['files']:
        path = OLD / item['path']
        check(sha(path) == item['sha256'] and path.stat().st_size == item['bytes'], f'Original raw output changed: {path}')
    audit = module('original_independent_audit', ROOT / 'post-asr-alignment-root-review-2026-11-28/audit_outputs.py')
    replay = module('reviewed_projection', NEW / 'replay_projection.py')
    frozen = replay.load_frozen_helper(plan['original_helper_path'])
    view = frozen.timing_view()
    inputs = read(OLD / 'input-cases.json')['cases']
    old = read(OLD / 'results/report.json')
    new = read(NEW / 'results/report.json')
    execution = read(NEW / 'replay-execution.json')
    check(new['complete'] and execution['returncode'] == 0, 'Replay did not complete')
    check(new['new_model_frontend_recognition_alignment_or_network_calls'] == 0, 'Unexpected model call')
    check(new['evaluation_reference_read'] is False, 'Candidate read evaluation data')
    check([c['id'] for c in new['case_results']] == plan['case_order'], 'Case order changed')
    cases = []
    for source, previous, result in zip(inputs, old['case_results'], new['case_results']):
        label = source['id']
        duration = source['array']['duration_seconds']
        baseline, candidate = result['baseline_segments'], result['candidate_segments']
        check(label == previous['id'] == result['id'], label + ': case mismatch')
        check(result['status'] == 'complete', label + ': incomplete output')
        check(baseline == previous['baseline_segments'], label + ': original bounded baseline changed')
        check(len(candidate) == len(source['raw_segments']), label + ': segment count changed')
        check([s['text'] for s in candidate] == [s['text'] for s in baseline], label + ': original strings/order changed')
        check(result['full_input'] == previous['full_input'], label + ': full input evidence changed')
        check(result['full_input']['sha256'] == source['array']['pcm_sha256'], label + ': PCM identity changed')
        check(result['full_input']['sample_count'] == source['array']['sample_count'], label + ': input length changed')
        adjusted = [None] * len(source['raw_segments'])
        mapping = {}
        for record in previous['windows']:
            for index, segment in zip(record['window']['segment_indices'], record['upstream_adjusted_segments']):
                check(adjusted[index] is None, label + ': duplicate retained segment')
                adjusted[index] = copy.deepcopy(segment)
            mapping.update(frozen.segment_mapping(record['native_words_after_merge'], record['window']))
        prebaseline, initial, warnings, prior_fallback = replay.build_candidates(source, adjusted, mapping, view)
        check(prebaseline == baseline, label + ': prefix baseline changed')
        resolution = result['projection']['local_conflict_resolution']
        reverted = resolution['reverted_segment_indices']
        expected_reverted = [80, 81] if label == plan['case_order'][0] else []
        check(reverted == expected_reverted, label + ': unexpected fallback scope')
        for index, (initial_segment, final_segment) in enumerate(zip(initial, candidate)):
            expected = copy.deepcopy(initial_segment)
            if index in reverted:
                expected.update(start=baseline[index]['start'], end=baseline[index]['end'], _words=[])
            check(final_segment == expected, label + ': unrelated candidate field changed at ' + str(index))
            check(all(type(final_segment[k]) in (int, float) and math.isfinite(final_segment[k]) for k in ('start', 'end'))
                  and 0 <= final_segment['start'] < final_segment['end'] <= duration, label + ': invalid physical interval')
            words = final_segment.get('_words', [])
            if words:
                check(''.join(w['word'] for w in words).strip() == final_segment['text'], label + ': word/text mismatch')
                check(all(0 <= w['start'] < w['end'] <= duration and final_segment['start']-.05 <= w['start']
                          and w['end'] <= final_segment['end']+.05 for w in words), label + ': invalid private word bounds')
                check(all(a['end'] <= b['start']+.001 for a,b in zip(words,words[1:])), label + ': unordered private words')
        check(all(a['end'] <= b['start']+1e-9 for a,b in zip(candidate,candidate[1:])), label + ': overlapping final segments')
        if label != plan['case_order'][0]:
            check(candidate == previous['candidate_segments'], label + ': unaffected short result changed')
        directory = NEW / 'results' / label
        for kind, segments in [('baseline', baseline), ('candidate', candidate)]:
            check(read(directory/(kind+'.json')) == [{k:v for k,v in s.items() if k != '_words'} for s in segments], label + ': JSON mismatch')
            check((directory/(kind+'.txt')).read_text() == '\n'.join(s['text'] for s in segments)+'\n', label + ': TXT mismatch')
            expected = [{'start_ms': math.ceil(s['start']*1000), 'end_ms': math.floor(s['end']*1000), 'text': s['text']} for s in segments]
            for suffix in ('.srt', '.vtt'):
                observed = timed_export(directory/(kind+suffix))
                check(observed == expected, label + ': ' + kind+suffix + ' does not preserve inward millisecond bounds/text')
        cases.append({'id': label, 'segments': len(candidate), 'segments_with_private_words': sum(bool(s.get('_words')) for s in candidate),
                      'segments_without_private_words': [i for i,s in enumerate(candidate) if not s.get('_words')],
                      'conflict_fallback_segment_indices': reverted, 'resolution': resolution,
                      'warnings': result['projection']['warnings'], 'unchanged_from_original_postpass': candidate == previous['candidate_segments'],
                      'timeline': [{'index':i, 'text':s['text'], 'baseline':[baseline[i]['start'],baseline[i]['end']],
                                    'candidate':[s['start'],s['end']], 'word_count':len(s.get('_words',[]))} for i,s in enumerate(candidate)]})
    film = new['case_results'][0]
    evaluation = read(OLD / 'evaluation-only.json')
    anchors = [{'criterion':a, 'baseline':audit.anchor_check(a,film['baseline_segments']),
                'candidate':audit.anchor_check(a,film['candidate_segments'])}
               for a in evaluation['existing_four_anchors']+evaluation['existing_command_regressions']]
    cues = audit.parse_cues(evaluation['reference_path'])
    check(len(cues) == evaluation['reference_cues'] == 76, 'Publisher cue count changed')
    comparison = audit.compare_all_cues(cues,film['baseline_segments'],film['candidate_segments'])
    result = {'schema_version':1, 'scope':'Independent retained-output audit of one offline local fallback replay; no native/model/recognition calls.',
              'auditor_sha256':sha(__file__), 'plan_sha256':sha(NEW/'plan.json'), 'report_sha256':sha(NEW/'results/report.json'),
              'raw_manifest_sha256':sha(NEW/'raw-results-manifest.json'), 'pinned_inputs_checked':len(plan['pinned_files']),
              'new_raw_files_checked':len(manifest['files']), 'original_raw_files_checked':len(old_manifest['files']),
              'contract_errors':errors, 'cases':cases, 'six_original_anchors':anchors, 'full_publisher_cue_comparison':comparison,
              'production_adoption_approved':False, 'semantic_or_acoustic_word_accuracy_approved':False,
              'original_global_fallback_profile_regraded':False, 'historical_provider_result_regraded':False}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'path':str(output),'sha256':sha(output),'contract_errors':errors,
                      'segment_anchor_passes':sum(a['candidate']['strict_segment_window_pass'] for a in anchors),
                      'word_anchor_passes':sum(a['candidate']['word_window_pass'] for a in anchors),
                      'cases':[{k:c[k] for k in ('id','segments','segments_with_private_words','conflict_fallback_segment_indices')} for c in cases]}))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
