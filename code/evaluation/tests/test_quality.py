"""quality: code-quality metrics from the standard library, plus optional dev tools.

complexity(), docstrings() and annotations() read source text only; the expected values below are
counted by hand on small snippets. A dev tool that is not installed is reported as SKIPPED (None),
never as a failure.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation import quality

SNIPPET = '''"""A module. Decisions: ADR 0001."""


def flat(a: int) -> int:
    """Documented."""
    return a


def branchy(a, b):
    if a and b or a:
        return [x for x in a if x]
    for _ in b:
        while a:
            try:
                a -= 1
            except ValueError:
                break
    return 1 if a else 2


class Thing:
    def method(self, x: str) -> None:
        """Documented."""

    def _private(self, y):
        pass
'''


def _tree(files):
    d = Path(tempfile.mkdtemp(prefix="ghostaudit_quality_"))
    for name, text in files.items():
        (d / name).parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text, encoding="utf-8")
    return d


class Complexity(unittest.TestCase):
    def test_counts_decision_points_like_radon(self):
        cc = {name: n for _, name, n in quality.complexity([_tree({"m.py": SNIPPET}) / "m.py"])}
        # branchy: 1 + if + and/or (2 operators) + comprehension for + its if + for + while
        # + except + conditional expression = 10
        self.assertEqual(cc, {"flat": 1, "branchy": 10, "Thing.method": 1, "Thing._private": 1})

    def test_a_nested_function_is_its_own_block(self):
        src = (
            "def outer(a):\n    def inner(b):\n        if b:\n            return 1\n"
            "    for x in a:\n        def in_loop(c):\n            return c or x\n    return a\n"
        )
        cc = {name: n for _, name, n in quality.complexity([_tree({"m.py": src}) / "m.py"])}
        self.assertEqual(cc, {"outer": 2, "outer.inner": 2, "outer.in_loop": 2})


class Coverage(unittest.TestCase):
    def test_docstrings_cover_modules_and_public_definitions(self):
        documented, total, missing = quality.docstrings([_tree({"m.py": SNIPPET}) / "m.py"])
        # module, flat, branchy, Thing, Thing.method; _private is not public
        self.assertEqual((documented, total), (3, 5))
        self.assertEqual([m.split(" ")[-1] for m in missing], ["branchy", "Thing"])

    def test_a_module_docstring_must_name_its_adr(self):
        p = _tree({"m.py": '"""A module without a decision line."""\n'}) / "m.py"
        self.assertEqual(quality.docstrings([p])[:2], (0, 1))

    def test_annotations_count_every_function_with_all_arguments_and_return(self):
        annotated, total, missing = quality.annotations([_tree({"m.py": SNIPPET}) / "m.py"])
        self.assertEqual((annotated, total), (2, 4))  # flat and method; self needs none
        self.assertEqual([m.split(" ")[-1] for m in missing], ["branchy", "Thing._private"])


class Tools(unittest.TestCase):
    def test_a_missing_tool_is_skipped_not_failed(self):
        empty = tempfile.mkdtemp(prefix="ghostaudit_nopath_")
        old = os.environ.get("PATH", "")
        os.environ["PATH"] = empty
        try:
            self.assertIsNone(quality.tool(["no-such-quality-tool-xyz"]))
        finally:
            os.environ["PATH"] = old

    def test_test_counts_come_from_unittest_discovery(self):
        counts = quality.test_counts(Path(__file__).resolve().parents[2])
        self.assertGreater(counts["solver"], 0)
        self.assertGreater(counts["evaluation"], 0)

    def test_report_marks_skipped_metrics(self):
        m = {
            "ruff_findings": None,
            "mypy_errors": None,
            "mypy_relaxed_errors": None,
            "coverage_min": None,
            "coverage_total": None,
        }
        lines = quality.render_tools(m)
        self.assertTrue(all("SKIPPED" in line for line in lines), lines)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
