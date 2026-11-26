# Actual public-caption access check — 26 November 2026

One ordinary call to the existing application caption path returned
**`IpBlocked` from `youtube-transcript-api`**. No captions were returned.
This does not establish that the video lacks captions, identify a particular
network cause independently, or prove universal YouTube unavailability.

## Scope and result

The earlier hosted live-provider workflow forced **Audio** mode. Its YouTube
acquisition failures did not test Smart mode's initial caption path. Browser
caption checks used explicitly controlled fixtures. This separate bounded
check exercised the real `app._captions("HOfdboHvshg", "auto")` function on the
same licensed [official Sintel trailer](https://www.youtube.com/watch?v=HOfdboHvshg).

The call used the existing working QA environment with
`youtube-transcript-api` 1.2.5, `requests` 2.34.2 and `certifi` 2026.11.20.
Existing proxy and TLS settings were inherited unchanged. No credentials,
cookies, new proxy, TLS-verification override or alternative acquisition
service was supplied. The attempt failed after **6.366 seconds**.

The check stopped after this ordinary access denial. There was no second-ID
request, full-film substitute or retry. It did not download media or invoke
ASR, a language model, the complete app job route, SQLite or exports. Therefore
it is **caption-acquisition failure evidence**, not full-app success or a
hosted-caption result. Actual Audio-mode failures remain separately recorded.

## Source and retained evidence

The application source hash before and after the call was identical:

`41386cfc78938c8d8a03837e02be7ed4a7a53cbc5525947a73da651304d8c671`

The exact caption function is retained in the raw report, with SHA-256
`eb9c0f2bd1d78ed8df67781740bd99217712994a5341936b7418c4aee7ea8948`. Its source remained unchanged.
The app contained the pending decoded-audio guards; those functions were not
called by this caption-only probe. The recorded source hashes identify the
measured working tree; no later commit is implied without a hash comparison.

- [Unchanged raw outcome](sintel-trailer.json): function source, runtime
  versions, timestamps, complete returned error and exception chain.
  SHA-256: `ef4541468652878bca7079dadecc78478e75a4ee99561a911ac04893a0a42512`.
- [Unchanged scope record](scope.json): inspected harness distinction,
  attempted and deliberately unattempted sources, and interpretation limits.
- [Copy manifest](manifest.json): exact original paths, sizes and checksums.

The error text itself includes the library's generic troubleshooting advice.
No workaround from that text was attempted.

## Attribution

Sintel: © Blender Foundation, [www.sintel.org](https://durian.blender.org/),
with [CC BY 3.0 sharing terms](https://durian.blender.org/sharing/).
The selected fixture is the official Blender trailer already used by the
provider QA. No film, audio, caption text, access token or model weights are
included in this evidence directory.
