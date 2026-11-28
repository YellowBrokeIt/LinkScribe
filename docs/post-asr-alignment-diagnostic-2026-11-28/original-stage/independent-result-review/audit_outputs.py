"""Independent retained-output audit; no speech/model/network execution."""
from __future__ import annotations

import difflib
import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'post-asr-alignment-diagnostic-2026-11-28'
RESULTS = BASE / 'results'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def normalize(text):
    # Exact existing analyzer normalization; no newly relaxed phrase matching.
    return ' '.join(re.findall(r'[^\W_]+', text.casefold().replace('’', "'").replace("'", '')))


def extent(items):
    return [min(item['start'] for item in items), max(item['end'] for item in items)] if items else None


def anchor_check(anchor, segments):
    low, high = anchor['window_seconds']
    contained = [s for s in segments if low <= s['start'] <= s['end'] <= high]
    words = [w for s in segments for w in s.get('_words', [])
             if low <= w['start'] <= w['end'] <= high]
    pattern = anchor.get('normalized_pattern', anchor.get('pattern'))
    full_text = ' '.join(s['text'] for s in segments)
    contained_text = ' '.join(s['text'] for s in contained)
    word_text = ''.join(w['word'] for w in words)
    return {
        'phrase_present': bool(re.search(pattern, normalize(full_text))),
        'strict_segment_window_pass': bool(re.search(pattern, normalize(contained_text))),
        'word_window_pass': bool(re.search(pattern, normalize(word_text))),
        'contained_segment_text': contained_text,
        'contained_word_text': word_text,
        'overlapping_segments': [s for s in segments if s['end'] >= low and s['start'] <= high],
    }


def parse_cues(path):
    text = Path(path).read_text(encoding='utf-8').replace('\r\n', '\n')
    cues = []
    def seconds(value):
        h, m, sec = value.replace(',', '.').split(':')
        return int(h) * 3600 + int(m) * 60 + float(sec)
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        start, end = lines[1].split(' --> ')
        cues.append({'id': int(lines[0]), 'start': seconds(start), 'end': seconds(end),
                     'text': ' '.join(lines[2:]).strip()})
    return cues


def compare_all_cues(cues, baseline, candidate):
    """Order-preserving exact-token diagnostic, with all unmatched tokens retained.

    No overlap score becomes an acceptance threshold. Subtitle text and timing
    are coarse references, not proof of acoustic word boundaries or ASR truth.
    """
    ref_words, ref_cue_ids, source_words, source_segment_ids = [], [], [], []
    for cue in cues:
        words = normalize(cue['text']).split()
        ref_words.extend(words)
        ref_cue_ids.extend([cue['id']] * len(words))
    for index, segment in enumerate(baseline):
        words = normalize(segment['text']).split()
        source_words.extend(words)
        source_segment_ids.extend([index] * len(words))
    match = difflib.SequenceMatcher(a=ref_words, b=source_words, autojunk=False)
    ref_to_source = {}
    for block in match.get_matching_blocks():
        for offset in range(block.size):
            ref_to_source[block.a + offset] = block.b + offset
    source_word_times = []
    for index, segment in enumerate(candidate):
        expected = normalize(baseline[index]['text']).split()
        words = [(token, word) for word in segment.get('_words', [])
                 for token in normalize(word['word']).split()]
        if [token for token, word in words] == expected:
            source_word_times.extend([word for token, word in words])
        else:
            source_word_times.extend([None] * len(expected))
    rows = []
    for cue in cues:
        ref_indices = [i for i, cue_id in enumerate(ref_cue_ids) if cue_id == cue['id']]
        mapped = [ref_to_source[i] for i in ref_indices if i in ref_to_source]
        segment_ids = sorted({source_segment_ids[i] for i in mapped})
        timed_words = [source_word_times[i] for i in mapped if source_word_times[i] is not None]
        rows.append({**cue, 'reference_tokens': len(ref_indices), 'matched_reference_tokens': len(mapped),
                     'unmatched_reference_tokens': [ref_words[i] for i in ref_indices if i not in ref_to_source],
                     'matched_source_segment_indices': segment_ids,
                     'matched_source_text': ' '.join(baseline[i]['text'] for i in segment_ids),
                     'baseline_parent_extent': extent([baseline[i] for i in segment_ids]),
                     'candidate_parent_extent': extent([candidate[i] for i in segment_ids]),
                     'candidate_matched_word_extent': extent(timed_words),
                     'matched_tokens_without_word_timing': len(mapped) - len(timed_words)})
    matched_sources = set(ref_to_source.values())
    unmatched = [{'source_token': word, 'segment_index': source_segment_ids[i]}
                 for i, word in enumerate(source_words) if i not in matched_sources]
    return {'method': 'Global order-preserving exact-token SequenceMatcher, autojunk=False; diagnostic only.',
            'acceptance_threshold': None, 'publisher_cues': len(cues), 'rows': rows,
            'source_tokens_not_matched_to_publisher': unmatched,
            'reference_gaps_are_not_automatic_asr_errors': True,
            'coarse_publisher_cues_are_not_acoustic_word_ground_truth': True}


