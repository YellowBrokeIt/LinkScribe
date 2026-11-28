# Hosted warning persistence and browser review

The actual Chromium run on commit `7a53991da60c9e052be9a72299218b291b364c8d`
passed all 35 checks, retaining all preceding 34 check names in their original
order. The added warning case survived an actual server process restart,
PID 4203 to 7097, with unchanged original text and stored warning metadata.
All eight source identities match the immutable published files and Git blobs.
Actual Tiny speech recognition and the following editor/export/backup checks
passed; zero uncaught JavaScript exceptions occurred.

[Independent review](independent-hosted-review.json) and the
[artifact audit](retained-artifact-audit.json) record the exact scope. Warnings
remain visible in batch detail/history and the saved editor after restart;
opening the exact clean record clears the warning panel. The actual six-record
[downloaded backup](artifact/downloads/library-backup.zip) preserves the two
warned records and their source text. This controlled warning case uses owned
captions and intentionally invalid enhancement settings, not live provider
acquisition or translation-meaning evaluation.

## Visually reviewed screenshots

- [Desktop warnings](artifact/screenshots/processing-warnings-desktop.png)
- [320-pixel mobile warnings](artifact/screenshots/processing-warnings-mobile.png)
- [Warnings after server restart](artifact/screenshots/processing-warnings-after-restart.png)
- [Later clean editor](artifact/screenshots/library-edited-mobile-320.png)

The mobile report measured 320-pixel viewport and document width with no overflow.
Long notes wrap into tall but readable rows. No blocking clipping or overlap was
observed in these views. The immediate clean-record clearing is established by
the live assertion; its screenshot is a later clean-editor view.

## Artifact identity and retained selection

[Run 46107711847](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46107711847)
and job 140864083983 completed successfully. The original artifact is 15248073165,
11,939,810 ZIP bytes, SHA-256
`f12408d6eca1196493722eed48da5f07222d76caf715d2618b289ffa14852a24`.
The independent reviewer downloaded the complete ZIP, checked all 45 extracted
files and reviewed its source snapshots. The [original review-bundle inventory](original-full-review-manifest.json)
retains all 70 original file identities; it is an inventory of that original
bundle, not a claim that every listed file is copied into this directory.

This repository selection retains the complete browser report, all non-image
artifact files including real backup/export bytes and owned speech, the four
relevant screenshots, independent findings and the audit program. Other layout
screenshots, duplicate source snapshots and the original full ZIP are omitted
from this selection. The [selection manifest](selection-manifest.json) enumerates
exactly the files stored here. The original audit program expects the complete
original review bundle; its retained successful result documents the audit that
actually occurred.

These results certify the stated checkpoint and scoped behavior. Generated-text
meaning, provider reliability and the remaining v1 gates are still open.
