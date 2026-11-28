"""Freeze identities using the declared existing ASR environment; no model."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = Path('/workspace/scratch/94360995dd61/LinkScribe')
PRIOR = Path('/workspace/scratch/94360995dd61/post-asr-alignment-feasibility-2026-11-28')
SITE = Path('/workspace/scratch/94360995dd61/linkscribe-dev-venv/lib/python3.12/site-packages')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    model = json.loads((PRIOR / 'native-api-contract.json').read_text(encoding='utf-8'))['existing_model']
    cases = json.loads((ROOT / 'input-cases.json').read_text(encoding='utf-8'))['cases']
    baseline = json.loads((REPO / 'docs/asr-official-tail-2026-11-28/baseline-report.json').read_text(encoding='utf-8'))
    options = next(event for event in baseline['official_tail_protocol']['events'] if event['kind'] == 'transcribe_request')['resolved_options']
    files = [ROOT / name for name in ('run_postpass.py', 'check_native_contract.py', 'input-cases.json', 'production-timing-view.json')]
    files += [REPO / 'tests/qa_qwen3_asr_candidate.py', REPO / 'app.py']
    files += [SITE / 'faster_whisper' / name for name in ('transcribe.py', 'tokenizer.py', 'feature_extractor.py', 'audio.py', 'utils.py')]
    files += [SITE / 'ctranslate2/_ext.cpython-312-x86_64-linux-gnu.so']
    plan = {
        'schema_version': 1, 'status': 'prepared; no model execution',
        'candidate': 'fixed_text_complete_upstream_postpass_v2',
        'source_commit': '6de3faddf88bb5da8ea35d985b33ad26e55e249f',
        'input_cases_path': str(ROOT / 'input-cases.json'), 'case_order': [case['id'] for case in cases],
        'max_cpu_threads': 4, 'device': 'cpu', 'compute_type': 'int8', 'workers': 1,
        'expected_effective_compute_types': ['int8', 'int8_float32'],
        'attempts_per_input': 1, 'model_initializations': 1,
        'expected_window_calls': sum(len(case['windows']) for case in cases),
        'limits': {'rss_bytes': 2684354560, 'startup_seconds': 120, 'per_input_seconds': 240, 'total_seconds': 600},
        'reference_or_publisher_material_supplied': False, 'recognition_or_generation_allowed': False,
        'frontend': {'full_recording': True, 'sample_rate_hz': 16000, 'n_mels': 80, 'n_fft': 400,
                     'hop_length': 160, 'padding_samples': 160, 'max_window_frames': 3000, 'vad': False},
        'prepend_punctuations': options['prepend_punctuations'], 'append_punctuations': options['append_punctuations'],
        'model': {'path': model['path'], 'repo': model['repo'], 'revision': model['revision'],
                  'files': model['files_rehashed_without_loading']},
        'runtime_packages': {name: importlib.metadata.version(name) for name in
                             ('faster-whisper', 'ctranslate2', 'numpy', 'av', 'tokenizers', 'onnxruntime', 'huggingface-hub')},
        'monitor_path': str(REPO / 'tests/qa_qwen3_asr_candidate.py'),
        'pinned_files': [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)} for path in files],
        'proposal_path': str(ROOT / 'POSTPASS-PROPOSAL.md'), 'proposal_sha256': sha(ROOT / 'POSTPASS-PROPOSAL.md'),
        'measurement_scope': 'Owned worker process group sampled every 100 ms; controller/browser/OS headroom excluded and short peaks may be missed.',
        'execution_scope': 'Standalone timing postprocessor and frozen current timing/export view; not full application or acoustic speaker inference.',
    }
    (ROOT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    review = Path('/workspace/scratch/94360995dd61/post-asr-alignment-independent-review-2026-11-28/revised-postpass-proposal-review.json')
    assert sha(review) == '80a455b87555a22509a2a08ec26a28ea5c3c51c01ecb2971874989d5f9f11439'
    shutil.copyfile(review, ROOT / 'independent-revised-proposal-review.json')
    print(json.dumps({'plan_sha256': sha(ROOT / 'plan.json'), 'cases': len(cases),
                      'windows': sum(len(case['windows']) for case in cases), 'model_execution': False}))


if __name__ == '__main__':
    main()