def main():
    output = HERE / 'independent-output-audit.json'
    if output.exists():
        raise ValueError('Refusing to overwrite the independent audit.')
    before = read(HERE / 'source-and-criteria-before-output.json')
    errors = []
    def check(value, message):
        if not value:
            errors.append(message)
    for item in before['source_identities']:
        check(sha(item['path']) == item['sha256'], 'Frozen input changed: ' + item['path'])
    plan, inputs, evaluation = read(BASE/'plan.json'), read(BASE/'input-cases.json'), read(BASE/'evaluation-only.json')
    execution, report = read(RESULTS/'execution.json'), read(RESULTS/'report.json')
    check(execution['execution_contract_passed'] is True and not execution['final_gate_errors'], 'Owner execution gate failed')
    check(execution['worker_returncode'] == 0 and not execution['limit_stop'] and not execution['controller_error'], 'Worker/controller failed')
    check(execution['cleanup']['leader_exited'] and not execution['cleanup']['live_group_members_after_cleanup'], 'Owned worker cleanup failed')
    check(report['plan_sha256'] == sha(BASE/'plan.json') == execution['plan_sha256'], 'Result plan mismatch')
    check(report['complete'] and report['all_inputs_completed'] and report['model_unloaded'], 'Incomplete result/model lifecycle')
    check(report['recognition_performed'] is False, 'Unexpected recognition')
    check(report['native_calls'] == {'encode':23,'align':23,'generate':0,'detect_language':0}, 'Wrong exact native counts')
    check(0 < report['process_peak_rss_bytes'] <= plan['limits']['rss_bytes'], 'Worker high-water cap exceeded')
    check(0 < execution['elapsed_seconds'] <= plan['limits']['total_seconds'], 'Total time cap exceeded')
    check(0 <= report['startup_completed_monotonic'] - execution['started_monotonic'] <= plan['limits']['startup_seconds'], 'Startup cap exceeded')
    samples = [json.loads(line) for line in (RESULTS/'resource-samples.jsonl').read_text().splitlines()]
    check(bool(samples), 'Resource sample stream absent')
    peak = max((s['group_rss_bytes'] for s in samples), default=0)
    check(peak == execution['sampled_group_peak_rss_bytes'] and 0 < peak <= plan['limits']['rss_bytes'], 'Sampled resource peak mismatch/cap')
    check(all(a['elapsed_seconds'] <= b['elapsed_seconds'] for a,b in zip(samples,samples[1:])), 'Resource time order changed')
    cases = []
    check([c['id'] for c in report['case_results']] == plan['case_order'], 'Incomplete case order')
    for original, result in zip(inputs['cases'], report['case_results']):
        label = original['id']
        check(result['id'] == label and result['status'] == 'complete', label + ': incomplete case')
        if result['status'] != 'complete':
            cases.append({'id':label,'status':result['status'],'error':result.get('error')})
            continue
        baseline, candidate = result['baseline_segments'], result['candidate_segments']
        duration = original['array']['duration_seconds']
        expected_baseline = [{**s,'end':min(s['end'],duration)} for s in original['baseline_segments']]
        check(baseline == expected_baseline, label + ': physical bounded baseline changed')
        check([s['text'] for s in candidate] == [s['text'] for s in original['baseline_segments']], label + ': source strings/order changed')
        check(len(candidate) == len(original['raw_segments']), label + ': source segment count changed')
        check(result['full_input']['sha256'] == original['array']['pcm_sha256']
              and result['full_input']['sample_count'] == original['array']['sample_count'], label + ': full PCM changed')
        check(result['full_features']['shape'] == [80,original['array']['sample_count']//160+1], label + ': complete frontend extent changed')
        check([w['window'] for w in result['windows']] == original['windows'], label + ': original windows changed')
        check(0 <= result['elapsed_seconds'] <= plan['limits']['per_input_seconds'], label + ': input time cap')
        check(result['process_peak_rss_bytes_so_far'] <= plan['limits']['rss_bytes'], label + ': input peak cap')
        for number, window in enumerate(result['windows']):
            check(window.get('encode_attempt_recorded') and window.get('encode_completed')
                  and window.get('align_attempt_recorded') and window.get('align_completed'), label + ': incomplete native window ' + str(number))
            for index, adjusted in zip(window['window']['segment_indices'],window['upstream_adjusted_segments']):
                source = original['raw_segments'][index]
                check(adjusted['text'] == source['text'] and adjusted['tokens'] == source['tokens'], label + ': native source tokens/text changed')
        word_count = 0
        for index, segment in enumerate(candidate):
            check(all(type(segment[k]) in (int,float) and math.isfinite(segment[k]) for k in ('start','end'))
                  and 0 <= segment['start'] < segment['end'] <= duration, label + ': invalid physical parent interval')
            words = segment.get('_words',[])
            word_count += len(words)
            if words:
                check(''.join(w['word'] for w in words).strip() == segment['text'], label + ': word/source reconstruction')
                for word in words:
                    check(0 <= word['start'] < word['end'] <= duration and segment['start']-.05 <= word['start']
                          and word['end'] <= segment['end']+.05, label + ': invalid private word')
                check(all(a['end'] <= b['start']+.001 for a,b in zip(words,words[1:])), label + ': unordered private words')
        check(all(a['end'] <= b['start']+1e-9 for a,b in zip(candidate,candidate[1:])), label + ': unordered projected segments')
        directory = RESULTS/label
        for kind, segments in [('baseline',baseline),('candidate',candidate)]:
            expected = [{k:v for k,v in s.items() if k != '_words'} for s in segments]
            check(read(directory/(kind+'.json')) == expected, label + ': JSON export mismatch')
            check((directory/(kind+'.txt')).read_text() == '\n'.join(s['text'] for s in segments)+'\n', label + ': TXT export mismatch')
        cases.append({'id':label,'segments':len(candidate),'aligned_words':word_count,
                      'segments_with_word_timing':sum(bool(s.get('_words')) for s in candidate),
                      'fallback_segment_indices':result['projection']['fallback_segment_indices'],
                      'global_candidate_ordered':result['projection']['global_candidate_ordered'],
                      'changed_intervals':[{'index':i,'text':a['text'],'baseline':[a['start'],a['end']],
                                            'candidate':[b['start'],b['end']]} for i,(a,b) in enumerate(zip(baseline,candidate))
                                           if (a['start'],a['end']) != (b['start'],b['end'])],
                      'warnings':result['projection']['warnings'],'elapsed_seconds':result['elapsed_seconds']})
    film = report['case_results'][0]
    anchors, full_reference = [], None
    if film['status'] == 'complete':
        for anchor in evaluation['existing_four_anchors'] + evaluation['existing_command_regressions']:
            anchors.append({'criterion':anchor,'baseline':anchor_check(anchor,film['baseline_segments']),
                            'candidate':anchor_check(anchor,film['candidate_segments'])})
        cues = parse_cues(evaluation['reference_path'])
        check(len(cues)==evaluation['reference_cues']==76,'Publisher cue count changed')
        full_reference = compare_all_cues(cues,film['baseline_segments'],film['candidate_segments'])
    result={'schema_version':1,'scope':'Independent retained-output integrity and timing diagnostics; no model or production execution.',
            'source_criteria_sha256':sha(HERE/'source-and-criteria-before-output.json'),
            'auditor_sha256':sha(__file__),'report_sha256':sha(RESULTS/'report.json'),
            'execution_sha256':sha(RESULTS/'execution.json'),'sample_stream_sha256':sha(RESULTS/'resource-samples.jsonl'),
            'contract_errors':errors,'resource_samples':len(samples),'execution':execution,
            'case_reviews':cases,'six_original_anchors':anchors,'full_publisher_cue_comparison':full_reference,
            'semantic_or_acoustic_accuracy_approved':False,'production_adoption_approved':False,
            'historical_provider_result_regraded':False}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'path':str(output),'sha256':sha(output),'contract_errors':errors,
                      'anchor_segment_passes':sum(a['candidate']['strict_segment_window_pass'] for a in anchors),
                      'anchor_word_passes':sum(a['candidate']['word_window_pass'] for a in anchors),
                      'cases':[{'id':c['id'],'aligned_words':c.get('aligned_words'),'fallbacks':c.get('fallback_segment_indices')} for c in cases]}))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
