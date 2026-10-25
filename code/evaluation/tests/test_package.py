"""T14 packaging: code.zip holds README.md, code/, the report copies and sanitized docs/; no key-like string anywhere."""
import hashlib
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

import package

ROOT = Path(__file__).resolve().parents[3]


class Zip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zip = Path(tempfile.mkdtemp()) / "code.zip"
        package.build(cls.zip)
        with zipfile.ZipFile(cls.zip) as z:
            cls.names = z.namelist()
            cls.text = {n: z.read(n) for n in cls.names}

    def test_only_readme_code_docs_and_the_two_report_copies(self):
        self.assertIn("README.md", self.names)
        extra = {"evaluation/evaluation_report.md", "evaluation/usage_report.md"}
        self.assertTrue(all(n == "README.md" or n.startswith(("code/", "docs/")) or n in extra for n in self.names), self.names[:5])

    def test_docs_are_present_markdown_only(self):
        docs = [n for n in self.names if n.startswith("docs/")]
        for n in ("docs/adr/README.md", "docs/adr/0001-case-id-sort-order.md", "docs/adr/0016-stale-absent-links.md",
                  "docs/01_CONTRACT.md", "docs/02_DATA_NOTES.md", "docs/02b_DOCS_AND_SCREENS.md", "docs/03_DESIGN.md",
                  "docs/03_ID_RECOVERY_PROTOTYPE.md", "docs/LOSS_LEDGER.md", "docs/SILVER_AUDIT.md", "docs/silver_audit/auditor_A.md",
                  "docs/JEV_SPIKE.md", "docs/JEV_HANDCHECK.md", "docs/JEV_REVIEW_QUEUE.md", "docs/READINESS.md", "docs/BOARD.md",
                  "docs/CONTEXT.md"):
            self.assertIn(n, docs)
        self.assertEqual(len([n for n in docs if n.startswith("docs/adr/0")]), len(list((ROOT / "docs" / "adr").glob("0*.md"))))
        self.assertTrue(all(n.endswith(".md") for n in docs), docs)

    def test_docs_and_readme_hold_no_email_or_phone(self):
        values = package.identity_values(ROOT / "dataset")
        self.assertGreater(len(values["email"]), 100)
        self.assertGreater(len(values["phone"]), 100)
        for n in [n for n in self.names if n.startswith("docs/")] + ["README.md"]:
            t = self.text[n].decode("utf-8")
            self.assertIsNone(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", t), n)
            self.assertIsNone(re.search(r"\+\d{1,3}[ (]*\d[\d ()-]{5,}\d", t), n)
            self.assertIsNone(re.search(r"tel:\+?\d{6,}", t), n)
            for kind in ("email", "phone"):
                self.assertFalse([v for v in values[kind] if v in t], (n, kind))

    def test_sanitizer_masks_stably_and_keeps_ids(self):
        src = "user_7 old a.b@example.org new A.B@example.org tel:+97150482 +34 612 847 593 case_12 account_005 evidence_01"
        out = package.sanitize(src, {"email": [], "phone": [], "rows": set()})
        self.assertNotIn("@", out)
        self.assertNotIn("612 847", out)
        for keep in ("user_7", "case_12", "account_005", "evidence_01"):
            self.assertIn(keep, out)
        tok = re.findall(r"email#[0-9a-f]{6}", out)
        self.assertEqual(len(tok), 2)
        self.assertEqual(tok[0], tok[1])                      # case-insensitive: the same address gives the same token

    def test_verbatim_dataset_rows_are_dropped(self):
        row = "INSERT INTO customer_profiles VALUES ('account_005', 'user_05', 'Some Name', 'x', 'y', 'z', 'ACTIVE', '2026-01-01');"
        out = package.sanitize(f"before\n    {row}\nafter `short fragment`", {"email": [], "phone": [], "rows": {row}})
        self.assertNotIn(row, out)
        self.assertIn("[dataset row omitted]", out)
        self.assertIn("short fragment", out)

    def test_two_builds_are_byte_identical(self):
        other = Path(tempfile.mkdtemp()) / "code.zip"
        package.build(other)
        self.assertEqual(hashlib.sha256(other.read_bytes()).hexdigest(), hashlib.sha256(self.zip.read_bytes()).hexdigest())

    def test_reports_exist_at_both_paths_and_are_identical(self):
        for r in ("evaluation_report.md", "usage_report.md"):
            self.assertIn(f"code/evaluation/{r}", self.names)
            self.assertIn(f"evaluation/{r}", self.names)
            self.assertEqual(self.text[f"evaluation/{r}"], self.text[f"code/evaluation/{r}"])
            self.assertEqual(self.text[f"evaluation/{r}"], (ROOT / "code" / "evaluation" / r).read_bytes())

    def test_required_files_are_inside(self):
        for n in ("code/main.py", "code/package.py", "code/evaluation/evaluation_report.md", "code/evaluation/usage_report.md",
                  "code/prompts/intent_classifier.md", "code/ghostaudit/llm_cache.py", "code/ghostaudit/loaders/pdf_text_cache.py"):
            self.assertIn(n, self.names)

    def test_nothing_forbidden(self):
        for n in self.names:
            parts = n.split("/")
            self.assertFalse({"dataset", "runs", "scratch", "__pycache__", ".venv", "venv", "node_modules", ".git"} & set(parts), n)
            self.assertNotIn(Path(n).name, (".env", ".DS_Store"))
            self.assertFalse(n.endswith((".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".pyc")), n)

    def test_no_key_pattern_in_the_zip(self):
        self.assertEqual([n for n, b in self.text.items() if package.key_hits(b.decode("utf-8", "ignore"))], [])


class Repo(unittest.TestCase):
    def test_no_key_pattern_in_any_tracked_file(self):
        self.assertEqual(package.scan_repo(), [])

    def test_the_scanner_catches_key_shapes_but_not_ordinary_words(self):
        self.assertTrue(package.key_hits("OPENAI_API_KEY=sk-" + "a1B2" * 6))
        self.assertTrue(package.key_hits("token apikey_" + "Zx9" * 4))
        self.assertFalse(package.key_hits("delete-task-btn, disk-cached, risk-free, the sk- prefix"))


if __name__ == "__main__":
    unittest.main()
