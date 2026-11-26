"""Postselection diagnostic only; never substitutes references into recognition.

The production app currently discards confidence fields, so this bounded replay
uses the same weights and decoding options plus word_timestamps=True to expose
per-word probabilities. Exact text agreement with the original production
output is recorded before confidence is interpreted. This is not an application
workflow test or calibration set, and must not be counted as fresh validation.
"""
from pathlib import Path
import hashlib
import json
import os
import time
from datetime import datetime, timezone

os.environ['ORT_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
ROOT = Path(__file__).resolve().parent
os.environ['HF_HOME'] = str(ROOT / 'hf-cache')

import onnxruntime
onnxruntime.disable_telemetry_events()
from faster_whisper import WhisperModel


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT / 'turbo-confidence-diagnostic.json'
    assert not output.exists(), 'Preserve earlier evidence; choose a new filename for another run'
    specifications = [
        ('turbo-fresh-auto-result.json', 'fresh-fixtures.json', 'fleurs-fresh-el_gr-validation-12-1558', None, 'accurate_Greek_control'),
        ('turbo-fresh-auto-result.json', 'fresh-fixtures.json', 'fleurs-fresh-el_gr-validation-13-1564', None, 'material_uncertainty_word_error'),
        ('turbo-development-result.json', 'fixtures.json', 'fleurs-en_us-validation-2-1510', 'en', 'accurate_English_control'),
        ('turbo-development-result.json', 'fixtures.json', 'fleurs-en_us-validation-3-1578', 'en', 'material_name_and_content_errors'),
    ]
    report = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
              'complete': False, 'purpose': 'postselection_confidence_diagnostic_not_calibration_or_fresh_validation',
              'model': 'large-v3-turbo', 'model_provenance': json.loads((ROOT / 'model-provenance-large-v3-turbo.json').read_text()),
              'options': {'device': 'cpu', 'compute_type': 'int8', 'beam_size': 5,
                          'vad_filter': True, 'condition_on_previous_text': False, 'word_timestamps': True},
              'production_difference': 'word_timestamps=True is added solely to expose actual word probabilities; exact output matching is recorded.',
              'telemetry_opt_out': {'ORT_DISABLE_TELEMETRY': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
                                    'onnxruntime_disable_telemetry_events_called': True},
              'reference_supplied_to_decoder': False, 'cases': []}
    started = time.monotonic()
    model = WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')
    for report_name, fixture_name, identifier, language, role in specifications:
        source = json.loads((ROOT / report_name).read_text())
        original = next(c for c in source['cases'] if c['id'] == identifier)
        fixtures = json.loads((ROOT / fixture_name).read_text())
        fixture = next(c for c in fixtures['cases'] if c['id'] == identifier)
        audio = ROOT / fixture['audio_file']
        assert digest(audio) == fixture['audio_sha256']
        case_started = time.monotonic()
        segments, info = model.transcribe(str(audio), language=language, beam_size=5,
                                         vad_filter=True, condition_on_previous_text=False,
                                         word_timestamps=True)
        captured = []
        for segment in segments:
            captured.append({'start': segment.start, 'end': segment.end, 'text': segment.text.strip(),
                             'avg_logprob': segment.avg_logprob, 'no_speech_prob': segment.no_speech_prob,
                             'compression_ratio': segment.compression_ratio,
                             'words': [{'word': w.word, 'probability': w.probability, 'start': w.start, 'end': w.end}
                                       for w in segment.words or []]})
        hypothesis = ' '.join(s['text'] for s in captured)
        case = {'id': identifier, 'diagnostic_role': role,
                'source_report': report_name, 'source_report_sha256': digest(ROOT / report_name),
                'audio_sha256': fixture['audio_sha256'], 'language_argument': language,
                'detected_language': info.language, 'language_probability': info.language_probability,
                'production_hypothesis': original['hypothesis'], 'hypothesis': hypothesis,
                'exact_text_matches_production': hypothesis == original['hypothesis'],
                'reference': fixture['reference'], 'segments': captured,
                'elapsed_seconds': round(time.monotonic() - case_started, 3)}
        report['cases'].append(case)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'id': identifier, 'exact_text_matches_production': case['exact_text_matches_production'],
                          'avg_logprob': [s['avg_logprob'] for s in captured]}, ensure_ascii=False), flush=True)
    report['complete'] = True
    report['elapsed_seconds'] = round(time.monotonic() - started, 3)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
