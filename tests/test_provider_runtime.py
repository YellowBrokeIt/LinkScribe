"""Exercise LinkScribe's runtime policy at the actual yt-dlp API boundary."""
from __future__ import annotations

import pytest
import yt_dlp

import runtime_check


def _provider_smoke():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).with_name("smoke_real_links.py")
    spec = importlib.util.spec_from_file_location("provider_smoke_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("explicit_rate", [False, True])
def test_real_decode_observer_preserves_audio_identity_and_measures_actual_samples(explicit_rate):
    import hashlib
    import numpy as np
    from types import SimpleNamespace
    observed, calls = [], []
    audio = np.full(480, 0.1, dtype=np.float32)

    def decode_audio(input_file, sampling_rate=16000, split_stereo=False):
        calls.append((input_file, sampling_rate, split_stereo))
        return audio

    target = SimpleNamespace(decode_audio=decode_audio)
    _provider_smoke().observe_audio_decode(target, lambda kind, **data: observed.append((kind, data)))
    rate = 8000 if explicit_rate else 16000
    result = target.decode_audio("owned-job/audio.wav", **({"sampling_rate": rate} if explicit_rate else {}))
    assert result is audio
    assert calls == [("owned-job/audio.wav", rate, False)]
    assert observed == [("audio_decoded", {"job_id": "owned-job", "sampling_rate_hz": rate,
        "decoded_arrays": [{"array_identity": hex(id(audio)), "shape": [480], "dtype": audio.dtype.str,
                            "sample_count": 480, "nonzero_sample_count": 480,
                            "pcm_sha256": hashlib.sha256(audio.tobytes()).hexdigest()}],
        "channel_sample_counts": [480], "decoded_duration_seconds": 480 / rate})]


def test_real_decode_observer_does_not_turn_a_decoder_error_into_success():
    from types import SimpleNamespace
    observed = []
    error = ValueError("Owned invalid audio fixture")

    def decode_audio(input_file, sampling_rate=16000):
        raise error

    target = SimpleNamespace(decode_audio=decode_audio)
    _provider_smoke().observe_audio_decode(target, lambda *args, **kwargs: observed.append((args, kwargs)))
    with pytest.raises(ValueError) as caught:
        target.decode_audio("owned-job/audio.wav")
    assert caught.value is error
    assert observed == []


def test_vad_observers_preserve_original_intervals_and_collected_audio():
    from dataclasses import dataclass
    from types import SimpleNamespace

    @dataclass
    class Options:
        threshold: float = 0.5
        max_speech_duration_s: float = float("inf")

    audio = list(range(12))
    chunks = [{"start": 1, "end": 3}, {"start": 8, "end": 10}]
    collected = ([audio[1:3], audio[8:10]], [{"offset": 0, "duration": 0.4}])
    options, calls, observed = Options(), [], []

    def get_speech_timestamps(value, vad_options=None, sampling_rate=10, **kwargs):
        calls.append(("vad", value, vad_options))
        return chunks

    def collect_chunks(value, selected, sampling_rate=10, max_duration=float("inf")):
        calls.append(("collect", value, selected))
        return collected

    target = SimpleNamespace(get_speech_timestamps=get_speech_timestamps, collect_chunks=collect_chunks)
    _provider_smoke().observe_speech_selection(target, lambda kind, **data: observed.append((kind, data)),
                                               lambda: "owned-job")
    assert target.get_speech_timestamps(audio, options) is chunks
    assert target.collect_chunks(audio, chunks) is collected
    assert calls[0][1] is calls[1][1] is audio
    assert calls[0][2] is options and calls[1][2] is chunks
    assert observed[0][1]["intervals"] == [{"start_sample": 1, "end_sample": 3},
                                          {"start_sample": 8, "end_sample": 10}]
    assert observed[0][1]["kept_sample_count"] == observed[1][1]["sample_count"] == 4
    assert observed[0][1]["last_kept_end_seconds"] == 1
    assert observed[1][1]["duration_seconds"] == 0.4
    assert observed[0][1]["vad_options"]["max_speech_duration_s"] == {"nonfinite_float": "inf"}


@pytest.mark.parametrize("fail", [False, True])
def test_whole_recording_observer_keeps_original_array_intervals_and_error(fail):
    from dataclasses import dataclass
    from types import SimpleNamespace
    import numpy as np

    @dataclass
    class Options:
        threshold: float = 0.5
        max_speech_duration_s: float = float("inf")

    audio = np.arange(16, dtype=np.float32)
    intervals = [{"start": 2, "end": 14}]
    error = RuntimeError("Owned corroboration failure")
    calls, events = [], []

    def detect(value, vad_options=None, sampling_rate=16000, **kwargs):
        calls.append((value, vad_options, sampling_rate, kwargs))
        if fail:
            raise error
        return intervals

    target = SimpleNamespace(get_speech_timestamps=detect, VadOptions=Options)
    _provider_smoke().observe_whole_recording_speech(target,
        lambda kind, **fields: events.append((kind, fields)), lambda: "owned-job")
    if fail:
        with pytest.raises(RuntimeError) as caught:
            target.get_speech_timestamps(audio, sampling_rate=16000)
        assert caught.value is error
        assert events[0][0] == "whole_recording_speech_check_failed"
    else:
        assert target.get_speech_timestamps(audio, sampling_rate=16000) is intervals
        assert events[0][0] == "whole_recording_speech_check"
        assert events[0][1]["intervals"] == intervals
        assert events[0][1]["vad_options"]["threshold"] == 0.5
    assert len(calls) == len(events) == 1 and calls[0][0] is audio
    assert calls[0][1:] == (None, 16000, {})
    assert events[0][1]["input_array_before"] == events[0][1]["input_array_after"]
    assert events[0][1]["input_array_before"]["array_identity"] == hex(id(audio))


@pytest.mark.parametrize("missing_tokenizer", [False, True])
def test_actual_resolver_files_are_hashed_without_replacing_result_or_exposing_token(tmp_path, missing_tokenizer):
    from types import SimpleNamespace
    import hashlib
    import json

    class ResolverPath(str):
        pass

    revision = "a" * 40
    path = tmp_path / "models--owned--model" / "snapshots" / revision
    path.mkdir(parents=True)
    names = ["model.bin", "config.json", "vocabulary.txt"] + ([] if missing_tokenizer else ["tokenizer.json"])
    for name in names:
        (path / name).write_bytes(("owned " + name).encode())
    original_result = ResolverPath(str(path))
    calls, events = [], []

    def resolve(size_or_id, revision=None, local_files_only=False, use_auth_token=None):
        calls.append((size_or_id, revision, local_files_only, use_auth_token))
        return original_result

    target = SimpleNamespace(download_model=resolve)
    _provider_smoke().observe_model_resolution(target,
        lambda kind, **fields: events.append((kind, fields)), lambda: "owned-job")
    result = target.download_model("small", revision=revision, use_auth_token="owned-private-token")
    assert result is original_result
    assert calls == [("small", revision, False, "owned-private-token")]
    kind, details = events[0]
    assert kind == "asr_model_resolved" and details["resolved_revision"] == revision
    assert details["identity_complete"] is (not missing_tokenizer)
    assert set(details["files"]) == set(names)
    assert details["files"]["model.bin"] == {"bytes": len(b"owned model.bin"),
        "sha256": hashlib.sha256(b"owned model.bin").hexdigest()}
    assert "owned-private-token" not in json.dumps(events)


def test_tail_audio_is_bounded_copied_and_never_changes_normal_decoded_samples():
    import numpy as np
    smoke = _provider_smoke()
    audio = np.arange(6000, dtype=np.float32)
    windows = smoke.prepare_tail_windows(audio, 10)
    assert sum(item["duration_seconds"] for item in windows) == 48
    assert [(item["start_sample"], item["end_sample"]) for item in windows] == [
        (4240, 4340), (5020, 5220), (5530, 5710)]
    assert all(not np.shares_memory(audio, item["audio"]) for item in windows)
    windows[0]["audio"][0] = -100
    assert audio[4240] == 4240
    clipped = smoke.prepare_tail_windows(audio[:5050], 10)
    assert clipped[-1]["sample_count"] == 0
    assert clipped[-1]["start_sample"] == clipped[-1]["end_sample"] == 5050


@pytest.mark.parametrize("failure", [None, "before_output", "after_partial_output"])
def test_tail_diagnostic_is_separate_and_retains_partial_failure(tmp_path, failure):
    from dataclasses import dataclass
    import json
    import numpy as np

    @dataclass
    class Segment:
        start: float
        end: float
        text: str

    @dataclass
    class Info:
        language: str
        duration: float

    class Engine:
        def __init__(self):
            self.calls = []

        def transcribe(self, samples, **settings):
            self.calls.append((samples, settings))
            if failure == "before_output" and len(self.calls) == 2:
                raise ValueError("Owned diagnostic error")
            if failure == "after_partial_output" and len(self.calls) == 2:
                def partial():
                    yield Segment(0, 1, "Owned partial diagnostic text")
                    raise ValueError("Owned diagnostic generator error")
                return partial(), Info("en", len(samples) / 10)
            return iter([Segment(0, 1, "Owned diagnostic text only")]), Info("en", len(samples) / 10)

    smoke, engine = _provider_smoke(), Engine()
    windows = smoke.prepare_tail_windows(np.zeros(6000, dtype=np.float32), 10)
    path = tmp_path / "diagnostic.json"
    report = smoke.run_tail_diagnostic(engine, windows, path, {"model": "small"},
                                      lambda: "unchanged-owned-saved-record")
    assert len(engine.calls) == 3
    assert all(settings == {"language": "en", "beam_size": 5, "vad_filter": False,
        "condition_on_previous_text": False, "word_timestamps": False} for _, settings in engine.calls)
    assert report["complete"] and report["normal_record_unchanged"]
    assert report["semantic_quality"] == "unreviewed"
    assert report["execution_status"] == ("error" if failure else "completed")
    assert report["cases"][1]["status"] == ("error" if failure else "completed")
    assert report["cases"][0]["raw_segments"][0]["text"] == "Owned diagnostic text only"
    if failure == "after_partial_output":
        assert report["cases"][1]["raw_segments"][0]["text"] == "Owned partial diagnostic text"
    assert json.loads(path.read_text()) == report


@pytest.mark.parametrize("raise_error", [False, True])
def test_normal_transcribe_observer_preserves_return_identity_and_real_failure(raise_error):
    from dataclasses import dataclass
    from types import SimpleNamespace

    @dataclass
    class Info:
        duration: float = 2.0
        duration_after_vad: float = 2.0
        vad_options: object = None

    result = (iter([]), Info())
    calls, events = [], []

    class Model:
        def transcribe(self, audio, language=None, vad_filter=True, clip_timestamps="0"):
            calls.append((audio, language, vad_filter, clip_timestamps))
            if raise_error:
                raise ValueError("Owned real-boundary error")
            return result

    _provider_smoke().observe_transcribe(SimpleNamespace(WhisperModel=Model),
        lambda kind, **data: events.append((kind, data)), lambda: "owned-job")
    if raise_error:
        with pytest.raises(ValueError, match="Owned real-boundary error"):
            Model().transcribe("owned.wav", vad_filter=False)
    else:
        assert Model().transcribe("owned.wav", vad_filter=False) is result
    assert calls == [("owned.wav", None, False, "0")]
    assert events[0][1]["explicit_kwargs"] == {"vad_filter": False}
    assert events[0][1]["resolved_options"]["vad_filter"] is False
    assert [kind for kind, _ in events] == (["transcribe_request"] if raise_error else
                                           ["transcribe_request", "transcribe_info"])


def _normal_observations(vad=False, retained=2.0):
    metadata = {"array_identity": "owned-array", "shape": [32000], "dtype": "<f4",
                "sample_count": 32000, "nonzero_sample_count": 1, "pcm_sha256": "a" * 64}
    events = [
        {"kind": "audio_decoded", "decoded_duration_seconds": 2.0, "sampling_rate_hz": 16000,
         "channel_sample_counts": [32000], "decoded_arrays": [metadata]},
        {"kind": "transcribe_request", "explicit_kwargs": {"vad_filter": vad},
         "audio_array": dict(metadata),
         "resolved_options": {"vad_filter": vad, "clip_timestamps": "0"}},
        {"kind": "transcribe_info", "info": {"duration": 2.0, "duration_after_vad": retained,
                                                "vad_options": {"threshold": 0.5} if vad else None}},
    ]
    if vad:
        events += [{"kind": "vad_speech_intervals", "kept_sample_count": int(retained * 16000),
                    "last_kept_end_seconds": 1.75},
                   {"kind": "post_vad_audio", "sample_count": int(retained * 16000), "duration_seconds": retained}]
    return events


def test_observation_validation_distinguishes_requested_vad_from_full_audio():
    smoke = _provider_smoke()
    direct = smoke.transcription_evidence(_normal_observations())
    selected = smoke.transcription_evidence(_normal_observations(vad=True, retained=1.5))
    assert direct["normal_vad_filter"] is False and direct["post_vad_duration_seconds"] == 2
    assert direct["last_vad_kept_end_seconds"] is None
    assert selected["normal_vad_filter"] is True and selected["post_vad_duration_seconds"] == 1.5


@pytest.mark.parametrize("defect", [None, "different_array", "mutated_array", "low_asr_score", "out_of_bounds"])
def test_corroboration_evidence_is_separate_from_vad_prefilter_and_requires_full_audio(defect):
    from copy import deepcopy
    events = _normal_observations()
    events[1]["resolved_options"]["no_speech_threshold"] = 0.6
    events.append({"kind": "asr_segment_created", "segment": {"text": "Owned diagnostic", "no_speech_prob": 0.99}})
    check = {"kind": "whole_recording_speech_check", "input_array_before": deepcopy(events[0]["decoded_arrays"][0]),
             "input_array_after": deepcopy(events[0]["decoded_arrays"][0]), "sampling_rate_hz": 16000,
             "intervals": [{"start": 1, "end": 31999}]}
    events.append(check)
    if defect == "different_array":
        check["input_array_before"]["array_identity"] = "replacement-array"
    elif defect == "mutated_array":
        check["input_array_after"]["pcm_sha256"] = "b" * 64
    elif defect == "low_asr_score":
        events[-2]["segment"]["no_speech_prob"] = 0.5
    elif defect == "out_of_bounds":
        check["intervals"][0]["end"] = 32001
    if defect:
        with pytest.raises(AssertionError):
            _provider_smoke().transcription_evidence(events)
    else:
        result = _provider_smoke().transcription_evidence(events)
        assert result["normal_vad_filter"] is False
        assert result["last_vad_kept_end_seconds"] is None
        assert result["post_vad_duration_seconds"] == 2
        assert result["whole_recording_speech_checks"] == [check]


@pytest.mark.parametrize("kind", ["whole_recording_speech_check", "whole_recording_speech_check_failed", "asr_model_resolved"])
def test_zero_pcm_cannot_claim_no_model_activity_if_new_observers_ran(kind):
    zero = _normal_observations()[:1]
    zero[0]["decoded_arrays"][0]["nonzero_sample_count"] = 0
    zero.append({"kind": kind})
    with pytest.raises(AssertionError):
        _provider_smoke().nonspeech_evidence(zero, "silence")


@pytest.mark.parametrize("defect", ["repeated_decode", "different_array", "mutated_samples", "wrong_shape"])
def test_normal_asr_requires_the_single_unchanged_decoded_array(defect):
    events = _normal_observations()
    if defect == "repeated_decode":
        events.append(events[0])
    elif defect == "different_array":
        events[1]["audio_array"]["array_identity"] = "replacement-array"
    elif defect == "mutated_samples":
        events[1]["audio_array"]["pcm_sha256"] = "b" * 64
    else:
        events[0]["decoded_arrays"][0]["shape"] = [2, 16000]
        events[1]["audio_array"]["shape"] = [2, 16000]
    with pytest.raises(AssertionError):
        _provider_smoke().transcription_evidence(events)


def test_digital_silence_evidence_requires_zero_samples_and_no_inference():
    from copy import deepcopy
    smoke = _provider_smoke()
    zero = _normal_observations()[:1]
    zero[0]["decoded_arrays"][0]["nonzero_sample_count"] = 0
    result = smoke.nonspeech_evidence(zero, "silence")
    assert result["inference_attempted"] is False
    assert result["processing_path"] == "exact_digital_silence_rejected_before_inference"
    for bad in (zero + _normal_observations()[1:], _normal_observations()[:1]):
        with pytest.raises(AssertionError):
            smoke.nonspeech_evidence(bad, "silence")
    noise = _normal_observations()
    assert smoke.nonspeech_evidence(noise, "white_noise")["normal_vad_filter"] is False
    bad_noise = deepcopy(noise)
    bad_noise[0]["decoded_arrays"][0]["nonzero_sample_count"] = 0
    bad_noise[1]["audio_array"]["nonzero_sample_count"] = 0
    with pytest.raises(AssertionError):
        smoke.nonspeech_evidence(bad_noise, "white_noise")


@pytest.mark.parametrize("generator_error", [False, True])
def test_segment_scores_are_observed_without_replacing_tuple_generator_or_objects(generator_error):
    from dataclasses import dataclass
    from types import SimpleNamespace
    import numpy as np

    @dataclass
    class Word:
        start: float
        end: float
        word: str
        probability: float

    @dataclass
    class Segment:
        start: float
        end: float
        text: str
        avg_logprob: float
        no_speech_prob: float
        compression_ratio: float
        temperature: float
        words: list

    @dataclass
    class Info:
        language: str = "en"

    constructed, events = [], []
    failure = ValueError("Owned late generator failure")

    def generate():
        segment = Segment(0, 1, " Low-score text retained ", -99.0, 1.0, 12.0, 1.0,
                          [Word(0.1, 0.9, " retained", 0.0)])
        constructed.append(segment)
        yield segment
        if generator_error:
            raise failure

    generator = generate()
    result = (generator, Info())

    class Model:
        def transcribe(self, audio, vad_filter=False, clip_timestamps="0"):
            return result

    target, smoke = SimpleNamespace(WhisperModel=Model, Segment=Segment), _provider_smoke()
    event = lambda kind, **details: events.append((kind, details))
    smoke.observe_segment_creation(target, event, lambda: "owned-job")
    smoke.observe_transcribe(target, event, lambda: "owned-job")
    actual = Model().transcribe(np.ones(16, dtype=np.float32))
    assert actual is result and actual[0] is generator
    assert not any(kind == "asr_segment_created" for kind, _ in events)
    segment = next(actual[0])
    assert segment is constructed[0] and type(segment) is Segment
    scores = next(details["segment"] for kind, details in events if kind == "asr_segment_created")
    assert scores["avg_logprob"] == -99.0 and scores["no_speech_prob"] == 1.0
    assert scores["words"][0]["probability"] == 0.0 and scores["text"] == segment.text
    assert segment.words[0].probability == 0.0
    if generator_error:
        with pytest.raises(ValueError) as caught:
            next(actual[0])
        assert caught.value is failure
    else:
        with pytest.raises(StopIteration):
            next(actual[0])


@pytest.mark.parametrize("defect", ["requested_vad_missing", "unrequested_vad_present", "audio_lost_without_vad"])
def test_inconsistent_vad_evidence_cannot_pass(defect):
    if defect == "requested_vad_missing":
        events = _normal_observations(vad=True)[:3]
    elif defect == "unrequested_vad_present":
        events = _normal_observations() + _normal_observations(vad=True)[3:]
    else:
        events = _normal_observations(retained=1.0)
    with pytest.raises(AssertionError):
        _provider_smoke().transcription_evidence(events)


@pytest.mark.parametrize("kind", ["silence", "white_noise"])
def test_owned_nonspeech_fixture_has_bounded_duration_and_reproducible_pcm(kind):
    from array import array
    import io
    import wave
    smoke = _provider_smoke()
    payload, provenance = smoke.generated_nonspeech(kind)
    again, repeated = smoke.generated_nonspeech(kind)
    assert payload == again and provenance == repeated
    with wave.open(io.BytesIO(payload)) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) == (
            1, 2, 16000, 32 * 16000)
        samples = array("h", audio.readframes(audio.getnframes()))
    if kind == "silence":
        assert not any(samples)
    else:
        assert max(samples) > 0 and min(samples) < 0
    assert provenance["expected_speech"] == "none_by_construction"


