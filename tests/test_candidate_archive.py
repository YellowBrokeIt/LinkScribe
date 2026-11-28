"""Candidate provenance and extraction failures must precede installation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile


spec = importlib.util.spec_from_file_location(
    "candidate_install", Path(__file__).with_name("smoke_candidate_install.py"))
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
COMMIT = "a" * 40
REPOSITORY = "owner/LinkScribe"


def make_artifact(tmp_path, extra=(), comment=COMMIT, manifest_changes=None, omit=()):
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    archive = artifact / candidate.ARCHIVE_NAME
    with warnings.catch_warnings(), zipfile.ZipFile(archive, "w") as bundle:
        warnings.filterwarnings("ignore", message="Duplicate name:", category=UserWarning)
        bundle.comment = comment.encode("ascii")
        for name in ("start_linux.sh", "requirements.txt", "app.py", "asr_timing.py", "static/index.html"):
            if name not in omit:
                bundle.writestr(f"LinkScribe/{name}", "fixture, never executed\n")
        for name, content in extra:
            bundle.writestr(name, content)
    manifest = {"repository": REPOSITORY, "commit": COMMIT,
                "artifact": candidate.ARCHIVE_NAME,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    manifest.update(manifest_changes or {})
    (artifact / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    destination = tmp_path / "extracted"
    destination.mkdir()
    return artifact, destination


class CandidateArchiveTests(unittest.TestCase):
    def test_verified_archive_extracts_required_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact, destination = make_artifact(Path(temporary))
            source = candidate.extract_candidate(artifact, destination, COMMIT, REPOSITORY)
            self.assertEqual(source["commit"], COMMIT)
            self.assertEqual(source["members"], 5)
            self.assertTrue((destination / "LinkScribe/static/index.html").is_file())
            self.assertTrue((destination / "LinkScribe/asr_timing.py").is_file())
            self.assertFalse((destination / "LinkScribe/.venv").exists())

    def test_missing_timing_module_extracts_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact, destination = make_artifact(Path(temporary), omit={"asr_timing.py"})
            with self.assertRaisesRegex(ValueError, "missing required application files"):
                candidate.extract_candidate(artifact, destination, COMMIT, REPOSITORY)
            self.assertEqual(list(destination.iterdir()), [])

    def test_5001_members_extract_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            extra = [(f"LinkScribe/evidence/{index}.txt", "small fixture\n")
                     for index in range(4996)]
            artifact, destination = make_artifact(Path(temporary), extra=extra)
            with zipfile.ZipFile(artifact / candidate.ARCHIVE_NAME) as bundle:
                self.assertEqual(len(bundle.infolist()), 5001)
            with self.assertRaisesRegex(ValueError, "invalid member count"):
                candidate.extract_candidate(artifact, destination, COMMIT, REPOSITORY)
            self.assertEqual(list(destination.iterdir()), [])

    def test_manifest_mismatch_extracts_nothing(self):
        for changes in ({"commit": "b" * 40}, {"repository": "other/LinkScribe"},
                        {"artifact": "../wrong.zip"}, {"sha256": "0" * 64}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as temporary:
                artifact, destination = make_artifact(Path(temporary), manifest_changes=changes)
                with self.assertRaisesRegex(ValueError, "does not match"):
                    candidate.extract_candidate(artifact, destination, COMMIT, REPOSITORY)
                self.assertEqual(list(destination.iterdir()), [])

    def test_wrong_git_archive_commit_extracts_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact, destination = make_artifact(Path(temporary), comment="b" * 40)
            with self.assertRaisesRegex(ValueError, "commit comment"):
                candidate.extract_candidate(artifact, destination, COMMIT, REPOSITORY)
            self.assertEqual(list(destination.iterdir()), [])

    def test_unsafe_or_duplicate_member_extracts_nothing(self):
        for path in ("LinkScribe/../../outside", "/outside", "LinkScribe\\..\\outside", "LinkScribe/app.py"):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                artifact, destination = make_artifact(root, extra=[(path, "must not be written")])
                with self.assertRaisesRegex(ValueError, "Unsafe or unsupported"):
                    candidate.extract_candidate(artifact, destination, COMMIT, REPOSITORY)
                self.assertEqual(list(destination.iterdir()), [])
                self.assertFalse((root / "outside").exists())

    def test_symlink_extracts_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            link = zipfile.ZipInfo("LinkScribe/escape")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            artifact, destination = make_artifact(Path(temporary), extra=[(link, "../../outside")])
            with self.assertRaisesRegex(ValueError, "Unsafe or unsupported"):
                candidate.extract_candidate(artifact, destination, COMMIT, REPOSITORY)
            self.assertEqual(list(destination.iterdir()), [])

    def test_nested_file_directory_conflict_extracts_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact, destination = make_artifact(
                Path(temporary), extra=[("LinkScribe/parent", "a file"),
                                       ("LinkScribe/parent/child/grandchild", "must not be written")])
            with self.assertRaisesRegex(ValueError, "conflicting file paths"):
                candidate.extract_candidate(artifact, destination, COMMIT, REPOSITORY)
            self.assertEqual(list(destination.iterdir()), [])
