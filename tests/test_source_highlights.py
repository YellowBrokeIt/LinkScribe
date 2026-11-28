"""Source fidelity, context retention and bounded deterministic excerpt selection."""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest

import source_highlights as highlights


def transcript(texts, *, speakers=False):
    result = []
    for index, text in enumerate(texts):
        segment = {"start": index * 3.25, "end": index * 3.25 + 3.0, "text": text}
        if speakers:
            segment["speaker"] = f"Speaker {index % 2 + 1}"
        result.append(segment)
    return result


class SourceHighlightsTests(unittest.TestCase):
    def assert_bound(self, result, source):
        highlights.validate_highlights(result, source)
        self.assertEqual(result["source_segment_count"], len(source))
        previous = -1
        selected = []
        for excerpt in result["excerpts"]:
            indices = excerpt["segment_indices"]
            self.assertGreater(indices[0], previous)
            self.assertEqual(indices, list(range(indices[0], indices[-1] + 1)))
            self.assertEqual(excerpt["text"], "\n".join(source[index]["text"] for index in indices))
            self.assertEqual(excerpt["start"], source[indices[0]]["start"])
            self.assertEqual(excerpt["end"], max(source[index]["end"] for index in indices))
            previous = indices[-1]
            selected.extend(indices)
        self.assertEqual(result["selected_segment_count"], len(selected))
        self.assertLessEqual(len(result["excerpts"]), highlights.MAX_EXCERPTS)
        self.assertLessEqual(sum(len(item["text"].encode("utf-8")) for item in result["excerpts"]),
                             highlights.MAX_EXCERPT_BYTES)
        self.assertIn("not a complete summary", result["warnings"][0])
        return selected

    def test_short_source_keeps_full_wording_context_and_authentic_times(self):
        source = transcript([
            '  "We can publish the recording," the host said.',
            "Correction: we may publish only the slides, not the recording.",
            "This permission applies only after Maria gives written consent.  ",
        ], speakers=True)
        source[0]["end"] = 10.5  # Overlap is source data, not a reason to invent a duration.
        original = copy.deepcopy(source)
        result = highlights.select_highlights(source, source_language="en")
        self.assertEqual(self.assert_bound(result, source), [0, 1, 2])
        self.assertEqual(result["excerpts"][0]["end"], 10.5)
        self.assertEqual(source, original)
        self.assertNotIn("summary", result)
        self.assertNotIn("title", result["excerpts"][0])

    def test_greek_accents_names_numbers_and_conditions_are_not_rewritten(self):
        source = transcript([
            "Η Μαρία συμφώνησε να επιστρέψει 12,50 ευρώ στον Νίκο.",
            "Όμως δεν επιτρέπεται να δημοσιευτεί η ηχογράφηση.",
            "Μόνο αν δοθεί γραπτή άδεια μπορούν να δημοσιευτούν οι διαφάνειες.",
        ])
        result = highlights.select_highlights(source, source_language="el-GR")
        self.assertEqual(self.assert_bound(result, source), [0, 1, 2])
        self.assertIn("Μαρία", result["excerpts"][0]["text"])
        self.assertIn("12,50", result["excerpts"][0]["text"])

    def test_long_source_prioritizes_local_correction_with_its_preceding_claim(self):
        source = transcript([
            f"Archive shelf {index} contains routine correspondence about deliveries and local meeting logistics."
            for index in range(120)
        ])
        source[72]["text"] = "The published draft budget assigned 900 euros to the event."
        source[73]["text"] = "Correction: the approved budget is only 90 euros, not 900 euros."
        source[74]["text"] = "This amount may be spent only if the committee gives written permission."
        result = highlights.select_highlights(source)
        selected = self.assert_bound(result, source)
        self.assertTrue({72, 73, 74}.issubset(selected))
        self.assertLess(len(selected), len(source))

    def test_long_greek_negation_and_condition_remain_in_selected_context(self):
        source = transcript([
            f"Το αρχείο {index} περιέχει συνηθισμένη αλληλογραφία για παραδόσεις και διοικητικές συναντήσεις."
            for index in range(100)
        ])
        source[55]["text"] = "Ο Νίκος πρότεινε να δημοσιευτεί το βίντεο την Παρασκευή."
        source[56]["text"] = "Διόρθωση: δεν εγκρίθηκε η δημοσίευση του βίντεο."
        source[57]["text"] = "Μόνο αν συμφωνήσει γραπτώς η Μαρία θα δημοσιευτούν οι διαφάνειες."
        result = highlights.select_highlights(source, source_language="el")
        self.assertTrue({55, 56, 57}.issubset(self.assert_bound(result, source)))

    def test_deterministic_diverse_selection_on_long_repetitive_input(self):
        source = transcript([
            f"Project {index} reviewed the delivery schedule, staffing, documentation and equipment storage."
            for index in range(1800)
        ])
        for index, text in ((120, "The team approved a budget of 15 euros and a Monday delivery deadline."),
                            (900, "The team agreed to keep all recordings private unless written consent is received."),
                            (1680, "The manager cancelled Friday delivery and assigned delivery to Tuesday instead.")):
            source[index]["text"] = text
        result = highlights.select_highlights(source)
        self.assertEqual(result, highlights.select_highlights(source))
        selected = self.assert_bound(result, source)
        self.assertTrue({120, 900, 1680}.issubset(selected))
        self.assertLess(len(selected), 100)
        self.assertLess(len(json.dumps(result).encode("utf-8")), 150_000)

    def test_blank_and_explicit_nonspeech_markers_do_not_produce_highlights(self):
        for source in ([], transcript(["", " \n", "...", "[Music]", "[Σιωπή]"])):
            with self.subTest(source=source):
                result = highlights.select_highlights(source)
                self.assertEqual(self.assert_bound(result, source), [])
                self.assertIn(highlights.EMPTY_NOTICE, result["warnings"])

    def test_selection_is_stable_between_python_hash_seeds(self):
        source = transcript([
            f"Project {index % 7} considered route {index} and reviewed delivery, staffing and archive decisions."
            for index in range(160)
        ])
        command = [sys.executable, "-c", "import json,sys; from source_highlights import select_highlights; "
                   "print(json.dumps(select_highlights(json.load(sys.stdin)), sort_keys=True))"]
        responses = []
        for seed in ("1", "53"):
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = seed
            responses.append(subprocess.check_output(command, input=json.dumps(source), text=True,
                                                       cwd=Path(__file__).resolve().parents[1],
                                                       env=environment, timeout=15))
        self.assertEqual(responses[0], responses[1])

    def test_an_indivisible_oversized_segment_is_not_silently_truncated(self):
        source = transcript(["Keep the original legal condition intact without truncation. " * 1000])
        result = highlights.select_highlights(source)
        self.assertEqual(self.assert_bound(result, source), [])
        self.assertIn(highlights.LIMIT_NOTICE, result["warnings"])

    def test_invalid_source_rejected_before_selection(self):
        invalid = [None, {}, [{"start": True, "end": 1, "text": "text"}],
                   [{"start": 0, "end": math.inf, "text": "text"}],
                   [{"start": 2, "end": 1, "text": "text"}],
                   [{"start": 0, "end": 1, "text": "\ud800"}],
                   [{"start": 0, "end": 1, "text": "text", "speaker": None}],
                   [{"start": 2, "end": 3, "text": "First."},
                    {"start": 1, "end": 2, "text": "Second."}]]
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(highlights.SourceHighlightsError):
                highlights.select_highlights(source)

    def test_source_bound_rejection_of_post_selection_edits(self):
        source = transcript(["The amount is 90 euros.", "It is not 900 euros."], speakers=True)
        result = highlights.select_highlights(source)
        for key, replacement in (("text", "The amount is 900 euros."), ("start", 0.5),
                                 ("end", 3.1), ("speaker", "Different speaker")):
            with self.subTest(key=key):
                edited = copy.deepcopy(source)
                edited[0][key] = replacement
                with self.assertRaises(highlights.SourceHighlightsError):
                    highlights.validate_highlights(result, edited)

    def test_saved_excerpts_cannot_invent_or_rearrange_source_content(self):
        source = transcript(["Alpha must stay private.", "Beta is public only after consent."])
        original = highlights.select_highlights(source)
        mutations = [
            lambda value: value["excerpts"][0].update(text="Alpha is public."),
            lambda value: value["excerpts"][0].update(start=True),
            lambda value: value["excerpts"][0].update(end=999),
            lambda value: value["excerpts"][0].update(segment_indices=[1, 0]),
            lambda value: value["excerpts"][0].update(segment_indices=[False, 1]),
            lambda value: value["excerpts"][0].update(title="Invented heading"),
            lambda value: value.update(selected_segment_count=True),
            lambda value: value.update(version=True),
            lambda value: value["warnings"].append("This is a complete and accurate summary."),
            lambda value: value["excerpts"].append(copy.deepcopy(value["excerpts"][0])),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                value = copy.deepcopy(original)
                mutate(value)
                with self.assertRaises(highlights.SourceHighlightsError):
                    highlights.validate_highlights(value, source)
