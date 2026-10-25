"""T15 overlay helper: the whole pipeline over a modified temporary copy of dataset/ (dataset/ is never edited)."""

import hashlib
import unittest
from pathlib import Path

from evaluation import overlay

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "dataset"


def digest(d):
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(d)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


class OverlayHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = digest(DATA)

    def test_edits_land_in_the_copy_never_in_dataset(self):
        with overlay.Overlay(DATA) as ov:
            rows = ov.rows("deletion_requests.csv")
            rows[0]["email"] = rows[0]["email"].upper()
            ov.write_rows("deletion_requests.csv", rows)
            ov.add_evidence(
                "evidence_900", "evidence/logs/injected.log", "test", "2026-12-31T00:00:00Z", b"x\n"
            )
            ov.remove_evidence("evidence_01")
            self.assertEqual(ov.rows("deletion_requests.csv")[0]["email"], rows[0]["email"])
            self.assertIn("evidence_900", {r["file_id"] for r in ov.rows("evidence_files.csv")})
            self.assertNotIn("evidence_01", {r["file_id"] for r in ov.rows("evidence_files.csv")})
            self.assertTrue((ov.root / "evidence/logs/injected.log").exists())
            tmp = ov.root
        self.assertFalse(tmp.exists())  # the temp copy is removed on exit
        self.assertEqual(digest(DATA), self.before)

    def test_rows_keep_column_order_and_rewrite_round_trips(self):
        with overlay.Overlay(DATA) as ov:
            before = (ov.root / "user_identities.csv").read_bytes()
            ov.write_rows("user_identities.csv", ov.rows("user_identities.csv"))
            self.assertEqual((ov.root / "user_identities.csv").read_bytes(), before)

    def test_run_produces_rows_by_case(self):
        with overlay.Overlay(DATA) as ov:
            out = ov.run()
        self.assertEqual(len(out), 518)
        status, steps = out["case_34"]
        self.assertIn(status, ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"))
        self.assertIsInstance(steps, list)


class Relations(unittest.TestCase):
    def test_all_thirteen_relations_are_registered_in_order(self):
        from evaluation import metamorphic

        self.assertEqual(
            [r.__name__.split("_")[0] for r in metamorphic.RELATIONS],
            [f"m{i}" for i in range(1, 14)],
        )

    def test_shuffle_and_email_case_relations_hold_through_the_cli(self):
        from evaluation.tests.test_cli import run

        code, out = run("metamorphic", "--only", "M1,M3")
        self.assertEqual(code, 0, out)
        self.assertIn("METAMORPHIC: 2/2 relations hold", out)


class Diff(unittest.TestCase):
    def test_diff_names_changed_cases(self):
        a = {"case_1": ("COMPLETE", [{"evidence_id": "e1"}]), "case_2": ("INCOMPLETE", [])}
        b = {"case_1": ("COMPLETE", [{"evidence_id": "e2"}]), "case_2": ("INCOMPLETE", [])}
        self.assertEqual(overlay.changed(a, b), ["case_1"])
        self.assertEqual(overlay.changed(a, a), [])


if __name__ == "__main__":
    unittest.main()
