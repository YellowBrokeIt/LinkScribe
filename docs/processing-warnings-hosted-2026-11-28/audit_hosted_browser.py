"""Read retained hosted artifacts only; no server, browser, model, or network calls."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
COMMIT = "7a53991da60c9e052be9a72299218b291b364c8d"
TREE = "07ceac544ca6da271cede39d409a0281b9cad5fd"
RUN = 46107711847
JOB = 140864083983
ARTIFACT = 15248073165


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def audit():
    run = read("run-completed.json")
    assert run["id"] == RUN and run["head_sha"] == COMMIT
    assert run["status"] == "completed" and run["conclusion"] == "success"
    job, = [j for j in read("jobs-completed.json")["jobs"] if j["id"] == JOB]
    assert job["status"] == "completed" and job["conclusion"] == "success"
    artifact, = [a for a in read("artifact-metadata.json")["artifacts"] if a["id"] == ARTIFACT]
    assert artifact["workflow_run"]["id"] == RUN
    assert artifact["workflow_run"]["head_sha"] == COMMIT
    archive = (ROOT / "linkscribe-browser-7a53991.zip").read_bytes()
    assert len(archive) == artifact["size_in_bytes"]
    assert "sha256:" + sha(archive) == artifact["digest"]
    inventory = read("artifact-file-manifest.json")
    assert len(inventory["files"]) == inventory["file_count"] == 45
    with zipfile.ZipFile(ROOT / "linkscribe-browser-7a53991.zip") as z:
        assert z.testzip() is None
        assert {i.filename for i in z.infolist() if not i.is_dir()} == {f["path"] for f in inventory["files"]}
        for item in inventory["files"]:
            data = (ROOT / "artifact" / item["path"]).read_bytes()
            assert len(data) == item["bytes"] and sha(data) == item["sha256"]
            assert z.read(item["path"]) == data

    tree = read("source-tree.json")
    assert tree["sha"] == TREE and tree["truncated"] is False
    entries = {e["path"]: e for e in tree["tree"]}
    identities = read("published-source-identities.json")
    assert identities["commit"] == COMMIT and identities["tree"] == TREE
    report = read("artifact/browser-report.json")
    for item in identities["files"]:
        data = (ROOT / "published-source" / item["path"]).read_bytes()
        assert len(data) == item["bytes"] and sha(data) == item["sha256"]
        assert git_blob(data) == item["git_blob_sha1"] == entries[item["path"]]["sha"]
    sources = {f["path"]: f["sha256"] for f in identities["files"]}
    assert len(report["source_sha256"]) == 8
    assert all(sources[k] == v for k, v in report["source_sha256"].items())

    old_path = "docs/integration-2026-11-28/hosted-00567db/browser-report.json"
    old_bytes = (ROOT / "prior-00567db-browser-report.json").read_bytes()
    assert len(old_bytes) == entries[old_path]["size"] == 14529
    assert git_blob(old_bytes) == entries[old_path]["sha"] == "633a2c6996db7b61ff3b2d620269653ff265d113"
    previous = json.loads(old_bytes)
    old_names = [c["name"] for c in previous["checks"]]
    names = [c["name"] for c in report["checks"]]
    assert len(set(old_names)) == len(old_names) == 34
    assert len(set(names)) == len(names) == 35
    assert [n for n in names if n in old_names] == old_names
    assert set(names) - set(old_names) == {"batch_processing_warnings_persist"}
    assert all(c["status"] == "pass" for c in report["checks"])
    assert report["complete"] is True and report["result"] == "pass"
    assert report["counts"] == {"pass": 35} and report["scope"] == "all"
    assert report["asr_mode"] == "real" and report["asr_executed_successfully"] is True
    assert report["page_errors"] == []
    warning, = [c for c in report["checks"] if c["name"] == "batch_processing_warnings_persist"]
    details = warning["details"]
    expected = ["Translation: Set a valid LINKSCRIBE_TRANSLATION_MODEL.",
                "Summary: Set a valid LINKSCRIBE_OLLAMA_MODEL."]
    assert details["completed"] == 2 and details["failed"] == 0 and details["with_warnings"] == 2
    assert details["initial_server_pid"] > 0 and details["restarted_server_pid"] > 0
    assert details["initial_server_pid"] != details["restarted_server_pid"]
    assert details["before_warnings"] == details["after_warnings"] == [expected, expected]
    assert details["original_record_unchanged"] is True
    assert details["unavailable_enhancement_links_absent"] is True
    assert details["warning_free_record_clears_editor_notes"] is True
    assert details["mobile_layout"] == {"viewport": 320, "document": 320, "overflowing": []}

    # Recover the literal caption fixture from the immutable source without importing it.
    source = ast.parse((ROOT / "published-source/tests/smoke_browser.py").read_text(encoding="utf-8"))
    assignments = [n for n in ast.walk(source) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "captions_fixture" for t in n.targets)]
    assert len(assignments) == 1
    fixture = ast.literal_eval(assignments[0].value)
    backup_path = ROOT / "artifact/downloads/library-backup.zip"
    with zipfile.ZipFile(backup_path) as z:
        assert z.testzip() is None and set(z.namelist()) == {"manifest.json", "transcripts.json"}
        raw = z.read("transcripts.json")
        manifest = json.loads(z.read("manifest.json"))
        records = json.loads(raw)["records"]
    assert sha(raw) == manifest["sha256"] and len(records) == manifest["records"] == 6
    warned = []
    for video_id in ("QaWarning01", "QaWarning02"):
        record, = [r for r in records if r["source"] == "https://www.youtube.com/watch?v=" + video_id]
        assert record["segments"] == fixture
        assert record["plain_text"] == "\n".join(s["text"] for s in fixture)
        assert record["translations"] == {} and record["summary"] is None
        assert record["processing_metadata"]["warnings"] == expected
        warned.append({"id": record["id"], "source": record["source"],
                       "source_segments_match_published_fixture": True,
                       "plain_text_preserved": True, "warnings": expected,
                       "translations": record["translations"], "summary": record["summary"]})
    return {
        "schema_version": 1, "result": "pass", "read_only_artifact_audit": True,
        "commit": COMMIT, "tree": TREE, "run_id": RUN, "job_id": JOB, "artifact_id": ARTIFACT,
        "zip_sha256": sha(archive), "zip_bytes": len(archive), "rehash_extracted_files": 45,
        "published_sources_git_blob_verified": len(identities["files"]),
        "report_sources_match_immutable_commit": len(report["source_sha256"]),
        "browser_report_sha256": sha((ROOT / "artifact/browser-report.json").read_bytes()),
        "prior_report_sha256": sha(old_bytes), "prior_checks_retained_in_order": old_names,
        "only_new_check": "batch_processing_warnings_persist", "all_current_checks_pass": 35,
        "actual_asr_executed": True, "uncaught_page_errors": report["page_errors"],
        "console_messages": report["console_errors"], "warning_case": warning,
        "backup": {"sha256": sha(backup_path.read_bytes()), "record_count": len(records),
                   "payload_sha256": sha(raw), "warned_records": warned},
        "limits": ["Report assertions are retained execution evidence, not a browser rerun.",
                   "Backup inspection establishes exported persisted records; no SQLite file is present for a separate database audit.",
                   "The warning case uses owned captions and deliberately invalid enhancement settings, with no live provider or language inference.",
                   "This audit does not evaluate translation or ASR semantic accuracy, nor certify a later source revision."]
    }


if __name__ == "__main__":
    result = audit()
    output = ROOT / "retained-artifact-audit.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": result["result"], "report": str(output),
                      "sha256": sha(output.read_bytes()), "checks": 35, "files": 45}))
