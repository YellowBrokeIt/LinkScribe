"""Independent small scanner for predeclared raw-JSON probe expectations.

This is NOT the pinned runtime, a schema converter or a GBNF validator. It
expresses the intended bounded language so future native tests can compare
actual acceptance with a frozen positive/negative matrix. It checks no meaning.
"""
from collections import Counter
import json


def no_duplicate_properties(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate property")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Nonstandard JSON constant: " + value)


def raw_bodies(content):
    """Return every JSON string's serialized body, including the fixed key."""
    bodies, i = [], 0
    while i < len(content):
        if content[i] != '"':
            i += 1
            continue
        start = i + 1
        _, end = json.decoder.scanstring(content, start, True)
        bodies.append(content[start:end - 1])
        i = end
    return bodies


def accepted(content, layout):
    try:
        content.encode("utf-8")
        value = json.loads(content, object_pairs_hook=no_duplicate_properties,
                           parse_constant=reject_constant)
        if (not isinstance(value, dict) or list(value) != ["translations"]
                or not isinstance(value["translations"], list)
                or len(value["translations"]) != len(layout)
                or any(not isinstance(s, str) for s in value["translations"])):
            return False
        bodies = raw_bodies(content)
        if len(bodies) != len(layout) + 1 or bodies[0] != "translations":
            return False
        for body, tags in zip(bodies[1:], layout):
            found, i = [], 0
            while i < len(body):
                char = body[i]
                if char == "\\":
                    if i + 1 >= len(body) or body[i + 1] not in '"\\/bfnrt':
                        return False
                    i += 2
                elif char == "<":
                    matching = [tag for tag in tags if body.startswith(tag, i)]
                    if len(matching) != 1:
                        return False
                    found.append(matching[0])
                    i += len(matching[0])
                elif char == '"' or ord(char) < 32:
                    return False
                else:
                    i += 1
            if Counter(found) != Counter(tags):
                return False
        return True
    except (ValueError, TypeError, UnicodeError):
        return False
