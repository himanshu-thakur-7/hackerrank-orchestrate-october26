"""T13 custom cases: hand-written expectations over a dataset overlay; the real 518 rows must not
move."""

import copy
import unittest

from evaluation import custom
from evaluation.fixtures.custom_cases import CASES


class CustomCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = custom.run_cases(CASES)

    def test_at_least_eight_fixtures_covering_the_required_situations(self):
        titles = " | ".join(c["title"] for c in CASES)
        self.assertGreaterEqual(len(CASES), 8)
        for need in (
            "replica-only",
            "DELETION_PENDING",
            "contradicted",
            "legal hold",
            "uppercase historical",
            "post-cutoff",
            "redacted tombstone",
            "exposed tombstone",
            "marketing-only",
            "tied",
            "unproven",
        ):
            self.assertIn(need, titles)

    def test_every_case_matches_its_hand_written_row_and_log(self):
        bad = [(r.case_id, r.problems) for r in self.report.results if not r.ok]
        self.assertEqual(bad, [])

    def test_the_real_rows_are_untouched(self):
        self.assertEqual(self.report.real_rows_changed, [])

    def test_a_wrong_expectation_is_reported(self):
        cases = copy.deepcopy([c for c in CASES if c["id"] == "case_9006"])
        status, steps = cases[0]["expect"]["case_9006"]
        cases[0]["expect"]["case_9006"] = ("INCOMPLETE", steps)
        r = custom.run_cases(cases, check_real=False).results[0]
        self.assertFalse(r.ok)
        self.assertIn("status: expected INCOMPLETE, got COMPLETE", r.problems)


if __name__ == "__main__":
    unittest.main()
