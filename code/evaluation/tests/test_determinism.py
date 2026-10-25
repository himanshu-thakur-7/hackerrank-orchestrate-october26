"""Determinism gate: run the solver command twice, compare sha256 of the file it writes."""

import sys, tempfile, unittest
from pathlib import Path
from evaluation import gate


class Determinism(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp()) / "output.csv"

    def test_stable_command_passes(self):
        cmd = [
            sys.executable,
            "-c",
            f"open({str(self.out)!r},'w').write('case_id,deletion_status,steps_json\\n')",
        ]
        ok, hashes, msg = gate.determinism(cmd, self.out)
        self.assertTrue(ok, msg)
        self.assertEqual(len(set(hashes)), 1)

    def test_unstable_command_fails_with_both_hashes(self):
        cmd = [
            sys.executable,
            "-c",
            f"import time; open({str(self.out)!r},'w').write(str(time.time_ns()))",
        ]
        ok, hashes, msg = gate.determinism(cmd, self.out)
        self.assertFalse(ok)
        self.assertTrue(msg.startswith("L0.determinism"))
        self.assertIn(hashes[0][:12], msg)

    def test_failing_command_is_reported(self):
        ok, _, msg = gate.determinism([sys.executable, "-c", "raise SystemExit(3)"], self.out)
        self.assertFalse(ok)
        self.assertIn("exit 3", msg)
