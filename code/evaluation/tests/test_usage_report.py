"""T14 usage report: render(data) is pure and carries every required figure; final_run() measures
the real run."""

import hashlib
import os
import unittest
from pathlib import Path

from evaluation import usage_report

ROOT = Path(__file__).resolve().parents[3]
MODEL = "gpt-5.4-mini-2026-03-17"
DATA = {
    "generated_at": "2026-10-25T00:00:00Z",
    "commit": "abc1234",
    "final": {
        "requests": 518,
        "sha256": "eb99c26b7974aaaa",
        "output_matches": True,
        "key_set": False,
        "intent": {"rules": 392, "cache": 6, "model": 0, "rules_fallback": 0, "degraded": 0},
        "totals": {
            "calls": 2,
            "cache_hits": 12,
            "degraded": 1,
            "failed_attempts": 3,
            "notes": [],
            "input_tokens": 840,
            "output_tokens": 80,
            "cost_usd": 0.00099,
            "per_model": {
                MODEL: {"provider": "openai", "calls": 2, "input_tokens": 840, "output_tokens": 80}
            },
            "cache_hits_per_model": {MODEL: 12},
        },
    },
    "openai_origin": [
        {
            "run_at": "r1",
            "live_calls": 398,
            "input_tokens": 363369,
            "output_tokens": 20163,
            "entries_added": 398,
        }
    ],
    "openai_cache_entries": 399,
    "jev_origin": {
        "run_at": "r2",
        "live_calls": 11450,
        "input_tokens": 8889300,
        "output_tokens": 435100,
        "errors": 0,
    },
    "jev_cache_entries": 1145,
}


class Render(unittest.TestCase):
    def setUp(self):
        self.md = usage_report.render(DATA)

    def test_required_sections(self):
        for h in (
            "## 1. Final full-dataset run",
            "## 2. Where the cache came from",
            "## 3. Evaluation-only model: TypeSafe Jev",
            "## 4. Totals per model and overall",
            "## 5. Prices and assumptions",
            "## 6. Reproduce",
        ):
            self.assertIn(h, self.md)

    def test_final_run_figures_per_provider_and_model(self):
        for s in (
            "openai",
            MODEL,
            "| 2 | 12 |",
            "840",
            "80",
            "460",
            "$0.0010",
            "degraded by error",
            "518",
        ):
            self.assertIn(s, self.md)
        self.assertIn("eb99c26b7974", self.md)

    def test_cache_origin_and_jev_are_reported_separately(self):
        for s in (
            "363,369",
            "20,163",
            "399 entries",
            "11,450",
            "8,889,300",
            "435,100",
            "1145 entries",
            "evaluation only",
        ):
            self.assertIn(s, self.md)
        self.assertIn("$0.3734", self.md)  # 8,889,300 input tokens at $0.042 / 1M, output free

    def test_no_secret_or_key_value_ever_appears(self):
        self.assertNotIn("sk-", self.md)
        self.assertIn("OPENAI_API_KEY", self.md)  # the variable is named, never its value


class FinalRun(unittest.TestCase):
    def test_the_measured_run_reproduces_the_committed_output_without_a_key(self):
        env = {
            k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "TYPESAFE_API_KEY")
        }
        f = usage_report.final_run(env=env)
        self.assertEqual(f["requests"], 518)
        self.assertEqual(
            f["sha256"], hashlib.sha256((ROOT / "output.csv").read_bytes()).hexdigest()
        )
        self.assertTrue(f["output_matches"])
        self.assertEqual(f["totals"]["calls"], 0)
        self.assertGreater(f["totals"]["cache_hits"], 0)


if __name__ == "__main__":
    unittest.main()
