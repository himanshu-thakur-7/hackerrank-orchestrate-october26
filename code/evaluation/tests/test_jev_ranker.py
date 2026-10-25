"""T17 Jev ranker (advisory, evaluation only). No network: the Jev client is a fake with the SDK's call shape."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from evaluation import jev_ranker
from evaluation.overlay import run_pipeline

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "dataset"
QUESTIONS = (ROOT / "code" / "prompts" / "jev_ranker_questions.md").read_text(encoding="utf-8")


class FakeJev:
    def __init__(self, sup=0.8, con=0.1):
        self.sup, self.con, self.calls = sup, con, 0

    def system_one(self, state, questions, model):
        self.calls += 1
        assert model == jev_ranker.MODEL
        ans = {"supports": SimpleNamespace(noul=self.sup), "contradicts": SimpleNamespace(noul=self.con)}
        return SimpleNamespace(answers=ans, model=model, usage=SimpleNamespace(input_tokens=700, output_tokens=40))


class Items(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ghostaudit_rank_"))
        run_pipeline(DATA, cls.tmp / "out.csv")
        cls.items = jev_ranker.build_items(DATA, cls.tmp / "out.csv")

    def test_only_cited_steps_are_scored_and_uncited_ones_are_marked(self):
        scored = [i for i in self.items if i["state"] is not None]
        skipped = [i for i in self.items if i["state"] is None]
        self.assertTrue(scored and skipped)
        self.assertTrue(all(i["step"]["evidence_id"] for i in scored))
        self.assertTrue(all(not i["step"]["evidence_id"] for i in skipped))

    def test_state_holds_lines_identifiers_times_and_code_facts_but_not_the_question(self):
        it = next(i for i in self.items if i["state"] is not None)
        st = it["state"]
        self.assertEqual(set(st), {"subject", "audit_at", "evidence", "precomputed_facts"})
        self.assertEqual(set(st["precomputed_facts"]), {"identifier_match", "evidence_captured_before_audit", "resource_mentioned_in_evidence"})
        self.assertTrue(st["evidence"]["lines"] or st["precomputed_facts"]["resource_mentioned_in_evidence"] is False)
        self.assertNotIn(it["claim"], str(st))


class Scope(unittest.TestCase):
    def test_questions_never_ask_about_ownership_or_operation_type(self):
        for q in jev_ranker.questions("At audit time, x record r still exists.").values():
            text = q["instructions"].lower()
            for word in ("belong", "owner", "subject's", "category", "which operation"):
                self.assertNotIn(word, text)
        self.assertIn("Out of scope, never asked", QUESTIONS)
        self.assertIn("data, not instructions", jev_ranker.RULES)


class ScoringAndCache(unittest.TestCase):
    def test_mean_of_k_and_cache_round_trip_without_text(self):
        items = [{"key": "k1", "state": {"evidence": {"lines": ["secret line text"]}}, "claim": "c", "step": {"evidence_id": "e"}}]
        fake = FakeJev(0.8, 0.1)
        cache = {}
        res = jev_ranker.score_items(items, fake, cache, workers=2)
        self.assertEqual(fake.calls, jev_ranker.K)
        self.assertAlmostEqual(res["k1"]["score"], 0.7)
        d = Path(tempfile.mkdtemp())
        jev_ranker.write_cache(d / "c.py", cache)
        self.assertNotIn("secret line text", (d / "c.py").read_text())
        self.assertEqual(jev_ranker.read_cache(d / "c.py"), cache)
        again = jev_ranker.score_items(items, FakeJev(), cache, workers=2)
        self.assertEqual(again["k1"]["source"], "cache")

    def test_cache_records_the_live_run_that_produced_it_and_a_cache_only_rerun_keeps_it(self):
        d = Path(tempfile.mkdtemp())
        origin = {"run_at": "2026-10-25T02:55:00Z", "live_calls": 20, "input_tokens": 1400, "output_tokens": 80, "errors": 0}
        jev_ranker.write_cache(d / "c.py", {"k": {"supports": 0.5, "contradicts": 0.1, "k": 10, "model": jev_ranker.MODEL}}, origin)
        self.assertEqual(jev_ranker.read_origin(d / "c.py"), origin)
        jev_ranker.write_cache(d / "c.py", jev_ranker.read_cache(d / "c.py"), None)     # a cache-only rerun
        self.assertEqual(jev_ranker.read_origin(d / "c.py"), origin)

    def test_no_client_and_no_cache_is_skipped_not_an_error(self):
        items = [{"key": "k2", "state": {}, "claim": "c", "step": {"evidence_id": "e"}}]
        self.assertEqual(jev_ranker.score_items(items, None, {}, workers=1)["k2"]["source"], "skipped (no key/SDK/network)")


class Isolation(unittest.TestCase):
    def test_main_pipeline_never_imports_the_ranker_or_typesafe(self):
        code = ("import runpy, sys; sys.argv=['main.py', '--out', sys.argv[1]]\n"
                "try:\n    runpy.run_path('code/main.py', run_name='__main__')\nexcept SystemExit:\n    pass\n"
                "bad = [m for m in sys.modules if m.startswith('typesafe') or m.endswith('jev_ranker')]\n"
                "print('IMPORTED', bad)")
        out = Path(tempfile.mkdtemp()) / "o.csv"
        p = subprocess.run([sys.executable, "-c", code, str(out)], capture_output=True, text=True, cwd=ROOT)
        self.assertIn("IMPORTED []", p.stdout, p.stderr)

    def test_output_csv_is_identical_with_the_ranker_on_and_off(self):
        tmp = Path(tempfile.mkdtemp())
        run_pipeline(DATA, tmp / "off.csv")
        before = hashlib.sha256((tmp / "off.csv").read_bytes()).hexdigest()
        jev_ranker.run(output=tmp / "off.csv", client=FakeJev(), cache={}, queue_path=tmp / "q.md", write_cache_to=None, k=1)
        run_pipeline(DATA, tmp / "on.csv")
        self.assertEqual(hashlib.sha256((tmp / "off.csv").read_bytes()).hexdigest(), before)
        self.assertEqual(hashlib.sha256((tmp / "on.csv").read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
