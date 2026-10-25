"""Run history: runs/<ts>/{metrics.json, output.csv, commit} plus a diff against the previous run."""

import json, tempfile, unittest
from pathlib import Path
from evaluation import history
from evaluation.tests.helpers import gold_rows, tmp_copy, mutate_step


class RunHistory(unittest.TestCase):
    def setUp(self):
        self.runs = Path(tempfile.mkdtemp()) / "runs"

    def test_record_writes_three_artifacts(self):
        out = tmp_copy()
        d = history.record(self.runs, out, {"proxy": 0.5}, commit="abc123", ts="20261025T010000Z")
        self.assertEqual(
            sorted(p.name for p in d.iterdir()), ["commit", "metrics.json", "output.csv"]
        )
        self.assertEqual(json.loads((d / "metrics.json").read_text())["proxy"], 0.5)
        self.assertEqual((d / "commit").read_text().strip(), "abc123")
        self.assertEqual((d / "output.csv").read_bytes(), out.read_bytes())

    def test_diff_against_previous_run_lists_status_and_step_changes(self):
        a = tmp_copy()
        rows = [list(r) for r in gold_rows()]
        rows[5][1] = "COMPLETE"  # case_05 status flips
        rows = mutate_step(rows, "case_06", 1, evidence_id="evidence_01")  # one step changes
        b = tmp_copy(rows=rows)
        history.record(self.runs, a, {}, commit="c1", ts="20261025T010000Z")
        d2 = history.record(self.runs, b, {}, commit="c2", ts="20261025T020000Z")
        prev = history.previous(self.runs, d2)
        self.assertEqual(prev.name, "20261025T010000Z")
        lines = history.diff(prev / "output.csv", d2 / "output.csv")
        self.assertIn("case_05: status INCOMPLETE -> COMPLETE", lines)
        self.assertTrue(any(l.startswith("case_06: - ") and "evidence_57" in l for l in lines))
        self.assertTrue(any(l.startswith("case_06: + ") and "evidence_01" in l for l in lines))
        self.assertEqual(
            len(
                [
                    l
                    for l in lines
                    if l.startswith("case_0") and not l.startswith(("case_05", "case_06"))
                ]
            ),
            0,
        )

    def test_first_run_has_no_previous(self):
        d = history.record(self.runs, tmp_copy(), {}, commit="c1", ts="20261025T010000Z")
        self.assertIsNone(history.previous(self.runs, d))
