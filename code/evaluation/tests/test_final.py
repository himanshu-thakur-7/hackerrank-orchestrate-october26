"""T14 final validation: the clean-room check runs the packaged code, alone in an empty directory, with no key."""
import hashlib
import unittest
from pathlib import Path

from evaluation import final

ROOT = Path(__file__).resolve().parents[3]


class CleanRoom(unittest.TestCase):
    def test_unzipped_code_alone_reproduces_output_csv_without_keys(self):
        r = final.clean_room()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["sha256"], hashlib.sha256((ROOT / "output.csv").read_bytes()).hexdigest())
        self.assertFalse(r["keys_in_env"])
        self.assertFalse(str(ROOT) in r["workdir"])


class Steps(unittest.TestCase):
    def test_a_failing_step_makes_the_whole_validation_fail(self):
        ok, rows = final.summarize([("a", 0, "fine"), ("b", 1, "broken")])
        self.assertFalse(ok)
        self.assertEqual([r[1] for r in rows], ["PASS", "FAIL"])
        self.assertTrue(final.summarize([("a", 0, "fine")])[0])


if __name__ == "__main__":
    unittest.main()
