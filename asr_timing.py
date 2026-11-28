"""Optional fixed-text timing after recognition; never recognize or replace words.

This adapter uses the inspected regular faster-whisper interface. Unsupported
versions or unusable evidence leave the accepted transcript available to callers.
Timing is an estimate, not proof that the recognized words were spoken.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from importlib.metadata import version
import inspect
import math
from numbers import Real
from typing import Any, Callable


class TimingUnavailable(ValueError):
    """The optional timing contract could not be established."""


@dataclass
class TimingResult:
    segments: list[dict[str, Any]]
    warnings: list[str]
    provenance: dict[str, Any]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TimingUnavailable(message)


def _finite(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def _bounded(bound, start, end, duration):
    # The application owns the physical-bound policy and its user-facing error
    # type. Translate only this optional evidence check into a local fallback.
    try:
        return bound(start, end, duration)
    except Exception:
        raise TimingUnavailable("Invalid optional timing interval") from None


def unavailable(baseline: list[dict[str, Any]]) -> TimingResult:
    """An empty word list activates the existing whole-segment speaker fallback."""
    return TimingResult(
        [{**segment, "_words": []} for segment in baseline],
        ["Word timing could not be prepared; the original transcript and segment timings "
         "were retained. Speaker labels may remain unassigned."],
        {"method": "fixed_text_postpass", "status": "unavailable",
         "segment_count": len(baseline), "word_timed_segments": 0,
         "original_timing_segments": len(baseline)},
    )


def _runtime():
    # The requirements allow other releases for ordinary recognition. Do not
    # assume their private timing/window semantics match this inspected adapter.
    _require(version("faster-whisper") == "1.2.1" and version("ctranslate2") == "4.9.1",
             "Unreviewed native timing interface")
    from faster_whisper.audio import pad_or_trim
    from faster_whisper.tokenizer import Tokenizer
    from faster_whisper.transcribe import WhisperModel
    from faster_whisper.utils import get_end
    return WhisperModel, Tokenizer, pad_or_trim, get_end


def _validate_native_path(path, probabilities, text_count: int, num_frames: int) -> None:
    """Keep the terminal row N, which is a boundary and not an extra text token."""
    _require(text_count > 0 and num_frames >= 2, "Missing native alignment extent")
    _require(len(probabilities) == text_count and
             all(_finite(p) and 0 <= p <= 1 for p in probabilities), "Incomplete token probabilities")
    _require(isinstance(path, (list, tuple)) and bool(path), "Missing native path")
    for pair in path:
        _require(isinstance(pair, (list, tuple)) and len(pair) == 2 and
                 type(pair[0]) is int and type(pair[1]) is int and
                 0 <= pair[0] <= text_count and 0 <= pair[1] < num_frames // 2,
                 "Invalid native alignment index")
    _require(tuple(path[0]) == (0, 0) and tuple(path[-1]) == (text_count, num_frames // 2 - 1),
             "Incomplete native terminal boundary")
    _require(all((right[0] - left[0], right[1] - left[1]) in ((1, 0), (0, 1), (1, 1))
                 for left, right in zip(path, path[1:])), "Invalid native monotonic path")
    _require({pair[0] for pair in path} == set(range(text_count + 1)), "Missing native text coverage")


class _AlignOnly:
    """Expose only fixed-token alignment to the upstream timing code."""
    def __init__(self, native, encoded, tokenizer, text_tokens, num_frames):
        self.native, self.encoded = native, encoded
        self.start_sequence = list(tokenizer.sot_sequence)
        self.text_tokens, self.num_frames = list(text_tokens), num_frames
        self.calls = 0

    def align(self, encoded, start_sequence, text_tokens, num_frames, *, median_filter_width=7):
        _require(self.calls == 0 and encoded is self.encoded and
                 list(start_sequence) == self.start_sequence and text_tokens == [self.text_tokens] and
                 num_frames == self.num_frames and median_filter_width == 7,
                 "Fixed-text alignment request changed")
        self.calls += 1
        results = self.native.align(encoded, start_sequence, text_tokens, num_frames,
                                    median_filter_width=median_filter_width)
        _require(len(results) == 1, "Incomplete native result batch")
        _validate_native_path(results[0].alignments, results[0].text_token_probs,
                              len(self.text_tokens), num_frames)
        return results


class _TimingAdapter:
    def __init__(self, engine, native_class, encoded, tokenizer, text_tokens, num_frames):
        self.model = _AlignOnly(engine.model, encoded, tokenizer, text_tokens, num_frames)
        self.frames_per_second = engine.frames_per_second
        self.tokens_per_second = engine.tokens_per_second
        self.native_class = native_class
        self.alignment = None

    def find_alignment(self, *args, **kwargs):
        self.alignment = self.native_class.find_alignment(self, *args, **kwargs)
        # The upstream punctuation/duration pass mutates this same list. Retain
        # it only for this window's exact token-to-segment boundary check.
        return self.alignment


def _conflicts(segments):
    return {index for i, (left, right) in enumerate(zip(segments, segments[1:]))
            if right["start"] < left["end"] - 1e-9 for index in (i, i + 1)}


def _valid_interval(segment, duration):
    start, end = segment.get("start"), segment.get("end")
    return _finite(start) and _finite(end) and 0 <= start < end <= duration


def resolve_interval_conflicts(candidates, baseline, duration):
    """Restore both conflicting endpoints, then check newly affected neighbors."""
    _require(_finite(duration) and duration > 0 and len(candidates) == len(baseline) > 0,
             "Incomplete source intervals")
    _require(all(_valid_interval(s, duration) for s in baseline) and not _conflicts(baseline),
             "No physically ordered baseline for timing fallback")
    _require(all(_valid_interval(s, duration) for s in candidates) and
             [s.get("text") for s in candidates] == [s.get("text") for s in baseline],
             "Invalid candidate timing or changed source text")
    output, reverted = deepcopy(candidates), set()
    for _ in range(len(output) + 1):
        incident = _conflicts(output)
        if not incident:
            return output, reverted
        _require(bool(incident - reverted), "Conflicting baseline intervals")
        for index in incident:
            output[index].update(start=baseline[index]["start"], end=baseline[index]["end"], _words=[])
        reverted.update(incident)
    raise TimingUnavailable("Timing fallback did not converge")


def project_segments(baseline, raw, adjusted, mapping, windows, duration, bound: Callable) -> TimingResult:
    """Preserve text; bad optional intervals revert without invented durations."""
    _require(len(baseline) == len(raw) == len(adjusted) == len(mapping) == len(windows) > 0,
             "Incomplete fixed source projection")
    output, fallback = [], set()
    for index, (original, native, candidate, mapped, window) in enumerate(
            zip(baseline, raw, adjusted, mapping, windows)):
        _require(candidate["text"] == native["text"] and candidate["tokens"] == native["tokens"]
                 and original["text"] == native["text"].strip(), "Fixed source text or tokens changed")
        item = dict(original)
        words = candidate.get("words") or []
        try:
            _require(mapped and "".join(word["word"] for word in words).strip() == original["text"],
                     "Incomplete word-to-segment mapping")
            start, end = _bounded(bound, candidate["start"], candidate["end"], duration)
            _require(start >= window[0] - 1e-9 and end <= window[1] + 1e-9,
                     "Adjusted interval leaves its encoder window")
            item.update(start=start, end=end)
        except (ValueError, TypeError, KeyError):
            fallback.add(index)
            words = []
        private, valid, previous_end = [], bool(words), item["start"] - 0.05
        for word in words:
            try:
                start, end = _bounded(bound, word["start"], word["end"], duration)
                _require(isinstance(word["word"], str) and bool(word["word"].strip()) and
                         start >= previous_end - 0.001 and start >= item["start"] - 0.05 and
                         end <= item["end"] + 0.05, "Invalid optional word evidence")
                private.append({"word": word["word"], "start": start, "end": end})
                previous_end = end
            except (ValueError, TypeError, KeyError):
                valid = False
                break
        item["_words"] = private if valid else []
        output.append(item)
    output, conflicts = resolve_interval_conflicts(output, baseline, duration)
    fallback.update(conflicts)
    timed = sum(bool(segment["_words"]) for segment in output)
    warnings = []
    if timed < len(output):
        warnings.append(f"Word timing was unavailable in {len(output) - timed} segment(s); "
                        "their complete text remains available for whole-segment speaker labeling.")
    if fallback:
        warnings.append(f"Original segment timing was retained in {len(fallback)} segment(s) "
                        "with incomplete or conflicting timing evidence; word-level speaker assignment "
                        "was unavailable there.")
    return TimingResult(output, warnings,
                        {"method": "fixed_text_postpass", "status": "complete" if not warnings else "partial",
                         "segment_count": len(output), "word_timed_segments": timed,
                         "original_timing_segments": len(fallback)})


def align_fixed_segments(engine, audio, language: str, baseline, raw_segments,
                         *, bound: Callable) -> TimingResult:
    """Use the existing engine/full waveform, once per original encoder window.

    Exceptions are optional-timing failures. The caller owns the already accepted
    baseline and must retain it, including on a late-window failure.
    """
    native_class, tokenizer_class, pad_or_trim, get_end = _runtime()
    import numpy as np
    extractor, native = engine.feature_extractor, engine.model
    hop, rate, max_frames = extractor.hop_length, extractor.sampling_rate, extractor.nb_max_frames
    _require(type(hop) is int and hop > 0 and rate == 16000 and
             type(max_frames) is int and max_frames >= 2 and engine.input_stride == 2 and
             extractor.time_per_frame == hop / rate and engine.frames_per_second == rate / hop and
             engine.tokens_per_second == rate / (hop * engine.input_stride),
             "Unsupported native window interface")
    _require(callable(extractor) and callable(engine.encode) and callable(native.align) and
             isinstance(language, str) and language not in {"", "auto"}, "Missing timing capability or language")
    _require(isinstance(audio, np.ndarray) and audio.ndim == 1 and audio.dtype == np.float32,
             "Timing requires the original complete decoded waveform")
    duration = len(audio) / rate
    _require(raw_segments is not None and len(raw_segments) == len(baseline) > 0,
             "Missing native source tokens or seek")
    _require(all(_valid_interval(segment, duration) for segment in baseline) and not _conflicts(baseline),
             "No physically ordered baseline for timing fallback")
    tokenizer = tokenizer_class(engine.hf_tokenizer, native.is_multilingual,
                                task="transcribe", language=language)
    _require(type(tokenizer.eot) is int and tokenizer.eot > 0 and
             all(type(token) is int for token in tokenizer.sot_sequence), "Invalid timing tokenizer")
    groups = []
    for index, (raw, public) in enumerate(zip(raw_segments, baseline)):
        tokens, seek = raw.get("tokens"), raw.get("seek")
        _require(isinstance(tokens, list) and bool(tokens) and
                 all(type(token) is int and token >= 0 for token in tokens) and
                 type(seek) is int and seek >= 0, "Invalid source token or seek")
        text_tokens = [token for token in tokens if token < tokenizer.eot]
        _require(bool(text_tokens) and tokenizer.decode(tokens) == raw["text"] and
                 raw["text"].strip() == public["text"], "Source token/text mismatch")
        if not groups or groups[-1]["seek"] != seek:
            _require(not groups or seek > groups[-1]["seek"], "Nonmonotonic original window map")
            groups.append({"seek": seek, "indices": [], "tokens": [], "spans": []})
        group = groups[-1]
        offset = len(group["tokens"])
        group["indices"].append(index)
        group["tokens"].extend(text_tokens)
        group["spans"].append((offset, len(group["tokens"])))
    # Full-array normalization must be identical to recognition, not recomputed
    # on individual cropped windows. The exhausted recognizer was released first.
    features = extractor(audio)
    _require(features.shape == (native.n_mels, len(audio) // hop + 1) and
             bool(np.isfinite(features).all()), "Incomplete or invalid full frontend")
    content_frames = features.shape[-1] - 1
    defaults = inspect.signature(native_class.transcribe).parameters
    prepend = defaults["prepend_punctuations"].default
    append = defaults["append_punctuations"].default
    _require(isinstance(prepend, str) and isinstance(append, str), "Unsupported timing punctuation policy")
    adjusted = deepcopy(raw_segments)
    mapping, windows, state = [False] * len(baseline), [None] * len(baseline), 0.0
    for window in groups:
        seek = window["seek"]
        num_frames = min(max_frames, content_frames - seek)
        _require(num_frames >= engine.input_stride, "Original window has no native alignment frames")
        fragment = features[:, seek:seek + num_frames]
        _require(fragment.shape == (native.n_mels, num_frames), "Truncated original encoder window")
        padded = pad_or_trim(fragment, length=max_frames)
        encoded = engine.encode(padded)
        adapter = _TimingAdapter(engine, native_class, encoded, tokenizer, window["tokens"], num_frames)
        group = [adjusted[index] for index in window["indices"]]
        native_class.add_word_timestamps(adapter, [group], tokenizer, encoded, num_frames,
                                        prepend, append, state)
        _require(adapter.model.calls == 1 and adapter.alignment is not None and
                 len(adapter.alignment) == 1, "Missing fixed-text native alignment")
        # Follow generate_segments' get_end state update on the adjusted copies;
        # do not use add_word_timestamps' different return or modify recognition seek.
        next_state = get_end(group)
        if next_state is not None:
            _require(_finite(next_state) and 0 <= next_state <= duration, "Invalid native timing state")
            state = float(next_state)
        words = [word for word in adapter.alignment[0] if word["word"]]
        _require([token for word in words for token in word["tokens"]] == window["tokens"],
                 "Timing postprocessor lost or reordered a source token")
        boundaries, offset = {0}, 0
        for word in words:
            offset += len(word["tokens"])
            boundaries.add(offset)
        for index, (start, end) in zip(window["indices"], window["spans"]):
            mapping[index] = start in boundaries and end in boundaries
            windows[index] = (seek * extractor.time_per_frame,
                              min(duration, (seek + num_frames) * extractor.time_per_frame))
        # Do not retain native tensors/path lists across windows or in the result.
        del adapter, encoded, padded, fragment, words
    del features
    return project_segments(baseline, raw_segments, adjusted, mapping, windows, duration, bound)
