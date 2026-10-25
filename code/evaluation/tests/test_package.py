"""T14 packaging: code.zip holds README.md and code/ only, and no key-like string appears in the zip or the repo."""
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

    def test_only_readme_and_code(self):
        self.assertIn("README.md", self.names)
        self.assertTrue(all(n == "README.md" or n.startswith("code/") for n in self.names), self.names[:5])

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
