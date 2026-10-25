"""Error handling in the solver package: one error family, warnings through logging.

Every error ghostaudit raises on purpose derives from GhostAuditError, so a caller can stop on
"the audit cannot continue" without catching unrelated bugs; and library code reports degradation
through the `ghostaudit` logger instead of printing.
"""

import ast
import unittest

from _path import CODE

from ghostaudit import errors, llm_intent
from ghostaudit.loaders import LoaderPending, UnknownSignature, pdf, screens


class ErrorFamily(unittest.TestCase):
    def test_every_solver_error_is_a_ghostaudit_error(self):
        for exc in (
            UnknownSignature,
            LoaderPending,
            pdf.PdfTextUnavailable,
            screens.MissingTranscription,
        ):
            self.assertTrue(issubclass(exc, errors.GhostAuditError), exc.__name__)

    def test_no_bare_except_and_no_print_in_library_code(self):
        for p in sorted((CODE / "ghostaudit").rglob("*.py")):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                if isinstance(n, ast.ExceptHandler):
                    self.assertIsNotNone(n.type, f"bare except in {p.name}:{n.lineno}")
                if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "print":
                    self.fail(f"print() in library code: {p.name}:{n.lineno}")


class Warnings(unittest.TestCase):
    def test_a_degradation_warning_is_logged_once(self):
        llm_intent._warned.discard("probe")
        with self.assertLogs("ghostaudit", level="WARNING") as logs:
            llm_intent._warn_once("probe", "something degraded")
            llm_intent._warn_once("probe", "something degraded")
        self.assertEqual(logs.output, ["WARNING:ghostaudit.llm_intent:something degraded"])


if __name__ == "__main__":
    unittest.main()
