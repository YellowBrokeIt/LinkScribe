# Reject newly introduced writing systems in translation drafts

The expanded Gemma 4 development run produced Arabic, Persian and Cyrillic words
inside translations requested in Greek, even though those words were absent
from the source. The responses had valid JSON, normal completion and complete
source coverage. The previous result checks accepted them structurally.

The production result check now rejects this specific corruption across the
JSON, dedicated-translator and Marian backends. It compares complete normalized
letter/mark runs, allows Latin and Greek text for both supported targets, and
allows other writing systems when the same complete normalized run already
appears in the source. Existing foreign names and quotations are retained;
sharing only a writing system or part of a name does not allow an unrelated
new word. Unicode compatibility normalization is used only for comparison and
recognizes mathematical Latin/Greek letters and presentation forms. Stored
source text and accepted output are not normalized or rewritten.

On rejection, the existing optional-enhancement failure path saves the original
transcript, records the warning in the job and SQLite metadata, and omits the
uncompleted translation from downloads and ZIP exports. The source remains
available after process restart. Other optional work can continue.

## Verification and limits

The initial targeted translation and application tests passed **57/57**.
Independent review then found two false positives: the modifier apostrophe in
`LʼHôpital` and the mathematical symbol `ℵ`, whose Unicode compatibility form is
a Hebrew letter. The first implementation patch, reviewer counterexamples and
first replay are retained as `initial-*` and
`independent-initial-guard-review.json`. Neither failure was published as a
finished fix. The corrected comparison treats name apostrophes/primes and the
four Hebrew-derived letterlike mathematical symbols as boundaries; actual
introduced Hebrew words remain checked.

After those corrections, the full local suite passed **703 tests and
32 subtests**. Tests cover all three translation
backends, preservation of exact foreign names/quotes and Unicode-equivalent
forms, ordinary technical notation, non-mutation, and the actual API/library/
export/restart failure path with a controlled corrupt model reply. These are
software regressions, not real-model translation acceptance.

The [retained-output replay](retained-output-replay.json) applies the new result
check to all twelve already generated, unchanged Gemma 4 v2 outputs. It makes
**zero model requests** and rejects three: the questionnaire quotation, weather
station and textile exhibition cases. Their existing raw reports, source
corpus and executed production checker are bound by SHA256. The other nine
outputs are unchanged by this check and are **not thereby approved**.

The model itself still fails its independent meaning review. This guard does
not detect a wrong name written in Latin/Greek, a borrower changed to a giver,
incorrect quantities, changed permissions or a paraphrase in the wrong target
language. Those errors remain release blockers. No new default, new inference,
fresh validation pass or v1.0 approval is claimed.

`replay.py` preserves the mechanical reproduction and refuses to overwrite the
retained report. The previously frozen model experiment files are unchanged.
Hosted results must be checked against the subsequent published commit; the
earlier `745554b` results cover the preceding implementation only.
