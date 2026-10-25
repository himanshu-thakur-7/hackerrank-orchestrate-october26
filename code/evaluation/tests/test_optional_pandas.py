"""The pandas round-trip is optional: absent pandas -> SKIPPED warning, never a gate failure."""

import sys
import unittest

from evaluation import gate
from evaluation.tests.helpers import GOLD, MANIFEST, SAMPLE_REQ, gold_rows, mutate_step, tmp_copy


class PandasBlocked(unittest.TestCase):
    def setUp(self):
        self._saved = sys.modules.get("pandas", "absent")
        sys.modules["pandas"] = None  # makes `import pandas` raise ImportError

    def tearDown(self):
        if self._saved == "absent":
            sys.modules.pop("pandas", None)
        else:
            sys.modules["pandas"] = self._saved

    def test_gold_passes_and_pandas_check_is_reported_skipped(self):
        warnings = []
        self.assertEqual(gate.check(GOLD, SAMPLE_REQ, MANIFEST, warnings=warnings), [])
        self.assertTrue(any(w.startswith("L0.pandas SKIPPED") for w in warnings), warnings)

    def test_real_violations_still_reported_by_their_own_check(self):
        rows = mutate_step(gold_rows(), "case_05", 2, evidence_id=None)
        v = gate.check(tmp_copy(rows=rows), SAMPLE_REQ, MANIFEST)
        self.assertTrue(v and v[0].startswith("L0.evidence"), v)


class PandasPresent(unittest.TestCase):
    def test_no_skip_warning_when_pandas_importable(self):
        try:
            import pandas  # noqa: F401
        except ImportError:
            self.skipTest("pandas not installed here")
        warnings = []
        gate.check(GOLD, SAMPLE_REQ, MANIFEST, warnings=warnings)
        self.assertEqual(warnings, [])
