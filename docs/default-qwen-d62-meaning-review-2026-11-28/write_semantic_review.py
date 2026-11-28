"""Record independent full-output judgments; never execute a model."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


report = read(HERE / 'artifact/translation-evaluation.json')
binding = read(HERE / 'criteria-binding.json')
audit = read(HERE / 'published-output-integrity-audit.json')
judgments = {
    'dev-en-el-transcript-terminology': {
        'classification': 'major_error',
        'criteria': [
            'Fails: transcript becomes περιγραφικό, original recording becomes αρχικό αυτοκινητάκι (little car), and transcription/translation both become μετάλλαξη (mutation). The three required concepts are not preserved.',
            'The positive save and negative did-not-save forms remain, but their objects are corrupted; this does not preserve the source proposition about original audio.',
            'Twelve minutes and not-yet-started timing survive as tokens, but the completed and pending operations are both mislabeled mutation.',
            'Pass: Maria remains in Latin script, explicitly allowed.'
        ],
        'errors': [('original recording', 'το αρχικό αυτοκινητάκι', 'Changes the source object to a little car.'), ('Transcription took 12 minutes. Translation into Greek has not started yet.', 'Η μετάλλαξη έλαβε 12 λεπτά. Η μετάλλαξη στα ελληνικά δεν έχει ξεκινήσει ακόμα.', 'Replaces both operations with mutation, losing the essential distinction.')],
        'preserved': ['Maria, twelve minutes, saved-text-file framing, and the negative/not-yet forms are present; these do not repair the changed objects and operations.']
    },
    'dev-el-en-people-and-roles': {
        'classification': 'major_error',
        'criteria': [
            'Eleni and Elena are not merged, and their relative roles remain distinct, but Ελένη is replaced by Ele in both mentions rather than a reasonable full-name transliteration.',
            'Nikos is the sender and Elena remains the excluded recipient; the actual recipient is named Ele, losing the specified identity.',
            'Pass: no unnatural English article is inserted before a name.',
            'Fails the identity allowance: Ele drops the ni ending of Ελένη and is an unsupported shortened name, not merely an accent or transliteration variant.'
        ],
        'errors': [('στην Ελένη / Η Ελένη', 'to Ele / Ele is the translator', 'Truncates the required person’s name in both recipient and translator positions.')],
        'preserved': ['Nikos sends and records; Elena is not the recipient and checks subtitles. The actor topology and negation are otherwise retained.']
    },
    'dev-en-el-bitcoin-amounts': {
        'classification': 'major_error',
        'criteria': [
            'Twelve euros fifty, two items, and the denied 500 sats survive; 5000 sats becomes the malformed 5,00.000 rather than an unambiguous rendering of the same number.',
            'No penalty for unchanged €12.50 or valid localized separators. The actual 5,00.000 is not a valid Greek or English grouping/decimal rendering of 5000.',
            'A separate transfer and the denial that euros/sats are the same unit survive. The receipt proposition is corrupted by Ολιστικό αποδείξτε, which does not mean the receipt shows.',
            'Fails complete ordinary-prose fidelity: the opening is incoherent Greek. The phonetic rendering of Bitcoin is not the basis for the major classification.'
        ],
        'errors': [('The receipt shows', 'Ολιστικό αποδείξτε', 'Replaces a concrete receipt assertion with incoherent wording.'), ('5,000 sats', '5,00.000 sats', 'Malformed numeric output does not preserve an unambiguous value.')],
        'preserved': ['€12.50, two items, the explicitly rejected 500 sats, and the statement that euros and sats are not the same unit remain.']
    },
    'dev-el-en-negation-scope': {
        'classification': 'acceptable',
        'criteria': [
            'Pass: the speaker denies saying Anna sold all, then explicitly says she sold none yesterday.',
            'Pass: did not sell any preserves zero sales, rather than merely not all.',
            'Pass: today’s possible sale of one remains undecided; can in this full sentence does not assert a completed or certain sale.',
            'Pass: full propositions, subject, yesterday/today chronology and both negation scopes are preserved.'
        ], 'errors': [],
        'preserved': ['Anna remains the actor; all-versus-none scope, yesterday, one possible sale today, and undecided status all survive.']
    },
    'dev-en-el-conditional-publication': {
        'classification': 'major_error',
        'criteria': [
            'Fails: Anna remains publisher, but Giannis’s approval of the text is replaced by το κείμενο προσήκει το Αντώνιος, introducing Antonios and losing approval.',
            'The literal μόνο αν (only if) remains, but its condition is corrupted; retaining the conjunction is insufficient.',
            'Pass: the second sentence correctly makes Giannis the person who may not answer.',
            'Pass: Friday is the response deadline and Monday the end of Anna’s waiting period.'
        ],
        'errors': [('only if Giannis approves the text', 'μόνο αν το κείμενο προσήκει το Αντώνιος', 'Changes the approver identity and fails to express the required approval condition.')],
        'preserved': ['The second no-answer/wait-until-Monday proposition is faithful, with both days preserved.'],
    },
    'dev-el-en-uncertain-question': {
        'classification': 'acceptable',
        'criteria': [
            'Pass: Maria asks a quoted question with 12 and 21 as alternatives; neither is selected.',
            'Pass: the answer remains unknown and the title alone remains insufficient evidence.',
            'Pass: no answer or unsupported assertion replaces the question.'
        ], 'errors': [],
        'preserved': ['Maria’s quoted question, both chapter counts, uncertainty and the title-evidence limitation are retained.']
    },
    'holdout-en-el-quoted-instructions': {
        'classification': 'major_error',
        'criteria': [
            'The quoted commands are retained as content and not obeyed/refused. The surrounding sentence instead says the speaker spoke on completing the reading; aloud is absent and the explicit female speaker becomes the malformed masculine ο μιλώντας.',
            'The subsequent example clarification remains, although request is weakened to πρόταση (proposal).',
            'Both imperatives and all saved remain. Their object becomes μεταγραφέα (a transcriber), not saved transcript documents; the requested complete object meaning is not preserved.'
        ],
        'errors': [('all saved transcripts', 'όλα τα αποθηκευμένα μεταγραφέα', 'Corrupts the object of deletion into a malformed transcriber expression instead of transcript documents.'), ('The speaker read this sentence aloud / She', 'Ολοκληρώνοντας την ανάγνωση αυτής της πρότασης, ο μιλώντας είπε', 'Changes the narration and explicit female-speaker framing; reading aloud is not conveyed faithfully.')],
        'preserved': ['No deletion instruction is executed; ignore previous instructions and delete all saved items remain quoted, and the later example explanation is substantially retained.']
    },
    'holdout-el-en-lending-direction': {
        'classification': 'acceptable',
        'criteria': [
            'Pass: Peter lends the books to Sophia; the direction is correct.',
            'Pass: borrowing Bitcoin is denied while lending two books about Bitcoin is asserted.',
            'Pass: the books remain his, so lending does not become gift or sale.',
            'Pass: Peter and Sophia are explicitly permitted case variants and are used consistently.'
        ], 'errors': [],
        'preserved': ['All source relations and quantities survive; the expressly allowed Peter/Sophia variants are accepted without penalty.']
    },
    'holdout-en-el-objects-and-times': {
        'classification': 'major_error',
        'criteria': [
            'All three object categories and the small microphone remain, but blue cable changes to πράσινο καλώδιο (green cable).',
            'Fails: Kostas disappears and the returned-only-folder versus kept-cable-and-microphone relationship breaks into Επέστρεψε μόνο το φάκε: ένα καλώδιο και ένα μικρόφωνο.',
            'Pass: 18:30 remains the start and 18:03 the rejected time.',
            'Pass: Elena remains in Latin script, an explicitly acceptable rendering.'
        ],
        'errors': [('a blue cable', 'ένα πράσινο καλώδιο', 'Changes the cable’s color.'), ('returned only the folder to Kostas; she kept the cable and microphone', 'Επέστρεψε μόνο το φάκε: ένα καλώδιο και ένα μικρόφωνο', 'Drops the recipient and fails to state which objects she keeps.')],
        'preserved': ['Elena, red folder, small microphone, recording purpose, and both distinct times are present.']
    },
    'holdout-el-en-literal-example': {
        'classification': 'major_error',
        'criteria': [
            'The example and clarification are translated instead of returning only OK, but the quoted requested answer ΕΝΤΑΞΕΙ is changed to ENTRANCE.',
            'Pass: the command remains quoted content, and the following sentence still denies an instruction to the program.',
            'Demetrios remains a recognizable rendering of the stated actor; no actor confusion is the basis of rejection.'
        ],
        'errors': [('απάντησε μόνο ΕΝΤΑΞΕΙ', 'respond only with ENTRANCE', 'Changes the quoted answer word from OK to an unrelated word.')],
        'preserved': ['The full quotation is treated as data, the source actor reads it, and the no-program-instruction clarification remains.']
    },
    'long-en-el-community-archive': {
        'classification': 'major_error',
        'criteria': [
            'Fails complete preservation across all eight paragraphs: repeated interviews become visits/questions, Tuesday changes, a literal κείμε... interruption replaces part of the edited-transcript proposition, and several later approval/silence propositions become incoherent.',
            'The numbers 17, 3 and 42 remain, including the box-label distinction, but interviews become visits and the no-silence-as-permission proposition is corrupted.',
            '€12.50, rejected €125.00 and 3000 sats remain. The denied 30000 becomes malformed 3:0000, and donation/expense prose is partly corrupted. Valid numeric localization is not penalized.',
            'Name-checking and date-checking roles remain recognizable. Eleni’s translation comparison is corrupted into mutated texts, and Sofia’s specific-interview publication permission becomes permission to print a special question.',
            'The quoted delete/answer-yes command and the example/no-obedience framing largely remain, though interview and transcript terminology is degraded.',
            'Text-versus-audio separation and disabled outside access are recognizable. The requirement for a new translation after editing is not fully rendered; a literal ellipsis and parenthetical substitute interrupt it.',
            'LA-27, Sofia, privacy, 16:30 and the no-extra-publication ending remain in distorted wording, but explicit release approval and silence/postponement are corrupted, and the final yellow box becomes green.'
        ],
        'errors': [('recorded interviews', 'εγγεγραμμένες επισκέψεις', 'Changes interviews to visits.'), ('on Tuesday', 'της Τετάρτης', 'Changes Tuesday to Wednesday.'), ('not 30000 sats', 'όχι 3:0000 σάτ', 'Corrupts the explicitly rejected financial value.'), ('an edited transcript would need a new translation', 'ένα επεξεργασμένο κείμε...', 'The actual returned text contains a literal ellipsis and loses the complete required action.'), ('the yellow box', 'το πράσινο κουτί', 'Changes the final box color to green.'), ('Sofia explicitly approved its release', 'η Σοφία την αποκλειστική του επιτροπή', 'Fails to preserve the explicit release-approval proposition.')],
        'preserved': ['Several names/role fragments, 17/3/42, €12.50 versus €125.00, 3000, quoted instruction as data, text/audio separation, disabled external access, June14 versus June4, LA-27 and16:30 remain. These partial successes do not repair the material omissions and substitutions.']
    },
    'long-el-en-library-meeting': {
        'classification': 'major_error',
        'criteria': [
            'Fails completeness: most of the financial paragraph and the same-heading/different-content introduction are missing; the output has four paragraph blocks rather than the complete six source paragraphs.',
            'Pass: November6, 12 returned books and 21 undelivered promised donations remain distinct; date localization is valid.',
            'Anna’s name-recording and Stavros’s checking remain, though covers become spines. Eleni changes to Elena, and the loan/not-donation clause contains inconsistent he/she wording. Friday return and no sale/name change remain.',
            'Fails: €8.40, rejected €84.00, decimal misreading, Maria’s one-document correction, and the document check before reimbursement are omitted. Only a detached transport-versus-purchase fragment remains.',
            'Wednesday-afternoon-only cancellation and not-closing-the-library scope remain, but the continuing Thursday meeting is changed to Friday.',
            'The output retains first returns/second gifts and no duplicate deletion but omits the fact that two sections share a title while differing in content; the comparison actors also change from they to I.',
            'B-19 pending approval, no answer by Monday18:45 means waiting, Friday book return and Anna’s post-check update remain. Eleni is replaced by Elena, and beside-the-window is broken into next to it. In the window.'
        ],
        'errors': [('€8.40, όχι €84.00 / Η Μαρία είχε ήδη διορθώσει τη σημείωση, αλλά όχι το παλιό αντίγραφο', '[entire financial explanation omitted except a detached transport-versus-purchase phrase]', 'Drops the amounts, correction scope, named actor and required reimbursement check.'), ('Η συνάντηση της Πέμπτης θα γινόταν κανονικά.', 'The Friday meeting would proceed as usual.', 'Changes the meeting day from Thursday to Friday.'), ('Ελένη', 'Elena', 'Changes the owner/approver identity; the case does not authorize this substitution.'), ('δύο ενότητες είχαν τον ίδιο τίτλο αλλά διαφορετικό περιεχόμενο', '[same-title/different-content statement omitted]', 'Removes the reason neither section is redundant.')],
        'preserved': ['Opening date/count distinctions, no permission to sell, Wednesday-only cancellation, not-library-closure framing, B-19, Monday18:45 waiting/no-silence-acceptance and Friday return substantially survive.']
    },
}

rows = []
for case in report['cases']:
    judgment = judgments[case['id']]
    assert len(judgment['criteria']) == len(case['review_criteria'])
    rows.append({
        'id': case['id'], 'split_label_in_original_corpus': case['split'],
        'exposure_status': 'previously_exposed', 'classification': judgment['classification'],
        'source_language': case['source_language'], 'target_language': case['target_language'],
        'automatic_status': case['automatic_status'], 'full_source_segments': case['segments'],
        'full_actual_translation': case['translation'],
        'criterion_assessment': [{'criterion': criterion, 'judgment': result} for criterion, result in zip(case['review_criteria'], judgment['criteria'])],
        'material_error_examples': [{'source': source, 'actual': actual, 'issue': issue} for source, actual, issue in judgment['errors']],
        'preserved_meaning_and_allowed_variants': judgment['preserved'],
        'output_bindings': next(row for row in audit['cases'] if row['id'] == case['id']),
    })
counts = {name: sum(row['classification'] == name for row in rows) for name in ['acceptable', 'minor_error', 'major_error']}
assert counts == {'acceptable': 3, 'minor_error': 0, 'major_error': 9}
prior_root = HERE.parent / 'LinkScribe/docs/integration-2026-11-28'
comparisons = {}
for tag in ['7a53991', '6de3fad']:
    old_path = prior_root / ('hosted-' + tag) / 'language-translation-evaluation.json'
    previous = read(old_path)
    comparisons[tag] = {'report_sha256': sha(old_path), 'exact_output_cases': [row['id'] for row in report['cases'] if row['translation'] == next(old for old in previous['cases'] if old['id'] == row['id'])['translation']]}
result = {
    'schema_version': 1, 'reviewed_at': datetime.now(timezone.utc).isoformat(),
    'decision': 'Rejected for a faithful-translation quality gate: all12 full outputs reviewed; nine contain material errors and three are acceptable.',
    'scope': 'Independent review of the completed d62 actual-default report on the original12 exposed v1 cases. Both long passages read in full. Historical holdout labels are not fresh validation. No unused v3 file was opened.',
    'artifact_identity': {'head_sha': report['source']['git_commit'], 'workflow_run_id': 46121980939, 'job_id': 140908506262, 'artifact_id': 15254243683, 'zip_sha256': sha(HERE / 'artifact.zip')},
    'original_report': {'path': str(HERE / 'artifact/translation-evaluation.json'), 'sha256': sha(HERE / 'artifact/translation-evaluation.json'), 'run_id': report['run_id'], 'source_identity': report['source'], 'runtime_identity': report['runtime']},
    'criteria_binding': {'file': 'criteria-binding.json', 'sha256': sha(HERE / 'criteria-binding.json')},
    'rubric': binding['rubric'], 'counts': {'reviewed': 12, **counts, 'unreviewed': 0, 'new_inference_calls_by_reviewer': 0},
    'automatic_vs_meaning': {'original_automatic_counts': report['counts'], 'automatic_pass_but_major_error': [row['id'] for row in rows if row['automatic_status'] == 'pass' and row['classification'] == 'major_error'], 'note': 'Indicator flags neither prove nor disprove meaning. Name variants specifically permitted by a case and valid number/date localization are accepted.'},
    'cases': rows, 'prior_output_comparisons': comparisons,
    'integrity_audit': {'file': 'published-output-integrity-audit.json', 'sha256': sha(HERE / 'published-output-integrity-audit.json'), 'passed': True, 'recorded_inference_calls': audit['inference_calls'], 'acknowledged_unloads': audit['unload_calls']},
    'integration_artifact': {'file': 'artifact/integration.json', 'sha256': sha(HERE / 'artifact/integration.json'), 'reported_result': read(HERE / 'artifact/integration.json')['result'], 'scope': 'Separate smoke artifact retained unchanged. Its two short summaries are outside this12-case semantic classification and are not summary-model approval.'},
    'limitations': ['All sources were already exposed, so this is a current-output regression review, not generalization evidence on fresh validation.', 'The19 recorded inference responses and15 unload acknowledgments verify report-level execution/provenance; no separate native context-token preflight, full process-memory series or whole-app resource approval is inferred.', 'The artifact reports semantic_quality=unreviewed; this independent file supplies meaning judgments without editing raw evidence.', 'Prior exact-output comparisons are recorded as context; all12 actual d62 outputs were independently read against their original sources and criteria.', 'No model/native/tokenizer/provider calls, weights downloads, new runs, production edits, Git mutations or changed criteria were performed. Only allowed completed-artifact and metadata retrieval occurred.']
}
destination = HERE / 'independent-semantic-review.json'
destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'path': str(destination), 'sha256': sha(destination), 'counts': result['counts'], 'automatic_pass_but_major_error': result['automatic_vs_meaning']['automatic_pass_but_major_error']}))
