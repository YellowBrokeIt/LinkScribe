"""Offline experiment: project a generated paragraph into ordered points.

This preserves paragraph content, not all information that an independently
generated original point list might contain. It never repairs a wrong paragraph.
"""
from __future__ import annotations

import copy
import re

ABBREVIATIONS = {"mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "st.",
                 "vs.", "etc.", "e.g.", "i.e.", "κ.", "κα.", "δρ.", "π.χ.", "δηλ."}
BOUNDARY = re.compile(r"[.!?][\"”’»'\)\]]*\s+")


def normalize(text):
    return " ".join(text.split())


def project(result, maximum_points=8, maximum_point_characters=900):
    text = result["summary"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Expected a nonempty generated paragraph.")
    boundaries = []
    for match in BOUNDARY.finditer(text):
        # A decimal's internal period has no following whitespace. Initials,
        # abbreviated titles and common abbreviations are conservatively kept
        # with the next sentence. Ambiguous title/name endings are merged too.
        prefix = text[:match.start() + 1]
        token = prefix.split()[-1]
        word = token.rstrip(".!?")
        if (token.casefold() in ABBREVIATIONS or
                re.fullmatch(r"(?:[^\W\d_]\.){2,}", token) or
                (word and word[0].isupper() and match.group()[0] == ".")):
            continue
        boundaries.append(match.end())
    starts = [0] + boundaries
    ends = boundaries + [len(text)]
    points = [text[start:end].strip() for start, end in zip(starts, ends) if text[start:end].strip()]
    if any(len(point) > maximum_point_characters for point in points):
        raise ValueError("A complete sentence span exceeds the point bound; no text was truncated.")
    while len(points) > maximum_points:
        choices = [(len(points[i]) + 1 + len(points[i + 1]), i) for i in range(len(points) - 1)
                   if len(points[i]) + 1 + len(points[i + 1]) <= maximum_point_characters]
        if not choices:
            raise ValueError("Complete ordered sentence spans cannot fit the point bounds.")
        _, i = min(choices)
        points[i:i + 2] = [points[i] + " " + points[i + 1]]
    if normalize(" ".join(points)) != normalize(text):
        raise ValueError("Projection did not preserve the complete generated paragraph.")
    projected = copy.deepcopy(result)
    projected["key_points"] = points
    return projected
