"""T14 final validation: the clean-room check runs the packaged code, alone in an empty directory, with no key."""

import hashlib
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from evaluation import final

ROOT = Path(__file__).resolve().parents[3]


class CleanRoom(unittest.TestCase):
    def test_unzipped_code_alone_reproduces_output_csv_without_keys(self):
        r = final.clean_room()
        self.assertTrue(r["ok"], r)
        self.assertEqual(
            r["sha256"], hashlib.sha256((ROOT / "output.csv").read_bytes()).hexdigest()
        )
        self.assertFalse(r["keys_in_env"])
        self.assertFalse(str(ROOT) in r["workdir"])


class Steps(unittest.TestCase):
    def test_a_failing_step_makes_the_whole_validation_fail(self):
        ok, rows = final.summarize([("a", 0, "fine"), ("b", 1, "broken")])
        self.assertFalse(ok)
        self.assertEqual([r[1] for r in rows], ["PASS", "FAIL"])
        self.assertTrue(final.summarize([("a", 0, "fine")])[0])


class Matrix(unittest.TestCase):
    PROBE = (
        "import importlib, shutil, subprocess, sys\n"
        "def ok(m):\n    try:\n        importlib.import_module(m); return True\n    except ImportError:\n        return False\n"
        "print({m: ok(m) for m in ('pandas', 'openai', 'pypdf', 'typesafe_sdk', 'json')}, shutil.which('pdftotext') is not None)\n"
        "print(subprocess.run([sys.executable, '-c', 'import importlib.util as u; print(u.find_spec(\"pandas\") is not None)'], "
        "capture_output=True, text=True).stdout.strip())"
    )

    def probe(self, block):
        p = subprocess.run(
            [sys.executable, "-c", self.PROBE],
            capture_output=True,
            text=True,
            env=final.blocked_env(block),
        )
        return p.stdout.strip().split("\n")

    def test_every_optional_dependency_can_be_blocked_alone_or_all_together(self):
        self.assertEqual(final.OPTIONAL, ("pandas", "openai", "pypdf", "typesafe_sdk", "pdftotext"))
        out = self.probe(("pandas",))
        self.assertIn("'pandas': False", out[0])
        self.assertIn("'json': True", out[0])
        self.assertEqual(out[1], "False")  # child processes stay blocked
        out = self.probe(final.OPTIONAL)
        for m in ("pandas", "openai", "pypdf", "typesafe_sdk"):
            self.assertIn(f"'{m}': False", out[0])
        self.assertTrue(out[0].endswith("False"))  # pdftotext is off PATH
        self.assertTrue(self.probe(())[0].endswith(str(shutil.which("pdftotext") is not None)))

    def test_configs_are_each_dependency_alone_then_all(self):
        self.assertEqual(final.matrix_configs(), [(m,) for m in final.OPTIONAL] + [final.OPTIONAL])


if __name__ == "__main__":
    unittest.main()
