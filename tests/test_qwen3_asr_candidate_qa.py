"""Non-model regression checks for the isolated hosted QA contract."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HELPER = Path(__file__).with_name("qa_qwen3_asr_candidate.py")
SPEC = importlib.util.spec_from_file_location("qwen3_asr_candidate_qa", HELPER)
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)
PLAN = qa.ROOT / "docs/qwen3-asr-screen-2026-11-28/plan.json"


class QwenCandidateContractTests(unittest.TestCase):
    def test_frozen_plan_passes_without_model_dependencies(self):
        plan = qa.validate_plan(PLAN)
        self.assertEqual(len(plan["cases"]), 8)
        self.assertEqual(plan["source_language_argument"], None)

    def test_import_and_validation_do_not_import_ml(self):
        program = (
            "import runpy,sys; m=runpy.run_path(sys.argv[1]); "
            "m['validate_plan'](sys.argv[2]); "
            "assert not ({'torch','transformers','numpy','av'} & set(sys.modules))"
        )
        result = subprocess.run([sys.executable, "-c", program, str(HELPER), str(PLAN)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_inputs_and_generation_cannot_silently_change(self):
        original = json.loads(PLAN.read_text(encoding="utf-8"))
        mutations = [
            lambda p: p["cases"][0].update(pcm_sha256="0" * 64),
            lambda p: p["cases"][0].update(sample_count=16000),
            lambda p: p["cases"].reverse(),
            lambda p: p["generation"].update(max_new_tokens=1024),
            lambda p: p.update(source_language_argument="Greek"),
            lambda p: p.update(model_initializations=2),
            lambda p: p["source_files"][0].update(sha256="0" * 64),
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "plan.json"
            for index, mutate in enumerate(mutations):
                with self.subTest(mutation=index):
                    changed = copy.deepcopy(original)
                    mutate(changed)
                    qa.write_json(path, changed)
                    with self.assertRaises(ValueError):
                        qa.validate_plan(path)

    def test_local_heavy_execution_is_denied(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "GitHub Actions"):
                qa.require_hosted()

    def test_native_eos_and_stream_match_are_required(self):
        prefix = [11, 12]
        eos = [151643, 151645]
        complete = prefix + [21, 22, eos[1]]
        self.assertTrue(all(qa.validate_generation(prefix, complete, complete, eos, 512).values()))
        examples = [
            (prefix, prefix + [21, 22], prefix + [21, 22]),
            (prefix, complete, complete[:-1]),
            (prefix, [99] + complete[1:], complete),
            (prefix, prefix + [eos[0], 21, eos[1]], prefix + [eos[0], 21, eos[1]]),
            ([], [21, eos[1]], [21, eos[1]]),
        ]
        for index, (p, returned, streamed) in enumerate(examples):
            with self.subTest(invalid_completion=index):
                self.assertFalse(all(qa.validate_generation(p, returned, streamed, eos, 512).values()))

    def test_token_cap_is_not_a_completed_transcript(self):
        sequence = [7, 8, 9, 151645]
        self.assertFalse(qa.validate_generation([7], sequence, sequence, [151645], 2)["within_declared_token_bound"])
        with self.assertRaises(ValueError):
            qa.validate_generation([True], [True, 151645], [True, 151645], [151645], 512)

    def test_raw_text_preserves_repetitions_and_words(self):
        raw = "language Greek<asr_text>όχι όχι όχι  Number One"
        self.assertEqual(qa.raw_asr_body(raw), "όχι όχι όχι  Number One")
        self.assertEqual(qa.raw_asr_body("malformed output"), "malformed output")

    def test_frozen_full_clip_feature_lengths(self):
        self.assertEqual(qa.mel_contract(96000),
                         {"valid_frames": 600, "padded_frames": 600, "audio_placeholder_tokens": 78})
        self.assertEqual(qa.mel_contract(106560),
                         {"valid_frames": 666, "padded_frames": 700, "audio_placeholder_tokens": 87})
        with self.assertRaises(ValueError):
            qa.mel_contract(106559)

    def test_paths_cannot_escape_inventory_or_repository(self):
        for name in ["../model", "/model", "a/b", "a\\b", ".", "..", "a?b"]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    qa.safe_filename(name)
        self.assertEqual(qa.safe_filename("model.safetensors"), "model.safetensors")
        with self.assertRaises(ValueError):
            qa.repo_file("../outside.json")
        with self.assertRaises(ValueError):
            qa.repo_file(str(HELPER.resolve()))

    def test_public_urls_strip_signed_query_and_reject_credentials(self):
        self.assertEqual(qa.public_url_without_query("https://example.org/audio.wav?signature=test"),
                         "https://example.org/audio.wav")
        for url in ["file:///tmp/model", "http://example.org/model", "https://user:secret@example.org/model"]:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    qa.public_url_without_query(url)

    def test_download_requires_actual_size_hash_and_no_retry(self):
        content = b"pinned bytes"
        digest = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "fixture.wav"
            with mock.patch.object(qa.urllib.request, "urlopen", return_value=io.BytesIO(content)):
                row = qa.download_pinned("https://example.org/audio.wav", target, len(content), digest, 1)
            self.assertEqual(row["sha256"], digest)
            with self.assertRaises(ValueError):
                qa.download_pinned("https://example.org/audio.wav", target, len(content), digest, 1)
            bad = Path(folder) / "bad.wav"
            with mock.patch.object(qa.urllib.request, "urlopen", return_value=io.BytesIO(content)):
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    qa.download_pinned("https://example.org/audio.wav", bad, len(content), "0" * 64, 1)
            self.assertFalse(bad.exists())
            self.assertTrue(bad.with_suffix(".wav.partial").exists())

    def test_cpu_selection_respects_available_affinity(self):
        self.assertEqual(qa.cpu_selection({8, 9}), [8, 9])
        self.assertEqual(qa.cpu_selection({0, 1, 2, 3, 4, 5}), [0, 1, 2, 3])
        with self.assertRaises(ValueError):
            qa.cpu_selection(set())

    @unittest.skipUnless(sys.platform == "linux", "owned process-group cleanup is Linux hosted only")
    def test_cleanup_stops_owned_process(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(15)"], start_new_session=True)
        try:
            qa.terminate_owned(process)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    @unittest.skipUnless(sys.platform == "linux", "owned process-group cleanup is Linux hosted only")
    def test_cleanup_stops_child_after_leader_exits(self):
        program = ("import subprocess,sys; p=subprocess.Popen([sys.executable,'-c',"
                   "'import time; time.sleep(15)']); print(p.pid,flush=True)")
        process = subprocess.Popen([sys.executable, "-c", program], stdout=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            child_pid = int(process.stdout.readline())
            process.wait(timeout=5)
            self.assertIn(child_pid, qa.live_group_members(process.pid))
            cleanup = qa.terminate_owned(process)
            self.assertTrue(cleanup["leader_exited"])
            self.assertEqual(cleanup["live_group_members_after_cleanup"], [])
            self.assertNotIn(child_pid, qa.live_group_members(process.pid))
        finally:
            qa.terminate_owned(process)
            process.stdout.close()


if __name__ == "__main__":
    unittest.main()
