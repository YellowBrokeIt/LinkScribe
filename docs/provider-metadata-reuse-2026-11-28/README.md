# Download the metadata that passed validation

This is the frozen local implementation and offline verification record, prepared before a new hosted run. It does not claim hosted verification of this change or a later revision.

The provider adapter previously called `extract_info(url, download=False)` to validate one video's metadata, then called `download([url])`, which performs another extraction. The transfer could therefore depend on a second provider response after the first response had passed the application's checks.

This change passes the validated result to `process_ie_result(info, download=True)`. The adapter also explicitly rejects unresolved non-video results and additional URLs or entries before that call, preventing those result types from dispatching another extractor. The existing canonical provider URL, playlist rejection, duration and declared-size checks, output template, file-size cap, transport settings and retries, readable error wrapping, and worker cleanup remain in place. This patch adds no retry loop, alternate endpoint, credential handling, or model change.

## Upstream route

The exact official [yt-dlp 2026.11.23 source](https://github.com/yt-dlp/yt-dlp/blob/2026.11.23/yt_dlp/YoutubeDL.py) was fetched through the GitHub connector. Its bytes match the installed module used for the offline contract test: SHA256 `1e6e127e8b03e987dfe81dc83e8de1217145339280e043feb867de168aef3e21`.

In that source, `download()` calls `extract_info()` for each URL. `process_ie_result()` accepts the extracted result and processes its download; upstream's info-file download path uses the same method. The adapter calls that method directly on the in-memory result, avoiding the info-file wrapper's possible fallback to another URL extraction. [api-source-review.json](api-source-review.json) records the source identity and scope. The contract concerns one application-level extraction call and no additional extractor dispatch from the validated result; it does not promise one HTTP request or prevent the initial extractor from resolving its own references.

## Verification

The final four-file focused run passed **104 tests**, including **20 new cases**, in 2.08 seconds. [focused-tests.json](focused-tests.json) records exact source hashes and command; [focused-tests.txt](focused-tests.txt) retains the output. The earlier 102-pass result is preserved separately in [focused-tests-before-review.json](focused-tests-before-review.json). Independent review found the additional-URL branch, recorded in [review-correction.json](review-correction.json); two more rejection cases cover its correction.

The new cases verify a single extraction and transfer of the same validated object, rejection of empty/playlist/unresolved/oversized metadata before downloading, retained error cause and readable public message, interrupted-download cleanup, accepted output requirements, and the final file-size check. A native contract case uses the installed yt-dlp processing code with an owned fake extractor and intercepted media transfer; any network request fails the test. Existing canonical Vimeo player, restriction and certificate-setting tests were adapted to the new method and passed.

The [final independent review](independent-review.json) found no remaining blocker on the exact corrected source. It verified that the production AST changes are confined to the reviewed download function, that the initial 102-pass identities are recoverable before the narrow correction, and that the existing limits, transport and cleanup paths remain intact. [manifest.json](manifest.json) binds this evidence bundle and the five implementation/test files. The parent integration owns the combined suite and later hosted verification.

## What this change does not establish

The previous 7a53991 Dailymotion incident remains an extraction failure with `No video formats found!`. Its retained logs do not identify whether the first or second extraction failed. This patch removes a redundant provider call and ties downloading to checked metadata; it is **not evidence that the intermittent provider incident is fixed**. No live provider or speech/language model call was made during this implementation.

The associated historical speech failure is also unchanged: the exact world-change phrase was retained at native interval 509.18–520.18 seconds, outside the frozen gate's full-containment rule for 510–529 seconds. No speech outputs, decoder settings, anchor windows, or frozen checkers were changed.
