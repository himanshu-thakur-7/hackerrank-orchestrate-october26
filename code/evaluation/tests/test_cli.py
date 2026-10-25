"""CLI behaviour of code/evaluation/main.py (run as a subprocess, the way users and CI call it)."""
import os, subprocess, sys, tempfile, unittest
from pathlib import Path
from evaluation.tests.helpers import ROOT, GOLD, SAMPLE_REQ, gold_rows, tmp_copy, mutate_step

MAIN = ROOT / "code" / "evaluation" / "main.py"


def run(*args, env_extra=None):
    env = dict(os.environ, **(env_extra or {}))
    p = subprocess.run([sys.executable, str(MAIN), *args], capture_output=True, text=True, cwd=ROOT, env=env)
    return p.returncode, p.stdout + p.stderr


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {"GHOSTAUDIT_RUNS_DIR": str(self.tmp / "runs"), "GHOSTAUDIT_REVEAL_LOG": str(self.tmp / "reveals.md")}

    def test_contract_ok_on_gold(self):
        code, out = run("contract", "--file", str(GOLD), "--requests", str(SAMPLE_REQ))
        self.assertEqual(code, 0, out)
        self.assertIn("CONTRACT OK (sample_output.csv, 32 rows)", out)

    def test_contract_fails_nonzero_with_message(self):
        bad = tmp_copy(rows=mutate_step(gold_rows(), "case_05", 2, evidence_id=None))
        code, out = run("contract", "--file", str(bad), "--requests", str(SAMPLE_REQ))
        self.assertEqual(code, 1)
        self.assertIn("CONTRACT FAILED", out)
        self.assertIn("case_05 step 2", out)

    def test_score_hides_holdout_detail_unless_revealed_and_logs_reveals(self):
        # contract-valid errors: a wrong verified resource in dev case_01 and in holdout case_26
        rows = mutate_step(gold_rows(), "case_01", 1, resource_id="account_999")
        rows = mutate_step(rows, "case_26", 1, resource_id="account_998")
        pred = tmp_copy(rows=rows)
        code, out = run("score", "--pred", str(pred), env_extra=self.env)
        self.assertIn("DEV", out); self.assertIn("HOLDOUT (aggregate only)", out)
        self.assertIn("case_01: missing", out)                           # dev case detail shown
        self.assertNotIn("case_26:", out)                                # holdout case detail hidden
        self.assertFalse((self.tmp / "reveals.md").exists())
        code, out = run("score", "--pred", str(pred), "--reveal-holdout", env_extra=self.env)
        self.assertIn("case_26: missing", out)
        self.assertIn("--reveal-holdout", (self.tmp / "reveals.md").read_text())

    def test_score_records_history_and_diff_gate_blocks_dev_regression(self):
        code, out = run("score", "--pred", str(GOLD), env_extra=self.env)
        self.assertEqual(code, 0, out)
        rows = mutate_step(gold_rows(), "case_01", 1, resource_id="account_999")   # dev case_01 regresses
        code, out = run("score", "--pred", str(tmp_copy(rows=rows)), env_extra=self.env)
        self.assertEqual(code, 2, out)
        self.assertIn("DIFF GATE", out)
        self.assertIn("case_01: - VERIFICATION account_service account_001", out)
        self.assertEqual(len(list((self.tmp / "runs").iterdir())), 2)

    def test_selftest_passes(self):
        code, out = run("selftest", env_extra=self.env)
        self.assertEqual(code, 0, out)
        self.assertIn("SELFTEST OK", out)
