"""Literal audit: no case_N / evidence_N literals in code/ outside tests/ and fixtures/."""

import tempfile
import unittest
from pathlib import Path

from evaluation import audit
from evaluation.tests.helpers import ROOT


class LiteralAudit(unittest.TestCase):
    def test_flags_literals_with_path_and_line(self):
        d = Path(tempfile.mkdtemp())
        (d / "solver.py").write_text("x = 1\nif cid == 'case_12': pass\n")
        (d / "notes.md").write_text("cite evidence_54 here\n")
        hits = audit.scan(d)
        self.assertIn("solver.py:2: case_12", hits)
        self.assertIn("notes.md:1: evidence_54", hits)

    def test_ignores_tests_fixtures_and_regex_patterns(self):
        d = Path(tempfile.mkdtemp())
        (d / "tests").mkdir()
        (d / "tests" / "t.py").write_text("'case_12'\n")
        (d / "evaluation" / "fixtures").mkdir(parents=True)
        (d / "evaluation" / "fixtures" / "s.txt").write_text("case_01\n")
        (d / "ok.py").write_text("PAT = r'case_\\d+'\nname = 'case_id'\n")
        self.assertEqual(audit.scan(d), [])

    def test_real_code_tree_is_clean(self):
        self.assertEqual(audit.scan(ROOT / "code"), [])


class GeneratedReports(unittest.TestCase):
    def test_generated_reports_are_exempt_but_hand_written_markdown_is_not(self):
        import tempfile
        from pathlib import Path

        d = Path(tempfile.mkdtemp())
        (d / "evaluation").mkdir()
        (d / "evaluation" / "evaluation_report.md").write_text("case_12 is cited\n")
        (d / "evaluation" / "notes.md").write_text("see case_12\n")
        self.assertEqual(audit.scan(d), ["evaluation/notes.md:1: case_12"])
