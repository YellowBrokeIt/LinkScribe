"""Unicode search on persisted transcript titles and text, not model output."""
import sqlite3
import unicodedata

import pytest

import library


@pytest.fixture
def records(tmp_path, monkeypatch):
    path = tmp_path / "library.sqlite3"
    monkeypatch.setattr(library, "DB_FILE", path)
    # Legacy schema: exercise search without a data migration or rewriting text.
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE transcripts (
            id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
            language TEXT NOT NULL, method TEXT NOT NULL, segments TEXT NOT NULL,
            plain_text TEXT NOT NULL, translations TEXT NOT NULL DEFAULT '{}',
            summary TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
        for key, title, body, ts in (
            ("a", "ΣΥΝΈΝΤΕΥΞΗ", "Η Αθήνα και ο κόσμος", 1),
            ("b", "Greek notes", unicodedata.normalize("NFD", "Αθήνα"), 2),
            ("c", "English notes", r"Literal 50% under_score C:\\audio", 3),
            ("d", "Other", "Literal 500 underXscore", 4),
        ):
            conn.execute("INSERT INTO transcripts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (key, "upload", title, "el", "asr", "[]", body, "{}", None, ts, ts))
    return path


@pytest.mark.parametrize(("query", "expected"), [
    ("συνέντευξη", ["a"]),
    ("ΑΘΉΝΑ", ["b", "a"]),
    (unicodedata.normalize("NFD", "Αθήνα"), ["b", "a"]),
    ("ΚΌΣΜΟΣ", ["a"]),
    ("english", ["c"]),
    ("50%", ["c"]),
    ("under_score", ["c"]),
    (r"C:\\audio", ["c"]),
    ("' OR 1=1 --", []),
    ("", ["d", "c", "b", "a"]),
    ("missing", []),
])
def test_unicode_literal_search(records, query, expected):
    assert [row["id"] for row in library.list_items(query)] == expected


def test_search_keeps_original_text_and_limit(records):
    rows = library.list_items("ΑΘΉΝΑ", limit=1)
    assert [row["id"] for row in rows] == ["b"]
    assert rows[0]["preview"] == unicodedata.normalize("NFD", "Αθήνα")
    assert library.list_items("συνέντευξη")[0]["title"] == "ΣΥΝΈΝΤΕΥΞΗ"
    assert len(library.list_items("", limit=0)) == 1
