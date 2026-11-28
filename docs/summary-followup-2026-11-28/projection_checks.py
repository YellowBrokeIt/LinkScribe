"""Non-model regressions for the bounded offline projection experiment."""
import copy
import unittest

from canonical_points import normalize, project


def value(text):
    return {"summary": text, "key_points": ["Independent original point."],
            "chapters": [{"start": 0.5, "title": "Planning"}]}


class ProjectionChecks(unittest.TestCase):
    def test_decimals_and_abbreviated_title_remain_complete(self):
        original = value("Dr. Beatrice keeps the approved €84.75 budget. It is not €847.50. No purchase has been paid for.")
        observed = project(original)
        self.assertIn("Dr. Beatrice keeps the approved €84.75 budget.", observed["key_points"])
        self.assertIn("It is not €847.50.", observed["key_points"])
        self.assertIn("No purchase has been paid for.", observed["key_points"])

    def test_greek_room_initials_keep_their_context(self):
        text = "Η πρώτη συνάντηση θα γίνει στην αίθουσα Β. Η παλιά αφίσα έγραφε αίθουσα Α. Δεν ακυρώθηκε η συνάντηση."
        observed = project(value(text))
        self.assertEqual(normalize(" ".join(observed["key_points"])), normalize(text))
        self.assertTrue(all(not point.startswith(("Β.", "Α.")) for point in observed["key_points"]))

    def test_closing_quote_stays_with_quoted_sentence(self):
        observed = project(value("The trainer read 'Everyone is approved.' This was a misleading example. Two requests remain pending."))
        self.assertEqual(observed["key_points"][0], "The trainer read 'Everyone is approved.'")
        self.assertIn("This was a misleading example.", observed["key_points"])

    def test_more_than_eight_sentences_preserve_late_condition(self):
        text = " ".join([f"Request {i} remains pending." for i in range(12)] +
                        ["No request is approved until written confirmation arrives."])
        observed = project(value(text))
        self.assertLessEqual(len(observed["key_points"]), 8)
        self.assertEqual(normalize(" ".join(observed["key_points"])), normalize(text))
        self.assertTrue(any("No request is approved until written confirmation arrives." in point
                            for point in observed["key_points"]))

    def test_oversized_indivisible_span_is_rejected_without_editing_input(self):
        original = value("Long " + "unpunctuated " * 100 + "statement.")
        before = copy.deepcopy(original)
        with self.assertRaisesRegex(ValueError, "no text was truncated"):
            project(original)
        self.assertEqual(original, before)

    def test_original_paragraph_and_chapters_are_unchanged(self):
        original = value("Two actions remain pending. They require written confirmation.")
        before = copy.deepcopy(original)
        observed = project(original)
        self.assertEqual(original, before)
        self.assertEqual(observed["summary"], original["summary"])
        self.assertEqual(observed["chapters"], original["chapters"])


if __name__ == "__main__":
    unittest.main()
