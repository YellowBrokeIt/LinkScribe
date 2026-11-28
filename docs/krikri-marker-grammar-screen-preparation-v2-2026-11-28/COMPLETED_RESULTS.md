# Completed grammar-constrained screen: rejected for translation quality

All six original development cases completed under the frozen protocol. The
independent complete-meaning review found **four acceptable outputs and two
major errors**, with no minor-only or operational rejection. Root independently
read all six full sources/raw/restored outputs and agreed with this result.

| Original case | Meaning decision | Main finding |
|---|---|---|
| Transcript terminology | Acceptable | Text versus recording, saving negation, completed 12-minute transcription and unstarted translation all survive. |
| People and roles | Major error | Extra unmarked Nick/Helen clauses introduce name substitutions and contradictory translator/subtitle roles. |
| Bitcoin amounts | Acceptable | Values, separate receipt/transfer, rejected 500 sats, units and ordinary Greek prose survive; 5.000 is valid localization. |
| Negation scope | Acceptable | Both denial scopes, no sales yesterday, undecided possible sale today and correct female references survive. |
| Conditional publication | Acceptable | Correct actors, necessary approval, no-answer condition and Friday/Monday deadlines survive. |
| Uncertain question | Major error | The asking actor becomes Mary; the preserved Μαρία is appended after the quotation without a grammatical connection. |

## Complete outputs determine the result

In the people/roles case, the first returned entry begins:

> Nick sent the text to Helen, not to Elena. Νίκος sent the text to Ελένη, not to Έλενα.

The second returned entry begins:

> Elena is the translator. Nick is doing the recording and Helen is checking the subtitles.

Correct restored clauses follow those statements. The full output still contains
the wrong names and role assignments: the source translator is Ελένη and the
subtitle checker is Έλενα. The original global rules reject these material
additions; the correct later clauses do not remove them.

The question case returns:

> Mary asked: 'Does the file have 12 chapters or 21?'Μαρία

The quoted alternatives, uncertainty and insufficiency of the title are intact.
The name-preservation rule still fails: Mary is a substituted actor name, while
the actual source name remains dangling after the quotation. All three
question-specific criteria are credited separately from this global failure.

## Structural and resource results

All six cases passed the existing execution, schema, exact marker, metadata and
post-restoration application guards. All 13 source-name mentions were restored
from their exact original spans, once and in the original entry. The complete
raw response is preserved before restoration. The independent audit verified
both raw-response routes and independently reconstructed each full restored
result without repairing it.

Actual prompt counts were 261, 350, 262, 266, 302 and 264. Output counts were
59, 93, 68, 56, 62 and 56. Every call stopped normally, below the unchanged
2048-token cap, with empty reasoning. Six generation calls and six acknowledged
unloads occurred; no case was retried. All full source messages, source-derived
spelling maps, settings and meaning criteria remained unchanged.

The measured stage took 144.364313 seconds. Peak owned-process RSS was
5573.8 MiB and PSS was 5564.8 MiB, under the 6144 MiB process budget. All 1,108
resource samples, their memory sums and peak records were checked. The daemon
and owned process group stopped, and the observed resident-model checks were
empty. This remains a standalone experimental measurement, without whole-app
resource approval.

The frozen historical adapter/source-spelling messages were used, with the
candidate's only translation-payload change being its response schema. The
earlier actual native grammar and 285-probe evidence remains separately sealed.
The observed structural mechanism succeeded while the two complete meanings
failed. No wider corpus, fresh validation, summary or production-default change
was performed by this screen.

## Evidence and immutable history

- `independent-meaning-review/independent-output-review.json` preserves all six
  original sources, full raw final content, complete restored outputs and every
  criterion judgment, including successes inside the two failed cases.
- `independent-meaning-review/completed-output-protocol-audit.json` and its
  read-only audit script bind exact case/preflight/protection/request/resource
  hashes. Original source and criteria snapshots were bound before output.
- `root-meaning-review.json` records root's independent agreement.
- All complete per-case reports, preflights, protection records, authorization,
  native freeze, execution report and resource samples remain unchanged.
- `actual-private-logs` contains byte-identical full worker and daemon logs.
  `logs-privacy-and-copy.json` records the checked empty proxy fields and lack
  of detected credential values without reproducing environment values.

The original preparation `manifest.json` and all frozen input/source files are
unchanged. The historical execution record still says `semantic_quality:
unreviewed`; this separate completed decision rejects quality promotion. No
automatic flag or old grade was rewritten. The new
`completed-evidence-manifest.json` seals this complete execution and review.
