"""Optional real-browser acceptance checks with an isolated local app.

Install Playwright separately from the application requirements, then run:
  python -m playwright install chromium
  PYTHONPATH=. python tests/smoke_browser.py --output /tmp/linkscribe-browser-qa

The default upload uses owned FFmpeg/flite speech and actual Whisper tiny. Public
provider acquisition is replaced with explicitly recorded owned caption fixtures
for link/batch UI mechanics. --asr stub is an explicit, weaker alternative; it
never claims real recognition. The actual HTTP routes, origin guard, queue,
SQLite, exports, backup validation and browser JavaScript remain in use.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import wave
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ID = "f" * 32
SPEECH = ("Hello. This is a speech recognition test. We are speaking clear words "
          "for a local transcript. Please keep the recording private.")
BASE_URL = "http://127.0.0.1:8765"


def serve(data_root: Path, asr: str) -> None:
    """Private subprocess entry point; no application source is modified."""
    sys.path.insert(0, str(ROOT))
    import app
    import library
    import uvicorn

    app.DATA_DIR = data_root / "jobs"
    app.DATA_DIR.mkdir(parents=True, exist_ok=True)
    library.DB_FILE = data_root / "library.sqlite3"
    # Exercise actual optional-enhancement failure handling without calling a
    # second process's local models or pretending these checks evaluate language.
    os.environ["LINKSCRIBE_OLLAMA_MODEL"] = " "
    os.environ["LINKSCRIBE_TRANSLATION_MODEL"] = " "
    os.environ["LINKSCRIBE_DEVICE"] = "cpu"

    captions_fixture = [
        {"start": 0.0, "end": 2.0, "text": "Hello. This is an owned browser workflow test."},
        {"start": 2.0, "end": 4.0, "text": "We are checking saved words and subtitle downloads."},
    ]

    def captions(video_id, language):
        time.sleep(1.8)  # Allow the actual polling UI to observe working state.
        if video_id == "QaFailure01":
            raise app.ReadableError("Controlled unavailable-caption fixture.")
        return [dict(item) for item in captions_fixture], "en"

    app._captions = captions
    if asr == "stub":
        def recognize(path, language, model):
            time.sleep(1.8)
            return [{"start": 0.0, "end": 8.0, "text": SPEECH}], "en"
        app._recognize = recognize

    segments = [{"start": float(i * 2), "end": float(i * 2 + 1.5),
                 "text": f"Owned QA fixture segment {i + 1}. Zebra docket stays searchable.",
                 "speaker": "Speaker 1" if i % 2 == 0 else "Speaker 2"}
                for i in range(35)]
    segments[2]["text"] = 'Literal markup <script>window.uiFixtureExecuted = true</script> stays text.'
    translations = {"el": [{**item, "text": f"Δοκιμαστικό τμήμα {i + 1}."}
                           for i, item in enumerate(segments)]}
    summary = {"summary": "Owned QA fixture summary; not model output.",
               "key_points": ["Tests editor pagination and exports."],
               "chapters": [{"start": 0, "title": "Owned QA fixture"}]}
    library.save(FIXTURE_ID, "owned-ui-fixture", "Owned editor fixture: 35 segments", "en",
                 "owned_ui_fixture", segments, translations, summary)
    uvicorn.run(app.app, host="127.0.0.1", port=8765, log_level="warning")


def make_audio(path: Path) -> dict:
    subprocess.run([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"flite=text='{SPEECH}':voice=slt",
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(path),
    ], check=True, timeout=30)
    with wave.open(str(path), "rb") as handle:
        duration = handle.getnframes() / handle.getframerate()
    return {"source": "owned_text_synthesized_with_ffmpeg_flite", "text": SPEECH,
            "seconds": round(duration, 3), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run(args) -> int:
    from playwright.sync_api import sync_playwright, expect

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "screenshots").mkdir(exist_ok=True)
    (output / "downloads").mkdir(exist_ok=True)
    report = {
        "schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
        "complete": False, "result": "running", "asr_mode": args.asr,
        "asr_executed_successfully": False,
        "provider_acquisition": "controlled_owned_caption_fixtures",
        "language_enhancement_failure": "deliberately_invalid_child_process_settings",
        "production_origin_guard": "unchanged_fixed_local_port_8765",
        "semantic_translation_quality": "not_evaluated",
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in ["app.py", "static/index.html", "library.py", "library_backup.py",
                                       "batch_store.py", "source_highlights.py", "sources.py", "tests/smoke_browser.py"]},
        "checks": [], "console_errors": [], "page_errors": [], "screenshots": [],
    }

    def checkpoint():
        target = output / "browser-report.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)

    checkpoint()
    server = None
    browser = None
    page = None
    scratch = tempfile.TemporaryDirectory(prefix="linkscr-browser-qa-")
    data_root = Path(scratch.name)
    audio_path = output / "owned-speech.wav"
    log = (output / "server.log").open("w", encoding="utf-8")
    try:
        # Never displace another local application or weaken the fixed-port guard.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 8765))
        report["speech_fixture"] = make_audio(audio_path)
        (output / "invalid.txt").write_text("Owned invalid media fixture.\n")
        (output / "empty.wav").write_bytes(b"")
        (output / "corrupt.wav").write_bytes(b"This is not a WAV file.")
        (output / "invalid-backup.zip").write_bytes(b"This is not a ZIP file.")
        command = [args.server_python or sys.executable, str(Path(__file__).resolve()),
                   "--serve", str(data_root), "--asr", args.asr]
        server = subprocess.Popen(command, cwd=data_root, stdout=log, stderr=subprocess.STDOUT,
                                  env={**os.environ, "PYTHONPATH": str(ROOT)})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("Isolated app exited during startup; see server.log.")
            try:
                with opener.open(BASE_URL + "/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise TimeoutError("Isolated app did not become ready within 30 seconds.")

        with sync_playwright() as playwright:
            launch = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            if args.browser_executable:
                launch["executable_path"] = args.browser_executable
            browser = playwright.chromium.launch(**launch)
            report["browser"] = {"engine": "chromium", "version": browser.version}
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(7000)
            page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
            page.on("console", lambda message: report["console_errors"].append(message.text)
                    if message.type == "error" else None)
            page.on("dialog", lambda dialog: dialog.accept())

            def shot(name):
                path = output / "screenshots" / (name + ".png")
                page.screenshot(path=path, full_page=True, animations="disabled")
                report["screenshots"].append({"file": str(path.relative_to(output)),
                                              "viewport": page.viewport_size})

            def check(name, action):
                started = time.monotonic()
                item = {"name": name, "status": "running"}
                report["checks"].append(item)
                checkpoint()
                try:
                    details = action()
                    item.update(status="pass", details=details)
                    print(name + ": PASS", flush=True)
                except Exception as error:
                    item.update(status="fail", error={"type": type(error).__name__, "message": str(error),
                                                       "traceback": traceback.format_exc()})
                    try:
                        shot("failure-" + name)
                    except Exception:
                        pass
                    first_line = str(error).splitlines()
                    print(name + ": FAIL: " + (first_line[0] if first_line else type(error).__name__), flush=True)
                finally:
                    item["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    checkpoint()

            def fresh(tab="link"):
                page.goto(BASE_URL)
                page.locator("#tab-" + tab).click()

            def consent():
                page.locator("#consent").check()

            def layout_sizes():
                return page.evaluate("""() => ({
                    viewport: document.documentElement.clientWidth,
                    document: document.documentElement.scrollWidth,
                    overflowing: [...document.querySelectorAll('body *')].filter(el => {
                      const r = el.getBoundingClientRect();
                      return r.width && r.height && (r.right > innerWidth + 1 || r.left < -1);
                    }).slice(0, 12).map(el => ({tag: el.tagName, id: el.id, cls: el.className,
                                              right: Math.round(el.getBoundingClientRect().right)}))
                })""")
            def layout(width, height, tab):
                page.set_viewport_size({"width": width, "height": height})
                fresh(tab)
                shot(f"layout-{width}-{tab}")
                sizes = layout_sizes()
                assert sizes["document"] <= sizes["viewport"], sizes
                return sizes

            for width, height, tab in [(1440, 1000, "link"), (390, 844, "link"), (320, 700, "link"),
                                       (390, 844, "upload"), (390, 844, "batch"), (390, 844, "library"),
                                       (320, 700, "upload"), (320, 700, "batch"), (320, 700, "library")]:
                check(f"layout_{width}_{tab}", lambda w=width, h=height, t=tab: layout(w, h, t))
            page.set_viewport_size({"width": 1440, "height": 1000})

            def permission_required():
                fresh()
                page.locator("#url").fill("https://www.youtube.com/watch?v=QaSuccess01")
                posted = []
                listener = lambda request: posted.append(request.url) if request.method == "POST" else None
                page.on("request", listener)
                try:
                    page.locator("#submit").click()
                    assert page.locator("#consent").evaluate("el => !el.validity.valid")
                    assert not posted, posted
                finally:
                    page.remove_listener("request", listener)
                return {"browser_validation_blocks_missing_consent": True}
            check("consent_required", permission_required)

            def empty_source(tab, expected):
                fresh(tab)
                consent()
                page.locator("#submit").click()
                expect(page.locator("#status-title")).to_have_text(expected)
            for tab, expected in [("link", "Link required"), ("upload", "File required"), ("batch", "Links required")]:
                check("empty_" + tab, lambda t=tab, e=expected: empty_source(t, e))

            def inactive_invalid_url(tab, expected):
                fresh()
                page.locator("#url").fill("this is not a URL")
                page.locator("#tab-" + tab).click()
                expect(page.locator("#url")).to_be_disabled()
                expect(page.locator("#file" if tab == "upload" else "#batch-urls")).to_be_enabled()
                consent()
                page.locator("#submit").click()
                expect(page.locator("#status-title")).to_have_text(expected, timeout=3000)
                page.locator("#tab-link").click()
                expect(page.locator("#url")).to_be_enabled()
                expect(page.locator("#url")).to_have_value("this is not a URL")
                assert page.locator("#url").evaluate("el => el.validity.typeMismatch"), "Active URL validation was lost."
            for tab, expected in [("upload", "File required"), ("batch", "Links required")]:
                check("inactive_url_does_not_block_" + tab,
                      lambda t=tab, e=expected: inactive_invalid_url(t, e))

            def invalid_link():
                fresh()
                consent()
                page.locator("#url").fill("https://example.com/not-a-supported-video")
                with page.expect_response(lambda r: r.url.endswith("/api/link") and r.request.method == "POST") as sent:
                    page.locator("#submit").click()
                assert sent.value.status == 400
                expect(page.locator("#status-title")).to_have_text("Could not start")
                assert page.locator("#status-detail").inner_text().strip()
                shot("unsupported-link-error")
            check("unsupported_link_error", invalid_link)

            def invalid_upload(filename, expected_status, terminal):
                fresh("upload")
                consent()
                page.locator("#file").set_input_files(output / filename)
                page.locator("#model").select_option("tiny")
                with page.expect_response(lambda r: r.url.endswith("/api/upload") and r.request.method == "POST") as sent:
                    page.locator("#submit").click()
                assert sent.value.status == expected_status, sent.value.text()
                expect(page.locator("#status-title")).to_have_text(terminal, timeout=20000)
                assert page.locator("#status-detail").inner_text().strip()
            check("invalid_upload_type", lambda: invalid_upload("invalid.txt", 400, "Could not start"))
            check("empty_upload_rejected", lambda: invalid_upload("empty.wav", 400, "Could not start"))
            check("corrupt_upload_error", lambda: invalid_upload("corrupt.wav", 200, "Unable to transcribe"))

            def download(selector, filename):
                with page.expect_download() as waiting:
                    page.locator(selector).click()
                target = output / "downloads" / filename
                waiting.value.save_as(target)
                assert target.stat().st_size > 0
                return target

            upload_record = {}

            def actual_upload():
                fresh("upload")
                consent()
                page.locator("#file").set_input_files(audio_path)
                page.locator("#language").select_option("en")
                page.locator("#model").select_option("tiny")
                page.locator("#summary").check()  # Controlled failure; original ASR must survive.
                page.locator("#highlights").check()
                polled = []
                listener = lambda request: polled.append(request.url) if re.search(r"/api/jobs/[a-f0-9]{32}$", request.url) else None
                page.on("request", listener)
                try:
                    with page.expect_response(lambda r: r.url.endswith("/api/upload") and r.request.method == "POST") as sent:
                        page.locator("#submit").click()
                    assert sent.value.status == 200, sent.value.text()
                    job_id = sent.value.json()["id"]
                    shot("upload-processing")
                    expect(page.locator("#status-title")).to_have_text("Transcript created", timeout=240000)
                finally:
                    page.remove_listener("request", listener)
                expect(page.locator("#results")).to_be_visible()
                expect(page.locator("#result-warnings")).to_contain_text("Summary:")
                text = page.locator("#preview").inner_text()
                words = set(re.findall(r"[a-z]+", text.lower()))
                assert len(words & {"hello", "recognition", "test", "speaking", "words"}) >= 4, text
                assert polled, "No actual polling request was observed."
                record_response = context.request.get(BASE_URL + "/api/library/" + job_id)
                assert record_response.status == 200
                upload_record.update(record_response.json())
                assert not list((data_root / "jobs" / job_id).glob("input.*")), "Uploaded audio was not cleaned."
                exports = {}
                for code in ("txt", "srt", "vtt", "json", "zip"):
                    target = download(f'#downloads a[href$="/download/{code}"]', "upload." + code)
                    exports[code] = {"bytes": target.stat().st_size,
                                     "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
                assert text.strip() in (output / "downloads/upload.txt").read_text(encoding="utf-8")
                with zipfile.ZipFile(output / "downloads/upload.zip") as archive:
                    assert {"transcript.txt", "transcript.srt", "transcript.vtt", "transcript.json"} <= set(archive.namelist())
                shot("upload-result")
                report["asr_executed_successfully"] = args.asr == "real"
                return {"job_id": job_id, "asr": args.asr, "preview": text,
                        "poll_requests": len(polled), "segments": len(upload_record["segments"]), "exports": exports}
            check("upload_asr_polling_exports", actual_upload)

            def upload_source_highlights():
                from source_highlights import validate_highlights
                highlights = upload_record["highlights"]
                validate_highlights(highlights, upload_record["segments"])
                expect(page.locator("#highlights-result")).to_be_visible()
                expect(page.locator("#highlights-result")).to_contain_text("not a complete summary")
                for excerpt in highlights["excerpts"]:
                    assert excerpt["text"] in page.locator("#highlights-result").inner_text()
                json_path = download('#downloads a[href$="/download/highlights_json"]', "upload-highlights.json")
                assert json.loads(json_path.read_text()) == highlights
                markdown = download('#downloads a[href$="/download/highlights_md"]', "upload-highlights.md")
                assert "# Source highlights" in markdown.read_text()
                page.locator("#highlights-result button").first.click()
                expect(page.locator("#editor")).to_be_visible()
                first = highlights["excerpts"][0]["segment_indices"][0]
                expect(page.get_by_label(f"Text of segment {first + 1}", exact=True)).to_have_value(upload_record["segments"][first]["text"])
                page.locator("#editor-close").click()
                shot("upload-source-highlights")
                return {"actual_asr_source": args.asr, "source_sha256": highlights["source_sha256"],
                        "excerpts": len(highlights["excerpts"]), "source_jump_and_exports": "pass"}
            check("actual_upload_source_highlights_and_downloads", upload_source_highlights)

            def upload_result_mobile_layout():
                assert upload_record, "The upload result was unavailable for this dependent check."
                sizes_at_widths = []
                try:
                    for width, height in [(390, 844), (320, 700)]:
                        page.set_viewport_size({"width": width, "height": height})
                        shot(f"upload-result-mobile-{width}")
                        sizes = layout_sizes()
                        sizes_at_widths.append(sizes)
                        assert sizes["document"] <= sizes["viewport"], sizes
                        bounds = page.locator("#copy").bounding_box()
                        assert bounds and bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width, bounds
                finally:
                    page.set_viewport_size({"width": 1440, "height": 1000})
                return {"mobile_layouts": sizes_at_widths}
            check("upload_result_mobile_layout", upload_result_mobile_layout)

            def saved_edits_refresh_visible_result():
                assert upload_record, "The upload result was unavailable for this dependent check."
                page.locator("#result-actions button").click()
                edited = "Saved browser edit. These are the current words, with 12 records."
                title = "Updated browser upload title"
                page.locator("#edit-title").fill(title)
                page.get_by_label("Text of segment 1", exact=True).fill(edited)
                page.get_by_label("Speaker of segment 1", exact=True).fill("Reader")
                page.locator("#editor-save").click()
                expect(page.locator("#editor-message")).to_contain_text("Saved.")
                page.locator("#editor-close").click()
                current = download('#downloads a[href$="/download/txt"]', "edited-upload.txt")
                assert "Reader: " + edited in current.read_text(encoding="utf-8")
                expect(page.locator("#preview")).to_contain_text("Reader: " + edited)
                expect(page.locator("#result-meta")).to_contain_text(title)
                expect(page.locator("#downloads a")).to_have_count(5)
                expect(page.locator("#summary-result")).to_be_hidden()
                expect(page.locator("#highlights-result")).to_be_hidden()
                saved_job = context.request.get(BASE_URL + "/api/jobs/" + upload_record["id"]).json()
                assert saved_job["title"] == title and "Reader: " + edited in saved_job["preview"], saved_job
                assert not saved_job["extras"]["summary"] and not saved_job["extras"]["translation_language"], saved_job
                assert not saved_job["extras"]["highlights"], saved_job
                shot("saved-result-refreshed")
                return {"visible_preview_and_download_match_saved_edit": True,
                        "title_speaker_and_job_status_refreshed": True}
            check("saved_edits_refresh_visible_result", saved_edits_refresh_visible_result)

            def link_success():
                fresh()
                consent()
                page.locator("#mode").select_option("captions")
                page.locator("#url").fill("https://www.youtube.com/watch?v=QaSuccess01")
                page.locator("#submit").click()
                expect(page.locator("#status-title")).to_have_text("Transcript created", timeout=20000)
                expect(page.locator("#preview")).to_contain_text("owned browser workflow")
                return {"caption_acquisition": "controlled_owned_fixture", "http_queue_storage_ui": "actual"}
            check("single_link_workflow", link_success)

            def batch_validation():
                fresh("batch")
                consent()
                url = "https://www.youtube.com/watch?v=QaSuccess01"
                page.locator("#batch-urls").fill(url + "\n" + url)
                expect(page.locator("#batch-count")).to_have_text("2")
                page.locator("#submit").click()
                expect(page.locator("#status-detail")).to_contain_text("duplicate")
            check("batch_duplicate_validation", batch_validation)

            def batch_partial_failure():
                fresh("batch")
                consent()
                page.locator("#mode").select_option("captions")
                page.locator("#batch-urls").fill("\n".join(
                    "https://www.youtube.com/watch?v=" + ident for ident in ("QaSuccess02", "QaFailure01")))
                page.locator("#submit").click()
                expect(page.locator("#status-title")).to_have_text("Batch complete", timeout=30000)
                expect(page.locator("#batch-progress")).to_contain_text("2/2 completed · 1 failed")
                archive_path = download("#batch-download a", "batch.zip")
                with zipfile.ZipFile(archive_path) as archive:
                    names = archive.namelist()
                    assert any(name.endswith(".txt") for name in names), names
                    assert "batch-report.json" in names, names
                shot("batch-complete")
                fresh("library")
                expect(page.locator("#saved-batches")).to_contain_text("1 failed")
                page.locator("#saved-batches button").first.click()
                expect(page.locator("#batch-progress")).to_contain_text("2/2 completed · 1 failed")
                return {"provider": "controlled_owned_caption_fixtures", "archive_files": names}
            check("batch_partial_failure_download_history", batch_partial_failure)

            def search_edit_export():
                fresh("library")
                page.locator("#library-search").fill("no-such-owned-fixture-identifier")
                page.locator("#library-search").press("Enter")
                expect(page.locator("#library-items")).to_have_text("No saved transcripts found yet.")
                page.locator("#library-search").fill("Zebra docket")
                page.locator("#library-refresh").click()
                expect(page.locator("#library-items .library-item")).to_have_count(1)
                page.locator("#library-items button").click()
                expect(page.locator("#editor-page-label")).to_have_text("Segments 1–30 of 35")
                assert page.evaluate("() => typeof window.uiFixtureExecuted") == "undefined"
                assert page.locator('#editor-downloads a[href$="/download/translation_srt"]').count() == 1
                assert page.locator('#editor-downloads a[href$="/download/summary_md"]').count() == 1
                page.locator("#edit-title").fill("")
                page.locator("#editor-save").click()
                expect(page.locator("#editor-message")).to_have_text("A title is required.")
                page.locator("#edit-title").fill("Edited owned fixture — English and Ελληνικά")
                first = page.get_by_label("Text of segment 1", exact=True)
                first.fill("")
                page.locator("#editor-save").click()
                expect(page.locator("#editor-message")).to_have_text("Every segment needs text.")
                first.fill("Edited first segment. Keep 12 records and the word ζέβρα.")
                page.get_by_label("Speaker of segment 1", exact=True).fill("Alex")
                page.locator("#editor-next").click()
                expect(page.locator("#editor-page-label")).to_have_text("Segments 31–35 of 35")
                page.get_by_label("Text of segment 35", exact=True).fill("Edited final segment remains saved.")
                page.locator("#editor-prev").click()
                expect(page.get_by_label("Text of segment 1", exact=True)).to_have_value(
                    "Edited first segment. Keep 12 records and the word ζέβρα.")
                page.locator("#editor-save").click()
                expect(page.locator("#editor-message")).to_contain_text("Saved.")
                expect(page.locator("#editor-downloads a")).to_have_count(5)
                record = context.request.get(BASE_URL + "/api/library/" + FIXTURE_ID).json()
                assert len(record["segments"]) == 35
                assert record["segments"][0]["speaker"] == "Alex"
                assert record["segments"][-1]["text"] == "Edited final segment remains saved."
                assert record["translations"] == {} and record["summary"] is None
                text_path = download('#editor-downloads a[href$="/download/txt"]', "edited-library.txt")
                assert "Edited first segment" in text_path.read_text(encoding="utf-8") and "Edited final segment" in text_path.read_text(encoding="utf-8")
                shot("library-edited-desktop")
                mobile_sizes = []
                try:
                    for width, height in [(390, 844), (320, 700)]:
                        page.set_viewport_size({"width": width, "height": height})
                        shot(f"library-edited-mobile-{width}")
                        sizes = layout_sizes()
                        mobile_sizes.append(sizes)
                        assert sizes["document"] <= sizes["viewport"], sizes
                        for control in ("#editor-prev", "#editor-next", "#editor-save", "#editor-delete"):
                            bounds = page.locator(control).bounding_box()
                            assert bounds and bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width, {"control": control, "bounds": bounds}
                finally:
                    page.set_viewport_size({"width": 1440, "height": 1000})
                return {"segments_preserved": 35, "edits_across_pages_saved": True,
                        "derived_enhancements_invalidated": True, "mobile_layouts": mobile_sizes}
            check("library_search_edit_pagination_exports", search_edit_export)
            page.set_viewport_size({"width": 1440, "height": 1000})

            def library_source_highlights():
                from source_highlights import validate_highlights
                fresh("library")
                page.locator("#library-search").fill("Edited owned fixture")
                page.locator("#library-refresh").click()
                fixture_row = page.locator("#library-items .library-item").filter(
                    has_text="Edited owned fixture — English and Ελληνικά")
                expect(fixture_row).to_have_count(1)
                fixture_row.get_by_role("button", name="Open / edit", exact=True).click()
                page.locator("#editor-highlights").click()
                expect(page.locator("#editor-message")).to_contain_text("Source highlights saved")
                before = context.request.get(BASE_URL + "/api/library/" + FIXTURE_ID).json()
                validate_highlights(before["highlights"], before["segments"])
                expect(page.locator("#editor-highlights-result")).to_be_visible()
                first = page.get_by_label("Text of segment 1", exact=True)
                first.fill(first.input_value() + " A saved clarification.")
                expect(page.locator("#editor-highlights")).to_be_disabled()
                page.locator("#editor-save").click()
                expect(page.locator("#editor-message")).to_contain_text("Saved.")
                expect(page.locator("#editor-highlights-result")).to_be_hidden()
                page.locator("#editor-highlights").click()
                expect(page.locator("#editor-message")).to_contain_text("Source highlights saved")
                after = context.request.get(BASE_URL + "/api/library/" + FIXTURE_ID).json()
                validate_highlights(after["highlights"], after["segments"])
                assert before["highlights"]["source_sha256"] != after["highlights"]["source_sha256"]
                shot("saved-source-highlights")
                page.locator("#editor-close").click()
                return {"saved_source_generation": "pass", "unsaved_edit_guard": "pass", "edit_regeneration": "pass"}
            check("library_source_highlights_edit_and_regenerate", library_source_highlights)

            def edits_during_save():
                fresh("library")
                fixture_row = page.locator("#library-items .library-item").filter(
                    has_text="Edited owned fixture — English and Ελληνικά")
                expect(fixture_row).to_have_count(1)
                fixture_row.get_by_role("button", name="Open / edit", exact=True).click()
                first = page.get_by_label("Text of segment 1", exact=True)
                earlier = first.input_value() + " First saved version."
                newer = earlier + " This correction was typed while saving."
                first.fill(earlier)
                intercepted = []
                endpoint = BASE_URL + "/api/library/" + FIXTURE_ID

                def finish_save_after_edit(route):
                    if route.request.method != "PUT" or intercepted:
                        return route.continue_()
                    response = route.fetch()  # The real SQLite save completes; its response waits.
                    assert response.ok, response.text()
                    intercepted.append(True)
                    page.evaluate("""text => {
                      const input=document.querySelector('[aria-label="Text of segment 1"]');
                      input.value=text; input.dispatchEvent(new Event('input',{bubbles:true}));
                    }""", newer)
                    route.fulfill(response=response)

                page.route(endpoint, finish_save_after_edit)
                try:
                    page.locator("#editor-save").click()
                    expect(page.locator("#editor-message")).to_contain_text("Your newer edits are still here")
                    expect(first).to_have_value(newer)
                    expect(page.locator("#editor-highlights")).to_be_disabled()
                    assert intercepted
                    saved = context.request.get(endpoint).json()
                    assert saved["segments"][0]["text"] == earlier
                    assert saved["highlights"] is None
                finally:
                    page.unroute(endpoint, finish_save_after_edit)
                page.locator("#editor-save").click()
                expect(page.locator("#editor-message")).to_contain_text("Saved.")
                assert context.request.get(endpoint).json()["segments"][0]["text"] == newer
                page.locator("#editor-highlights").click()
                expect(page.locator("#editor-message")).to_contain_text("Source highlights saved")
                shot("edits-preserved-during-save")
                page.locator("#editor-close").click()
                return {"actual_sqlite_save": True, "newer_unsaved_edit_preserved": True,
                        "explicit_second_save_persisted_newer_text": True}
            check("new_edits_survive_inflight_save", edits_during_save)

            def edits_during_open():
                fresh("library")
                fixture_row = page.locator("#library-items .library-item").filter(
                    has_text="Edited owned fixture — English and Ελληνικά")
                expect(fixture_row).to_have_count(1)
                fixture_row.get_by_role("button", name="Open / edit", exact=True).click()
                expect(page.locator("#editor")).to_be_visible()
                expect(page.locator("#edit-title")).to_have_value("Edited owned fixture — English and Ελληνικά")
                old_title = page.locator("#edit-title").input_value()
                first = page.get_by_label("Text of segment 1", exact=True)
                newer = first.input_value() + " Keep this edit made while opening another transcript."
                endpoint = BASE_URL + "/api/library/" + upload_record["id"]
                other = context.request.get(endpoint).json()
                intercepted = []

                def finish_open_after_edit(route):
                    response = route.fetch()
                    assert response.ok, response.text()
                    intercepted.append(True)
                    page.evaluate("""text => {
                      const input=document.querySelector('[aria-label="Text of segment 1"]');
                      input.value=text; input.dispatchEvent(new Event('input',{bubbles:true}));
                    }""", newer)
                    route.fulfill(response=response)

                page.route(endpoint, finish_open_after_edit)
                try:
                    other_row = page.locator("#library-items .library-item").filter(has_text=other["title"])
                    expect(other_row).to_have_count(1)
                    other_row.get_by_role("button", name="Open / edit", exact=True).click()
                    expect(page.locator("#editor-message")).to_contain_text("Newer edits were kept")
                    expect(page.locator("#edit-title")).to_have_value(old_title)
                    expect(first).to_have_value(newer)
                    assert intercepted
                finally:
                    page.unroute(endpoint, finish_open_after_edit)
                page.locator("#editor-save").click()
                expect(page.locator("#editor-message")).to_contain_text("Saved.")
                original = context.request.get(BASE_URL + "/api/library/" + FIXTURE_ID).json()
                assert original["segments"][0]["text"] == newer
                assert context.request.get(endpoint).json() == other
                page.locator("#editor-highlights").click()
                expect(page.locator("#editor-message")).to_contain_text("Source highlights saved")
                page.locator("#editor-close").click()
                return {"pending_open_preserved_newer_edit": True,
                        "saved_to_original_transcript": True, "other_transcript_unchanged": True}
            check("new_edits_survive_inflight_open", edits_during_open)

            def backup_delete_restore():
                fresh("library")
                source_before = context.request.get(BASE_URL + "/api/library/" + FIXTURE_ID).json()
                assert source_before["highlights"] is not None, "The backup fixture must contain actual saved highlights."
                backup_path = download('a[href="/api/library/backup"]', "library-backup.zip")
                with zipfile.ZipFile(backup_path) as archive:
                    names = archive.namelist()
                    assert "transcripts.json" in names, names
                before = context.request.get(BASE_URL + "/api/library?limit=100").json()["items"]
                page.locator("#library-search").fill("Owned")
                page.locator("#library-refresh").click()
                fixture_row = page.locator("#library-items .library-item").filter(has_text="fixture")
                expect(fixture_row).to_have_count(1)
                fixture_row.get_by_role("button", name="Open / edit", exact=True).click()
                page.locator("#editor-delete").click()
                expect(page.locator("#editor")).to_be_hidden()
                assert context.request.get(BASE_URL + "/api/library/" + FIXTURE_ID).status == 404
                page.locator("#library-restore-btn").click()
                expect(page.locator("#library-feedback")).to_have_text("Select a LinkScribe backup ZIP first.")
                page.locator("#library-restore-file").set_input_files(backup_path)
                page.locator("#library-restore-btn").click()
                expect(page.locator("#library-feedback")).to_contain_text("Restore complete: 1 imported;")
                restored = context.request.get(BASE_URL + "/api/library/" + FIXTURE_ID)
                assert restored.status == 200
                assert restored.json()["highlights"] == source_before["highlights"]
                after = context.request.get(BASE_URL + "/api/library?limit=100").json()["items"]
                assert len(after) == len(before)
                page.locator("#library-restore-file").set_input_files(output / "invalid-backup.zip")
                page.locator("#library-restore-btn").click()
                expect(page.locator("#library-feedback")).to_contain_text("Restore rejected:")
                assert len(context.request.get(BASE_URL + "/api/library?limit=100").json()["items"]) == len(before)
                shot("backup-restore-validation")
                return {"records_before": len(before), "records_after": len(after), "restored_records": 1}
            check("backup_export_delete_restore_validation", backup_delete_restore)

            def diagnostics_ui():
                fresh("library")
                page.locator("#diagnostics-btn").click()
                expect(page.locator("#setup-info")).to_contain_text("Python ")
                expect(page.locator("#setup-info")).to_contain_text("Whisper: installed")
                expect(page.locator("#setup-info")).to_contain_text("Summary: Set a valid LINKSCRIBE_OLLAMA_MODEL.")
                expect(page.locator("#setup-info")).to_contain_text("Translation: Set a valid LINKSCRIBE_TRANSLATION_MODEL.")
                shot("diagnostics")
                return {"visible_report": page.locator("#setup-info").inner_text()}
            check("diagnostics_ui_independent_model_errors", diagnostics_ui)

            def origin_guard():
                response = context.request.post(BASE_URL + "/api/link", headers={"Origin": "https://example.com"},
                                                form={"url": "https://www.youtube.com/watch?v=QaSuccess01",
                                                      "consent": "true", "mode": "captions"})
                assert response.status == 403
                return {"cross_site_post_status": response.status, "same_origin_browser_writes": "exercised_above"}
            check("actual_origin_guard", origin_guard)

            def javascript_errors():
                assert not report["page_errors"], report["page_errors"]
                return {"uncaught_page_exceptions": 0,
                        "console_messages_include_deliberate_http_error_scenarios": True}
            check("no_uncaught_javascript_errors", javascript_errors)
            report["complete"] = True
            browser.close()
            browser = None
    except Exception as error:
        report["fatal_error"] = {"type": type(error).__name__, "message": str(error),
                                 "traceback": traceback.format_exc()}
        print("BROWSER QA ERROR: " + str(error), file=sys.stderr, flush=True)
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        log.close()
        scratch.cleanup()
        counts = Counter(item["status"] for item in report["checks"])
        report["counts"] = dict(counts)
        report["result"] = "pass" if report["complete"] and not counts["fail"] else "fail"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        checkpoint()
    print(json.dumps({key: report[key] for key in ["complete", "result", "counts", "asr_mode",
                                                    "asr_executed_successfully"]}), flush=True)
    return int(report["result"] != "pass")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--asr", choices=("real", "stub"), default="real")
    parser.add_argument("--server-python", help="Optional Python executable containing the app's dependencies.")
    parser.add_argument("--browser-executable", help="Optional existing Chromium executable.")
    parser.add_argument("--serve", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.asr)
        return 0
    if args.output is None:
        parser.error("--output is required")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
