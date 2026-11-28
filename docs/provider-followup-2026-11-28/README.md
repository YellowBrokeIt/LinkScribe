# Public-provider investigation and Vimeo player correction

## Result and scope

A real local Vimeo link → download → full-recording Whisper transcription → SQLite → exports → restart run passed on **2026-11-27 at 23:50:55 UTC**. The tested input was the explicitly supplied public player URL `https://player.vimeo.com/video/19934655`, a licensed Sintel re-render. The previous regular-page and restricted-embed failures remain failures.

This run used frozen commit [`002d8fc66e5f3666b40477878e064c825ef1c495`](https://github.com/YellowBrokeIt/LinkScribe/commit/002d8fc66e5f3666b40477878e064c825ef1c495) with **only the Vimeo player parser correction** applied. It does not establish a pass for the concurrently developed highlights feature, the final integrated revision, or future hosted checks. [evidence.json](evidence.json) records the exact tested patch, source fingerprints, model identity, individual outcomes and raw-report hashes.

The run is a pipeline pass. Semantic accuracy and subtitle alignment remain unreviewed. The raw output contains suspicious and repeated phrases, and automatic English language confidence was only 0.353. This evidence does not establish v1 quality.

## Why the player link failed before

`parse_source` recognized `player.vimeo.com/video/ID`, then rewrote it to `vimeo.com/ID`. The [yt-dlp Vimeo extractor](https://github.com/yt-dlp/yt-dlp/blob/2026.11.23/yt_dlp/extractor/vimeo.py) handles those routes differently: an explicit player URL can use public player configuration, while a regular page can fall back to Vimeo's API. The [current upstream guidance](https://github.com/yt-dlp/yt-dlp#vimeo) states that the web API client needs a logged-in account. The installed extractor was already the [2026.11.23 release](https://github.com/yt-dlp/yt-dlp/releases/tag/2026.11.23).

The correction preserves a strictly reconstructed explicit public player URL. It retains the same numeric video ID and provider identity, strips queries and fragments, and continues to reject extra paths, credentials, ports and other hosts. Regular Vimeo pages keep their previous behavior. Batch duplicate identity is `(provider, video_id)`, so supplying both forms of one video cannot queue it twice. Stored player links also survive parsing during recovery.

No automatic page-to-player fallback, login, cookie, private hash, custom referrer, alternate proxy or access workaround was added. The [Vimeo privacy documentation](https://help.vimeo.com/hc/en-us/articles/12426199699985-About-video-privacy-settings) distinguishes public viewing from restricted privacy settings; a public-player URL is not a guarantee that every video is accessible.

## Observed cases

| Case | Observed result | Meaning |
| --- | --- | --- |
| Earlier hosted YouTube trailer fixtures `HOfdboHvshg` and `WwHux5QZfC8` | `This content isn’t available.` | Original failures retained; this message alone does not establish whether a video was removed or access was blocked. |
| Earlier hosted Vimeo regular page `11721242` | `The web client only works when logged-in.` | Original failure retained. |
| Explicit player `11721242` in this investigation | HTTP 403; `Cannot download embed-only video without embedding URL.` | Treated as restricted; no forged embedding URL or referrer was supplied. |
| Official Blender YouTube full film `R6MlUcmOul8` | Public metadata and 33 formats found; actual media download returned HTTP 403 | Metadata success was not counted as provider success. The media origin was `rr5---sn-q4flrn7r.googlevideo.com`, with `Server: envoy` and a `Site Unavailable` response. This records the actual response without claiming a proven root cause. |
| Explicit public player `19934655`, first full attempt | Download and decoding passed; model initialization failed because the existing SOCKS proxy required the missing `socksio` package | Concrete runtime dependency failure, recorded separately from Vimeo access. |
| Same explicit public player, corrected runtime | Full pipeline passed | Added `socksio==1.0.0` in an isolated dependency target while retaining the existing proxy and certificate verification. |

The original hosted provider report is [run 45897284195](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284195). The follow-up JSON and wrapper add separately named licensed fixtures; they do not replace those original fixtures or rewrite their results.

## Successful full-recording evidence

The successful run lasted from **23:48:16 to 23:50:55 UTC** on November 27. It used [Teddl's public Sintel re-render](https://vimeo.com/19934655), whose public description identifies CC BY 3.0; the [Blender source license](https://durian.blender.org/sharing/) and attribution are retained in the fixture.

| Check | Recorded evidence |
| --- | --- |
| Actual downloaded media | 17,669,814 bytes; SHA-256 `de4bf866b48858c8fe7b9448ecc3d4713dfd74f44c7ca87736bda6c558fc2364` |
| Decoded recording | 888.070375 seconds; 14,209,126 samples at 16 kHz |
| ASR input | The same complete decoded array reached normal `transcribe`; `vad_filter=false`, `clip_timestamps="0"` |
| Local model | Faster Whisper 1.2.1, `small`, CPU; resolved revision `536b0662742c02347bc0e980a01041f333bce120` |
| Model weights | SHA-256 `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |
| Saved output | 81 segments; last segment ended at 880.06 seconds |
| Persistence and downloads | SQLite matched saved segments; TXT, SRT, VTT, JSON and ZIP exports passed; text order retained |
| Restart and cleanup | Saved record/downloads survived restart; temporary input audio was cleaned |
| Source integrity | Frozen tested source hashes matched before and after the run |
| Not exercised here | Mixed-provider batch, nonspeech cases and separate tail diagnostics; prior evidence remains separately scoped |
| Not established | Word accuracy, faithful speech coverage, speaker identity, subtitle alignment, highlights quality or general provider availability |

The production change also has **14 focused deterministic tests** covering route preservation, parser round trips, strict validation, dropped privacy/authentication query parameters, unchanged denial behavior and batch duplicate identity. Those tests are not substitutes for the live pipeline evidence.

## Reproduction and remaining work

Use a fresh output directory with the additional fixture runner:

```sh
PYTHONPATH=. python tests/smoke_provider_followups.py \
  --fixture vimeo_sintel_rerendered_player --model small \
  --output qa-vimeo-player
```

The wrapper also exposes `youtube_tears_of_steel_full` and all original fixture names. With no `--fixture`, it runs both added fixtures and retains any failures. It calls the original acceptance harness and fingerprints the wrapper and fixture file; it does not substitute media, captions or generated text. A network/authentication failure remains a failed provider result.

Next steps are to verify the final integrated revision in hosted checks, review actual transcription accuracy against licensed references, and retain a precise YouTube access limitation until a permitted full pipeline succeeds. Repeating the same blocked media request, changing network access controls, or relabeling a metadata probe as success would not resolve that gate.
