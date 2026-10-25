"""Usage tracker: totals, cost, notes and the per-run log (ADR 0008).

Costs are worked out by hand from PRICE_PER_MTOK: 1,000 input and 300 output tokens of the intent
model cost (1000 * 0.75 + 300 * 4.50) / 1e6 = 0.0021 USD; a cache hit costs nothing.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401  (puts code/ on sys.path)

from ghostaudit import usage

MODEL = "gpt-5.4-mini-2026-03-17"


class Tracker(unittest.TestCase):
    def setUp(self):
        self.t = usage.Tracker()
        self.t.record("openai", MODEL, 1000, 300, 812.34, cache_hit=False)
        self.t.record("openai", MODEL, 0, 0, 0.0, cache_hit=True)
        self.t.record_failure("openai", MODEL, 3, 95.0, "APITimeoutError: timed out")
        self.t.note("key set without the SDK")
        self.t.note("key set without the SDK")  # repeated: kept once

    def test_totals_count_live_calls_cache_hits_failures_and_cost(self):
        t = self.t.totals()
        self.assertEqual(
            (t["calls"], t["cache_hits"], t["degraded"], t["failed_attempts"]), (1, 1, 1, 3)
        )
        self.assertEqual((t["input_tokens"], t["output_tokens"]), (1000, 300))
        self.assertAlmostEqual(t["cost_usd"], 0.0021)
        self.assertEqual(t["notes"], ["key set without the SDK"])
        self.assertEqual(t["cache_hits_per_model"], {MODEL: 1})
        self.assertEqual(self.t.rows()[0]["latency_ms"], 812.3)

    def test_summary_names_the_notes(self):
        s = self.t.summary()
        self.assertIn("1 live call(s), 1 cache hit(s)", s)
        self.assertIn("est. cost $0.0021", s)
        self.assertTrue(s.endswith("; notes: key set without the SDK"), s)

    def test_run_log_lists_every_call_and_failure(self):
        d = Path(tempfile.mkdtemp(prefix="ghostaudit_usage_test_"))
        try:
            usage.write_run_log(d / "usage", self.t)
            [log] = sorted((d / "usage").glob("usage_*.md"))
            text = log.read_text(encoding="utf-8")
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertIn("- live calls 1, cache hits 1, input tokens 1000", text)
        self.assertIn("- note: key set without the SDK", text)
        self.assertIn("- failure: APITimeoutError: timed out after 3 attempts", text)
        self.assertIn(f"| openai | {MODEL} | 1000 | 300 | 812.3 | False |", text)
        self.assertIn(f"| openai | {MODEL} | 0 | 0 | 0.0 | True |", text)


if __name__ == "__main__":
    unittest.main()
