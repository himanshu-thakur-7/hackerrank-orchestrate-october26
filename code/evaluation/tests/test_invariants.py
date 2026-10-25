"""T16 invariants over the real output: invariants.check(output, data_dir) -> {invariant id: [violations]}.
Each test breaks one property of a copy of the real output.csv and expects exactly that invariant to fire."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import invariants
from evaluation.overlay import run_pipeline

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "dataset"


class Invariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ghostaudit_inv_"))
        run_pipeline(DATA, cls.tmp / "out.csv")
        with open(cls.tmp / "out.csv", newline="", encoding="utf-8") as f:
            cls.rows = list(csv.DictReader(f))

    def write(self, rows):
        p = self.tmp / "mut.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        return p

    def mutate(self, pick, change):
        rows = [dict(r) for r in self.rows]
        r = next(r for r in rows if pick(r))
        steps = json.loads(r["steps_json"])
        change(r, steps)
        r["steps_json"] = json.dumps(steps, separators=(",", ":"))
        return invariants.check(self.write(rows), DATA)

    def fired(self, result):
        return sorted(k for k, v in result.items() if k != "rows" and v)

    def test_real_output_satisfies_every_invariant(self):
        self.assertEqual(self.fired(invariants.check(self.tmp / "out.csv", DATA)), [])

    def test_activity_citation(self):
        def ch(r, steps):
            next(s for s in steps if s["evidence_id"])["evidence_id"] = "activity_3600"
        self.assertIn("I4.no_claim_citation", self.fired(self.mutate(lambda r: r["deletion_status"] == "COMPLETE", ch)))

    def test_cited_file_must_name_the_resource(self):
        def ch(r, steps):
            s = next(s for s in steps if s["evidence_id"])
            s["resource_id"] = s["resource_id"].rsplit("_", 1)[0] + "_999999"
        self.assertIn("I7.citation_names_resource", self.fired(self.mutate(lambda r: r["deletion_status"] == "COMPLETE", ch)))

    def test_finding_without_remediation(self):
        def ch(r, steps):
            steps[:] = [s for s in steps if s["phase"] != "REMEDIATION"]
            for i, s in enumerate(steps, 1):
                s["step_no"] = i
        self.assertIn("I2.finding_has_plan", self.fired(self.mutate(
            lambda r: r["deletion_status"] == "INCOMPLETE" and '"FINDING"' in r["steps_json"], ch)))

    def test_status_consistent_with_steps(self):
        def ch(r, steps):
            r["deletion_status"] = "COMPLETE"
        self.assertIn("I6.status_matches_steps", self.fired(self.mutate(
            lambda r: r["deletion_status"] == "INCOMPLETE" and '"FINDING"' in r["steps_json"], ch)))


if __name__ == "__main__":
    unittest.main()
