"""Deterministic, source-bound transcript excerpts with no generated claims.

The selector ranks source passages using repeated content words, English/Greek
decision and qualification cues, and chronological diversity. It preserves
whole source segments and groups nearby continuations/corrections. These are
navigation aids, not a complete summary or a guarantee of semantic coverage.
No model, network request, synthetic heading, or inferred timestamp is used.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import re
import unicodedata
from typing import Any


MAX_SOURCE_SEGMENTS = 100_000
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_EXCERPTS = 6
MAX_EXCERPT_BYTES = 24 * 1024
MAX_SELECTED_SEGMENTS = 2048
SHORT_SOURCE_BYTES = 1800
MAX_FEATURE_TERMS = 192
MAX_VOCABULARY = 20_000

NOTICE = ("Selected transcript excerpts, not a complete summary. They may omit important "
          "information or distant context. Check the full transcript; recognition errors are retained.")
SHORT_NOTICE = "The short transcript is retained in full instead of ranking isolated sentences."
EMPTY_NOTICE = "No spoken-word transcript text is available to select."
LIMIT_NOTICE = ("Some source passages are too large to include whole within the excerpt limits; "
                "they remain available in the full transcript.")
WHOLE_NOTICE = "A long source passage is retained whole to avoid cutting its context."
WARNINGS = {NOTICE, SHORT_NOTICE, EMPTY_NOTICE, LIMIT_NOTICE, WHOLE_NOTICE}

_WORDS = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?|\d+(?:[.,]\d+)*", re.UNICODE)
_END = re.compile(r"[.!?;··][\"'”’»\)\]]*\s*\Z")
_MARKER = re.compile(r"\s*[\[\(](?:music|silence|applause|laughter|noise|inaudible|"
                     r"μουσικη|σιωπη|χειροκροτημα|γελια|θορυβος|ακαταληπτο)[\]\)]\s*\Z")


def _normalize(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(char)).replace("’", "'")


_STOP = set(("a an the and or of to in on at for from with as by is are was were be been being "
             "i me my we our you your he she it its they them their this that these those "
             "there here have has had do does did very really just about into over also "
             "ο η το οι τα τον την τους τις του τη των ενας μια ενα σε με για απο και η "
             "ειναι ηταν ειμαι ειμαστε ειναι αυτο αυτη αυτος αυτα αυτες αυτοι εγω εμεις "
             "εσυ εσεις μου σου μας σας του της τους εχει εχουν ειχε ειχαν ως στον στην "
             "στο στους στις στα εδω εκει πολυ πιο επισης καποιο καποια καποιος που").split())
_NEGATION = set("not no never cannot can't don't mustn't neither without δεν μην μη οχι ποτε χωρις".split())
_CONDITION = set(("if unless only until except provided conditional contingent subject "
                  "αν εαν μονο εφοσον εκτος μεχρι προϋποθεση").split())
_ACTION = set(("decided agreed approve approved approval deliver deadline must required permission "
               "consent due schedule assigned planned plan refund reimburse budget cost amount "
               "decision cancel cancelled canceled revoke revoked withdrawn withdraw "
               "πρεπει αδεια συγκαταθεση προθεσμια κοστος ποσο προϋπολογισμος").split())
_CORRECTION = set(("correction corrected revise revised instead actually cancel cancelled canceled "
                   "revoke revoked withdrawn withdraw διορθωση διορθωθηκε αντιθετα τελικα "
                   "ακυρο ακυρωνεται ανακαλειται").split())
_DEPENDENT_STARTS = set(("and but however otherwise therefore instead actually yes no this that "
                         "these those it they unless except only if until provided correction "
                         "corrected revised και αλλα ομως αντιθετα επομενως αρα τελικα "
                         "ναι οχι αυτο αυτη αυτος αυτοι αυτες αυτα εκτος μονο αν εαν "
                         "εφοσον μεχρι διορθωση").split())
_FILLER = set("welcome hello goodbye subscribe subscription thanks thank καλησπερα καλημερα ευχαριστω εγγραφη".split())
# Accents are folded only for ranking; original text is never normalized.
_STOP = {_normalize(word) for word in _STOP}
_NEGATION = {_normalize(word) for word in _NEGATION}
_CONDITION = {_normalize(word) for word in _CONDITION}
_ACTION = {_normalize(word) for word in _ACTION}
_CORRECTION = {_normalize(word) for word in _CORRECTION}
_DEPENDENT_STARTS = {_normalize(word) for word in _DEPENDENT_STARTS}
_FILLER = {_normalize(word) for word in _FILLER}


class SourceHighlightsError(ValueError):
    """A source or saved excerpt does not meet the bounded source-binding contract."""


def _finite_time(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and 0 <= value <= 7 * 24 * 3600
    except OverflowError:
        return False


def _source_details(segments: Any) -> tuple[str, list[int], list[bool]]:
    if not isinstance(segments, list) or len(segments) > MAX_SOURCE_SEGMENTS:
        raise SourceHighlightsError("Highlights require a bounded list of transcript segments.")
    digest = hashlib.sha256(b"linkscribe-source-highlights-v1\n")
    sizes = [0]
    meaningful = []
    previous = -1.0
    for segment in segments:
        if not isinstance(segment, dict):
            raise SourceHighlightsError("Every source segment must be an object.")
        start, end, text = segment.get("start"), segment.get("end"), segment.get("text")
        if (not _finite_time(start) or not _finite_time(end) or start < previous
                or end < start or not isinstance(text, str)):
            raise SourceHighlightsError("Highlights require ordered finite source timestamps and text.")
        speaker = segment.get("speaker")
        if "speaker" in segment and (not isinstance(speaker, str) or len(speaker) > 120):
            raise SourceHighlightsError("A source speaker label must be bounded text.")
        if len(text) > MAX_SOURCE_BYTES:
            raise SourceHighlightsError("Transcript text exceeds the 8 MiB highlights limit.")
        try:
            encoded = text.encode("utf-8")
            if sizes[-1] + len(encoded) > MAX_SOURCE_BYTES:
                raise SourceHighlightsError("Transcript text exceeds the 8 MiB highlights limit.")
            canonical = json.dumps({"start": float(start) or 0.0, "end": float(end) or 0.0,
                                    "text": text, "speaker": speaker}, ensure_ascii=False,
                                   separators=(",", ":"), allow_nan=False).encode("utf-8")
        except UnicodeError as error:
            raise SourceHighlightsError("Highlights require valid Unicode source text.") from error
        sizes.append(sizes[-1] + len(encoded))
        if sizes[-1] > MAX_SOURCE_BYTES:
            raise SourceHighlightsError("Transcript text exceeds the 8 MiB highlights limit.")
        digest.update(canonical)
        digest.update(b"\n")
        meaningful.append(any(char.isalnum() for char in text)
                          and not bool(_MARKER.fullmatch(_normalize(text))))
        previous = start
    return digest.hexdigest(), sizes, meaningful


def _bytes(sizes: list[int], first: int, last: int) -> int:
    return sizes[last + 1] - sizes[first] + last - first  # Exact newline joins.


def _excerpt(segments: list[dict[str, Any]], first: int, last: int) -> dict[str, Any]:
    return {"segment_indices": list(range(first, last + 1)),
            "start": segments[first]["start"],
            "end": max(segment["end"] for segment in segments[first:last + 1]),
            "text": "\n".join(segment["text"] for segment in segments[first:last + 1])}


def _words(text: str):
    return (match.group() for match in _WORDS.finditer(_normalize(text)))


def _depends_on_previous(segments, first: int, last: int) -> bool:
    beginning = []
    for index in range(first, last + 1):
        for word in _words(segments[index]["text"]):
            beginning.append(word)
            if len(beginning) == 8:
                break
        if len(beginning) == 8:
            break
    return bool(beginning and (beginning[0] in _DEPENDENT_STARTS
                               or any(word in _CORRECTION for word in beginning[:3])))


def _passages(segments: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Whole sentence/turn blocks; dependent openings stay with their antecedent.

    This is a conservative local heuristic, not discourse understanding. A
    remote later correction may still need the full transcript for context.
    """
    raw = []
    first = 0
    for index, segment in enumerate(segments):
        following = segments[index + 1] if index + 1 < len(segments) else None
        boundary = bool(_END.search(segment["text"]))
        if following is not None:
            different_speakers = (segment.get("speaker") and following.get("speaker")
                                  and segment["speaker"] != following["speaker"])
            boundary |= bool(different_speakers or following["start"] - segment["end"] > 2.0)
        if boundary or following is None:
            raw.append((first, index))
            first = index + 1
    grouped = []
    for first, last in raw:
        if grouped and (_depends_on_previous(segments, first, last)
                        or segments[grouped[-1][1]]["text"].rstrip().endswith((":", "—", "-"))):
            grouped[-1] = (grouped[-1][0], last)
        else:
            grouped.append((first, last))
    return grouped


