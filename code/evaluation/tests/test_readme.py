"""T14: the README in code.zip quotes only commands that exist and counts that the real run reproduces."""
import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def commands():
    return [re.split(r"\s+#", l)[0].strip() for l in re.findall(r"^python3 code/\S+.*$", README, re.M)] + \
           re.findall(r"`(python3 code/[^`]+)`", README)


class Commands(unittest.TestCase):
    def test_every_quoted_command_and_flag_parses(self):
        cmds = commands()
        self.assertGreaterEqual(len(cmds), 8)
        for c in cmds:
            argv = c.split()[1:]
            if argv[0] == "code/package.py":            # no argparse; running it builds the zip
                self.assertTrue((ROOT / argv[0]).is_file())
                continue
            p = subprocess.run([sys.executable] + argv + ["--help"], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(p.returncode, 0, f"{c}: {p.stderr[-300:]}")

    def test_every_quoted_path_exists(self):
        for path in set(re.findall(r"`((?:code|docs)/[\w./-]+)`", README)):
            self.assertTrue((ROOT / path).exists(), path)


class Numbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = Path(tempfile.mkdtemp()) / "o.csv"
        cls.stdout = subprocess.run([sys.executable, "code/main.py", "--out", str(out)], capture_output=True, text=True, cwd=ROOT).stdout
        cls.rows = list(csv.DictReader(open(out, newline="", encoding="utf-8")))

    def test_counts_quoted_in_the_readme_match_the_real_run(self):
        self.assertIn(f"({len(self.rows)} rows)", README)
        empty = sum(1 for r in self.rows if r["deletion_status"] == "INCOMPLETE" and json.loads(r["steps_json"]) == [])
        self.assertIn(f"{empty} eval rows are affected", README)
        tied = int(re.search(r"tied (\d+)", self.stdout).group(1))
        self.assertIn(f"{tied} eval cases have tied account candidates", README)
        adrs = sorted(p.name[:4] for p in (ROOT / "docs" / "adr").glob("0*.md"))
        self.assertIn(f"ADRs {adrs[0]}–{adrs[-1]}", README)


if __name__ == "__main__":
    unittest.main()
