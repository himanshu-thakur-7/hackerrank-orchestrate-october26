"""CLI behaviour of code/evaluation/main.py (run as a subprocess, the way users and CI call it)."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.tests.helpers import GOLD, ROOT, SAMPLE_REQ, gold_rows, mutate_step, tmp_copy

MAIN = ROOT / "code" / "evaluation" / "main.py"


def run(*args, env_extra=None):
    env = dict(os.environ, **(env_extra or {}))
    p = subprocess.run(
        [sys.executable, str(MAIN), *args], capture_output=True, text=True, cwd=ROOT, env=env
    )
    return p.returncode, p.stdout + p.stderr


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {
            "GHOSTAUDIT_RUNS_DIR": str(self.tmp / "runs"),
            "GHOSTAUDIT_REVEAL_LOG": str(self.tmp / "reveals.md"),
        }

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
        self.assertIn("DEV", out)
        self.assertIn("HOLDOUT (aggregate only)", out)
        self.assertIn("case_01: missing", out)  # dev case detail shown
        self.assertNotIn("case_26:", out)  # holdout case detail hidden
        self.assertFalse((self.tmp / "reveals.md").exists())
        code, out = run("score", "--pred", str(pred), "--reveal-holdout", env_extra=self.env)
        self.assertIn("case_26: missing", out)
        self.assertIn("--reveal-holdout", (self.tmp / "reveals.md").read_text())

    def test_score_records_history_and_diff_gate_blocks_dev_regression(self):
        code, out = run("score", "--pred", str(GOLD), env_extra=self.env)
        self.assertEqual(code, 0, out)
        rows = mutate_step(
            gold_rows(), "case_01", 1, resource_id="account_999"
        )  # dev case_01 regresses
        code, out = run("score", "--pred", str(tmp_copy(rows=rows)), env_extra=self.env)
        self.assertEqual(code, 2, out)
        self.assertIn("DIFF GATE", out)
        self.assertIn("case_01: - VERIFICATION account_service account_001", out)
        self.assertEqual(len(list((self.tmp / "runs" / "score").iterdir())), 2)

    def test_selftest_passes(self):
        code, out = run("selftest", env_extra=self.env)
        self.assertEqual(code, 0, out)
        self.assertIn("SELFTEST OK", out)


BLOCK_PANDAS = (
    "import sys, runpy; sys.modules['pandas'] = None; sys.argv = ['main.py', 'selftest']; "
    "runpy.run_path(%r, run_name='__main__')"
)


class SelftestTargetsSpecificChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = dict(os.environ, GHOSTAUDIT_RUNS_DIR=str(self.tmp / "runs"))

    def _assert_specific(self, out):
        self.assertIn("bad quoting    -> FAILS on L0.csv", out)
        self.assertIn("null evidence  -> FAILS on L0.evidence", out)
        self.assertIn("wrong order    -> FAILS on L0.order", out)
        self.assertIn("SELFTEST OK", out)

    def test_selftest_with_pandas_available(self):
        p = subprocess.run(
            [sys.executable, str(MAIN), "selftest"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=self.env,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self._assert_specific(p.stdout)

    def test_selftest_with_pandas_import_blocked(self):
        p = subprocess.run(
            [sys.executable, "-c", BLOCK_PANDAS % str(MAIN)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=self.env,
        )
        out = p.stdout + p.stderr
        self.assertEqual(p.returncode, 0, out)
        self.assertIn("WARNING L0.pandas SKIPPED", out)
        self._assert_specific(out)


class BaselineFindings(unittest.TestCase):
    """Bugs found when the first real (trivial) prediction file was scored."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {"GHOSTAUDIT_RUNS_DIR": str(self.tmp / "runs")}

    def test_determinism_subcommand_accepts_cmd(self):
        out = self.tmp / "o.csv"
        cmd = f"{sys.executable} -c \"open('{out}','w').write('x')\""
        code, text = run("determinism", "--cmd", cmd, "--file", str(out))
        self.assertEqual(code, 0, text)
        self.assertIn("2 runs identical", text)

    def test_selftest_history_does_not_feed_the_score_diff_gate(self):
        run("selftest", env_extra=self.env)
        rows = mutate_step(gold_rows(), "case_01", 1, resource_id="account_999")
        code, text = run("score", "--pred", str(tmp_copy(rows=rows)), env_extra=self.env)
        self.assertEqual(code, 0, text)
        self.assertIn("(first run)", text)


class LoaderCheck(unittest.TestCase):
    def test_loaders_command_reports_summary_gold_check_and_losses(self):
        code, out = run("loaders", "--files", "evidence_03,evidence_92,evidence_94", "--spot")
        self.assertEqual(code, 0, out)
        for marker in ("DATASET SUMMARY", "GOLD CHECK", "SPOT CHECK", "UNATTRIBUTED (smallest 10"):
            self.assertIn(marker, out)
        self.assertIn("gold-cited pairs: ", out)
        self.assertIn(" 0 failed", out)


class SqlLoaderReport(unittest.TestCase):
    def test_sql_kind_reports_replica_drift_and_deletion_pending(self):
        code, out = run("loaders", "--kind", "sql")
        self.assertEqual(code, 0, out)
        self.assertIn("SQL DRIFT: 13 replica-only resources in 11 files", out)
        self.assertIn("DELETION_PENDING rows: 8", out)