def _features(segments, first: int, last: int) -> tuple[set[str], float]:
    terms: set[str] = set()
    cues: set[str] = set()
    filler: set[str] = set()
    numeric = False
    for index in range(first, last + 1):
        for word in _words(segments[index]["text"]):
            if word in _CORRECTION or word.startswith(("διορθ", "ανακαλ", "ακυρων")):
                cues.add("correction")
            if word in _NEGATION:
                cues.add("negation")
            if word in _CONDITION:
                cues.add("condition")
            if word in _ACTION or word.startswith(("αποφασ", "συμφων", "εγκρι", "παραδο", "απαγορευ")):
                cues.add("action")
            if word in _FILLER:
                filler.add(word)
            numeric |= word[0].isdigit()
            if word not in _STOP and 1 < len(word) <= 64 and len(terms) < MAX_FEATURE_TERMS:
                terms.add(word)
    priority = sum({"correction": 4.0, "negation": 2.0, "condition": 2.5,
                    "action": 2.0}[cue] for cue in cues)
    return terms, priority + (0.4 if numeric else 0.0) - min(len(filler), 2) * 0.6


def _merged(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for first, last in sorted(ranges):
        if result and first <= result[-1][1] + 1:
            result[-1] = (result[-1][0], max(result[-1][1], last))
        else:
            result.append((first, last))
    return result


def select_highlights(segments: list[dict[str, Any]],
                      source_language: str | None = None) -> dict[str, Any]:
    """Return at most six chronological passages, copied exactly from the source.

    English and Greek cue words are both recognized, including mixed-language
    speech. source_language is accepted for consistency with other enhancement
    APIs; it never causes translation or text normalization in the result.
    """
    fingerprint, sizes, meaningful = _source_details(segments)
    result = {"kind": "source_highlights", "version": 1,
              "method": "deterministic_source_selection", "source_sha256": fingerprint,
              "source_segment_count": len(segments), "selected_segment_count": 0,
              "excerpts": [], "warnings": [NOTICE]}
    if not any(meaningful):
        result["warnings"].append(EMPTY_NOTICE)
        return result
    if sizes[-1] + max(0, len(segments) - 1) <= SHORT_SOURCE_BYTES and len(segments) <= MAX_SELECTED_SEGMENTS:
        result["excerpts"] = [_excerpt(segments, 0, len(segments) - 1)]
        result["selected_segment_count"] = len(segments)
        result["warnings"].append(SHORT_NOTICE)
        return result

    passages = _passages(segments)
    feature_rows = [_features(segments, first, last) for first, last in passages]
    frequency: Counter[str] = Counter()
    for terms, _priority in feature_rows:
        for term in sorted(terms):
            if term in frequency or len(frequency) < MAX_VOCABULARY:
                frequency[term] += 1
    candidates = []
    omitted_oversized = False
    for index, ((first, last), (terms, priority)) in enumerate(zip(passages, feature_rows)):
        if not any(meaningful[first:last + 1]):
            continue
        # Include adjacent complete passages where they fit. Dependencies were
        # already grouped above, so reducing optional context never cuts a group.
        left = passages[max(0, index - 1)][0]
        right = passages[min(len(passages) - 1, index + 1)][1]
        if _bytes(sizes, left, right) > MAX_EXCERPT_BYTES or right - left + 1 > MAX_SELECTED_SEGMENTS:
            left, right = first, last
        if _bytes(sizes, left, right) > MAX_EXCERPT_BYTES or right - left + 1 > MAX_SELECTED_SEGMENTS:
            omitted_oversized = True
            continue
        # Normalize frequency so a long repeated agenda cannot overwhelm a
        # single decision, correction or qualification through repetition alone.
        topicality = (2.5 * sum(math.log1p(frequency.get(term, 0)) for term in sorted(terms))
                      / (max(1, len(terms)) * math.log1p(max(1, len(passages)))))
        score = topicality + priority + 0.2 * index / max(1, len(passages) - 1)
        candidates.append((left, right, score, terms, min(2, index * 3 // len(passages))))
    budget = min(MAX_EXCERPT_BYTES, max(3000, math.ceil(sizes[-1] * 0.4)))
    if candidates and not any(_bytes(sizes, left, right) <= budget for left, right, *_ in candidates):
        budget = min(_bytes(sizes, left, right) for left, right, *_ in candidates)
        result["warnings"].append(WHOLE_NOTICE)
    selected: list[tuple[int, int]] = []
    selected_terms: set[str] = set()
    selected_buckets: set[int] = set()
    for _ in range(min(12, len(candidates))):
        best = None
        for order, (first, last, score, terms, bucket) in enumerate(candidates):
            merged = _merged(selected + [(first, last)])
            if merged == selected or len(merged) > MAX_EXCERPTS:
                continue
            if (sum(_bytes(sizes, left, right) for left, right in merged) > budget
                    or sum(right - left + 1 for left, right in merged) > MAX_SELECTED_SEGMENTS):
                continue
            novelty = len(terms - selected_terms) / max(1, len(terms))
            merit = score * (0.25 + 0.75 * novelty) * (1.35 if bucket not in selected_buckets else 1.0)
            choice = (merit, -order)
            if best is None or choice > best[0]:
                best = (choice, merged, terms, bucket)
        if best is None:
            break
        _choice, selected, terms, bucket = best
        selected_terms.update(terms)
        selected_buckets.add(bucket)
    result["excerpts"] = [_excerpt(segments, first, last) for first, last in selected]
    result["selected_segment_count"] = sum(last - first + 1 for first, last in selected)
    if omitted_oversized or not selected:
        result["warnings"].append(LIMIT_NOTICE)
    return result


def validate_highlights(value: Any, segments: list[dict[str, Any]]) -> None:
    """Reject stale, invented, reordered or oversized excerpts before persistence."""
    fingerprint, _sizes, meaningful = _source_details(segments)
    keys = {"kind", "version", "method", "source_sha256", "source_segment_count",
            "selected_segment_count", "excerpts", "warnings"}
    if not isinstance(value, dict) or set(value) != keys:
        raise SourceHighlightsError("Saved highlights have an invalid format.")
    if (value["kind"] != "source_highlights" or type(value["version"]) is not int or value["version"] != 1
            or value["method"] != "deterministic_source_selection"
            or value["source_sha256"] != fingerprint
            or type(value["source_segment_count"]) is not int
            or value["source_segment_count"] != len(segments)):
        raise SourceHighlightsError("Saved highlights do not match this transcript source.")
    excerpts, warnings = value["excerpts"], value["warnings"]
    if (not isinstance(excerpts, list) or len(excerpts) > MAX_EXCERPTS
            or not isinstance(warnings, list) or not 1 <= len(warnings) <= len(WARNINGS)
            or any(not isinstance(warning, str) or warning not in WARNINGS for warning in warnings)
            or NOTICE not in warnings or len(set(warnings)) != len(warnings)):
        raise SourceHighlightsError("Saved highlights contain invalid excerpts or notices.")
    previous = -1
    count = 0
    byte_count = 0
    for excerpt in excerpts:
        if not isinstance(excerpt, dict) or set(excerpt) != {"segment_indices", "start", "end", "text"}:
            raise SourceHighlightsError("Saved highlights contain an invalid excerpt.")
        indices = excerpt["segment_indices"]
        if (not isinstance(indices, list) or not indices or len(indices) > MAX_SELECTED_SEGMENTS
                or any(type(index) is not int for index in indices)
                or indices[0] <= previous or indices[0] < 0 or indices[-1] >= len(segments)
                or indices != list(range(indices[0], indices[-1] + 1))):
            raise SourceHighlightsError("Saved highlights must reference ordered, contiguous source segments.")
        expected = _excerpt(segments, indices[0], indices[-1])
        if (not _finite_time(excerpt["start"]) or not _finite_time(excerpt["end"])
                or excerpt != expected or not any(meaningful[indices[0]:indices[-1] + 1])):
            raise SourceHighlightsError("Saved highlight text or timestamps differ from the source.")
        previous = indices[-1]
        count += len(indices)
        byte_count += len(excerpt["text"].encode("utf-8"))
    if (count > MAX_SELECTED_SEGMENTS or byte_count > MAX_EXCERPT_BYTES
            or type(value["selected_segment_count"]) is not int or value["selected_segment_count"] != count):
        raise SourceHighlightsError("Saved highlights exceed their bounded source selection.")
