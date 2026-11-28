"""Model-free source-contract examples; never acoustic/model evidence.

The DTW recurrence follows pinned CTranslate2 src/dtw.cc for small synthetic
matrices. It demonstrates the terminal row and first-token boundary that an
alignment consumer must handle. No speech runtime or tokenizer is imported.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def synthetic_negative_dtw(values):
    """Small standard-library reproduction of the pinned finite-matrix path."""
    n, m = len(values), len(values[0])
    if not n or not m or any(len(row) != m for row in values):
        raise ValueError("Invalid synthetic matrix")
    if any(not math.isfinite(value) for row in values for value in row):
        raise ValueError("Synthetic examples require finite values")
    cost = [[math.inf] * (m + 1) for _ in range(n + 1)]
    trace = [[-1] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for j in range(1, m + 1):
        for i in range(1, n + 1):
            c0, c1, c2 = cost[i - 1][j - 1], cost[i - 1][j], cost[i][j - 1]
            if c0 < c1 and c0 < c2:
                c, t = c0, 0
            elif c1 < c0 and c1 < c2:
                c, t = c1, 1
            else:
                c, t = c2, 2
            cost[i][j] = -values[i - 1][j - 1] + c
            trace[i][j] = t
    for k in range(m + 1):
        trace[0][k] = 2
    for k in range(n + 1):
        trace[k][0] = 1
    i, j, path = n, m, []
    while i > 0 or j > 0:
        path.append([i - 1, j - 1])
        step = trace[i][j]
        if step == 0:
            i, j = i - 1, j - 1
        elif step == 1:
            i -= 1
        elif step == 2:
            j -= 1
        else:
            raise ValueError("Invalid source recurrence")
    return list(reversed(path))


def validate_native_path(path, text_token_probs, text_count, num_frames):
    """Validate native DTW structure, allowing terminal index N and zero spans.

    The terminal row is a boundary, not an extra recognized text token. A valid
    native path can still yield unusable word timing; this is not an acoustic
    acceptance rule and does not manufacture positive durations.
    """
    if type(text_count) is not int or text_count <= 0:
        raise ValueError("Nonempty text token count required")
    if type(num_frames) is not int or num_frames < 2:
        raise ValueError("No native alignment frames")
    frame_count = num_frames // 2
    if len(text_token_probs) != text_count:
        raise ValueError("Text probability count must exclude terminal boundary")
    if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
           for x in text_token_probs):
        raise ValueError("Invalid token probability")
    if not isinstance(path, list) or not path:
        raise ValueError("Missing native path")
    for pair in path:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("Invalid alignment pair")
        text_index, frame_index = pair
        if (type(text_index) is not int or type(frame_index) is not int
                or not 0 <= text_index <= text_count
                or not 0 <= frame_index < frame_count):
            raise ValueError("Native index outside text/terminal or frame range")
    if tuple(path[0]) != (0, 0) or tuple(path[-1]) != (text_count, frame_count - 1):
        raise ValueError("Incomplete native start or terminal boundary")
    for left, right in zip(path, path[1:]):
        delta = (right[0] - left[0], right[1] - left[1])
        if delta not in ((1, 0), (0, 1), (1, 1)):
            raise ValueError("Invalid native monotonic step")
    indices = {pair[0] for pair in path}
    if indices != set(range(text_count + 1)):
        raise ValueError("Missing text or terminal boundary")
    first_frame = [next(frame for index, frame in path if index == token)
                   for token in range(text_count + 1)]
    return {"boundary_frames": first_frame, "first_boundary_seconds": first_frame[0] / 50,
            "terminal_is_boundary_only": True,
            "zero_duration_token_spans": sum(a == b for a, b in zip(first_frame, first_frame[1:]))}


def main():
    inventory = json.loads((ROOT / "native-contract/inventory.json").read_text(encoding="utf-8"))
    for entry in inventory:
        data = (ROOT / "native-contract" / entry["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == entry["git_blob_sha1"]
    matrices = [
        [[0, 0, 0, 20, 20, 0], [0, 0, 0, 0, 20, 0], [0, 0, 0, 0, 0, 20]],
        [[0, 0, 0, 0, 0, 0, 20, 0], [0, 0, 0, 0, 0, 0, 0, 20]],
        [[0, 10, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 10, 0, 0, 0, 0, 0],
         [0, 0, 0, 0, 0, 10, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 10, 0]],
    ]
    examples = []
    for values in matrices:
        path = synthetic_negative_dtw(values)
        result = validate_native_path(path, [0.5] * (len(values) - 1), len(values) - 1, len(values[0]) * 2)
        assert result["first_boundary_seconds"] == 0
        examples.append({"synthetic_attention_values": values, "synthetic_path": path, "consumer_result": result})
    vertical = [[0, 0], [1, 0], [2, 1], [2, 2]]
    zero = validate_native_path(vertical, [0.5, 0.5], 2, 6)
    assert zero["zero_duration_token_spans"] == 1
    good = [[0, 0], [0, 1], [1, 2], [2, 3]]
    rejected = []
    for name, path, probs, count, frames in [
        ("missing_terminal", good[:-1], [0.5, 0.5], 2, 8),
        ("terminal_probability_invented", good, [0.5] * 3, 2, 8),
        ("negative_frame", [[0, -1], *good[1:]], [0.5, 0.5], 2, 8),
        ("missing_text_index", [[0, 0], [2, 3]], [0.5, 0.5], 2, 8),
        ("crossing_path", [[0, 0], [1, 2], [1, 1], [2, 3]], [0.5, 0.5], 2, 8),
        ("nan_probability", good, [math.nan, 0.5], 2, 8),
        ("no_encoder_stride_frame", good, [0.5, 0.5], 2, 1),
    ]:
        try:
            validate_native_path(path, probs, count, frames)
        except ValueError as exc:
            rejected.append({"name": name, "rejected": True, "reason": str(exc)})
        else:
            raise AssertionError(name)
    result = {
        "schema_version": 1, "scope": "Synthetic source-contract control, not model/alignment/accuracy evidence.",
        "model_initialized": False, "model_inference": False,
        "upstream_commit": "88e735ac42a2a97c7c10daec4e7ce9db49edf562",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "native_source_inventory_sha256": hashlib.sha256((ROOT / "native-contract/inventory.json").read_bytes()).hexdigest(),
        "synthetic_examples": examples, "valid_zero_span_example": {"path": vertical, "result": zero},
        "malformed_results": rejected,
        "source_deduction": "Finite native DTW starts at token0/frame0, and native word grouping starts at token boundary0. A raw-only first-word start therefore equals its audio-window start. Terminal indexN is required as an endpoint, but there are onlyN text probabilities.",
        "official_baseline_implication": [
            {"segment_id": 77, "seek_frames": 48500, "first_text_span_start": 0, "raw_only_start_seconds": 485.0,
             "unchanged_window": [501, 513], "full_containment_start_impossible": True},
            {"segment_id": 78, "seek_frames": 50880, "first_text_span_start": 0, "raw_only_start_seconds": 508.8,
             "unchanged_window": [510, 529], "full_containment_start_impossible": True},
        ],
    }
    target = ROOT / "native-contract-check.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                      "positive_examples": len(examples) + 1, "malformed_rejections": len(rejected),
                      "model_inference": False}))


if __name__ == "__main__":
    main()