@pytest.mark.parametrize("detected", [
    {"deno": "2.2.9", "node": "24.22.0"},
    {"deno": "unreadable version"},
    {},
])
def test_rejected_runtimes_are_not_reenabled_by_downloader_defaults(monkeypatch, detected):
    # Omitting js_runtimes lets yt-dlp re-enable Deno, even after our check
    # rejected it. Pass the real options to the real downloader (no network).
    monkeypatch.setattr(runtime_check, "runtime_details", lambda: {
        "runtime": None, "supported": False, "detected": detected,
    })
    with yt_dlp.YoutubeDL({"quiet": True, **runtime_check.yt_dlp_js_options()}) as downloader:
        assert downloader.params["js_runtimes"] == {}


def test_security_patched_node_fallback_does_not_enable_other_runtimes(monkeypatch):
    monkeypatch.setattr(runtime_check, "runtime_details", lambda: {
        "runtime": "node", "supported": True, "version": "24.22.1",
    })
    with yt_dlp.YoutubeDL({"quiet": True, **runtime_check.yt_dlp_js_options()}) as downloader:
        assert set(downloader.params["js_runtimes"]) == {"node"}


@pytest.mark.parametrize("setting", [None, "1", "0", "true", ""])
def test_system_certificate_store_requires_explicit_opt_in_without_disabling_tls(monkeypatch, tmp_path, setting):
    import app
    from sources import parse_source

    if setting is None:
        monkeypatch.delenv("LINKSCRIBE_USE_SYSTEM_CERTS", raising=False)
    else:
        monkeypatch.setenv("LINKSCRIBE_USE_SYSTEM_CERTS", setting)
    identifier = "c" * 32
    source = parse_source("https://www.dailymotion.com/video/xbvubxi")
    monkeypatch.setattr(app, "jobs", {identifier: app.Job(identifier, tmp_path, source.url)})
    observed = {}

    class Downloader:
        def __init__(self, options):
            observed.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def extract_info(self, url, download):
            assert url == source.url and download is False
            self.info = {"title": "Owned mocked downloader fixture", "duration": 1}
            return self.info

        def process_ie_result(self, info, download=True):
            assert info is self.info and download is True
            (tmp_path / "audio.wav").write_bytes(b"Mocked transport output; no live media request.")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", Downloader)
    path, _title = app._download_source_audio(identifier, source)
    assert path == tmp_path / "audio.wav"
    assert ("no-certifi" in observed.get("compat_opts", [])) is (setting == "1")
    assert not observed.get("nocheckcertificate")
    assert not observed.get("prefer_insecure")
