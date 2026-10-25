"""Degradation: a key without the SDK, API errors, bad answers or a missing PDF tool must fall back
to
rules + committed caches, never crash, never cache a failure, and never change output.csv for
cached texts."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from _path import CODE, DATA, ROOT

from ghostaudit import llm_intent, usage
from ghostaudit.intent import classify_rules
from ghostaudit.loaders import pdf

# rules remainder -> model decides
MIXED = "Please remove me from marketing lists only, I still want receipts."


class Raising:
    """chat.completions.create raises (or returns junk) every time; counts attempts."""

    def __init__(self, exc=None, content=None):
        self.exc, self.content, self.calls = exc, content, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        if self.exc:
            raise self.exc
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2),
        )


class ApiFailures(unittest.TestCase):
    def check(self, client):
        t = usage.Tracker()
        cache = {}
        c = llm_intent.IntentClassifier(client=client, cache=cache, tracker=t, backoff=0)
        got = c.classify(MIXED)
        self.assertEqual(
            (got.label, got.source), (classify_rules(MIXED).label, "rules (model error)")
        )
        self.assertEqual(client.calls, 1 + llm_intent.MAX_RETRIES)  # bounded retry
        self.assertEqual(cache, {})  # a failure is never cached
        self.assertEqual(t.totals()["degraded"], 1)
        self.assertEqual(c.counts["degraded"], 1)
        return t

    def test_connection_timeout_auth_and_rate_limit_errors(self):
        for exc in (
            ConnectionError("down"),
            TimeoutError("slow"),
            PermissionError("401 invalid key"),
            RuntimeError("429 rate limit"),
        ):
            t = self.check(Raising(exc=exc))
            self.assertIn(type(exc).__name__, t.failures[0]["error"])

    def test_malformed_json_and_schema_violation(self):
        self.check(Raising(content="not json"))
        self.check(
            Raising(content=json.dumps({"asks_to_delete": "yes"}))
        )  # wrong type, missing fields


class MissingSdk(unittest.TestCase):
    def test_key_without_openai_package_warns_once_and_falls_back(self):
        import builtins

        real = builtins.__import__

        def blocked(name, *a, **k):
            if name == "openai" or name.startswith("openai."):
                raise ModuleNotFoundError("No module named 'openai'")
            return real(name, *a, **k)

        t = usage.Tracker()
        old = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-not-a-real-key"
        builtins.__import__ = blocked
        try:
            client = llm_intent.default_client(t)
            client2 = llm_intent.default_client(t)
        finally:
            builtins.__import__ = real
            if old is None:
                del os.environ["OPENAI_API_KEY"]
            else:
                os.environ["OPENAI_API_KEY"] = old
        self.assertIsNone(client)
        self.assertIsNone(client2)
        self.assertEqual([n for n in t.notes if "openai" in n].__len__(), 1)  # warned once
        c = llm_intent.IntentClassifier(client=None, cache={}, tracker=t)
        self.assertEqual(c.classify(MIXED).source, "rules (no model verdict)")


class PdfWithoutTools(unittest.TestCase):
    def test_dataset_pdfs_load_from_the_committed_text_cache_without_any_backend(self):
        raw = (DATA / "evidence" / "documents" / "delivery_correction_attachment.pdf").read_bytes()
        self.assertIn("support_001", pdf.extract_text(raw, backends=()))

    def test_unknown_pdf_without_backends_is_still_a_hard_error(self):
        with self.assertRaises(pdf.PdfTextUnavailable):
            pdf.extract_text(b"%PDF-1.4 not a dataset file", backends=())


def run_main(out, env_extra, data=DATA, extra_path=None):
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    env.update(env_extra)
    if extra_path:
        env["PYTHONPATH"] = str(extra_path) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(CODE / "main.py"), "--data", str(data), "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )


class WholePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ghostaudit_degrade_"))
        p = run_main(cls.tmp / "cache_only.csv", {})
        assert p.returncode == 0, p.stderr
        cls.baseline = (cls.tmp / "cache_only.csv").read_bytes()

    def fake_openai(self, body):
        d = self.tmp / f"fake_{abs(hash(body))}"
        (d / "openai").mkdir(parents=True, exist_ok=True)
        (d / "openai" / "__init__.py").write_text(body)
        return d

    def test_key_set_but_openai_import_blocked(self):
        d = self.fake_openai("raise ModuleNotFoundError(\"No module named 'openai'\")\n")
        p = run_main(
            self.tmp / "blocked.csv", {"OPENAI_API_KEY": "test-not-a-real-key"}, extra_path=d
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((self.tmp / "blocked.csv").read_bytes(), self.baseline)
        self.assertEqual(p.stderr.count("openai"), 1, p.stderr)  # one warning

    def test_client_raising_on_every_call(self):
        # a fresh remainder text forces a cache miss; the raising client must degrade it to the
        # rules label
        from evaluation.overlay import Overlay

        body = (
            "class _C:\n    def create(self, **kw):\n        raise ConnectionError('injected "
            "failure')\n"
            "class OpenAI:\n    def __init__(self, **kw):\n        self.chat = type('X', (), "
            "{'completions': _C()})()\n"
        )
        d = self.fake_openai(body)
        with Overlay(DATA) as ov:
            rows = ov.rows("deletion_requests.csv")
            extra = dict(
                rows[-1],
                case_id="case_9999",
                request_text="Please remove my old newsletter preferences only; do not close the "
                "account.",
            )
            ov.write_rows("deletion_requests.csv", rows + [extra])
            ref = run_main(self.tmp / "ov_nokey.csv", {}, data=ov.root)
            p = run_main(
                self.tmp / "ov_raise.csv",
                {"OPENAI_API_KEY": "test-not-a-real-key"},
                data=ov.root,
                extra_path=d,
            )
        self.assertEqual((ref.returncode, p.returncode), (0, 0), p.stderr)
        self.assertEqual(
            (self.tmp / "ov_raise.csv").read_bytes(), (self.tmp / "ov_nokey.csv").read_bytes()
        )
        self.assertIn("degraded by error 1", p.stdout)


if __name__ == "__main__":
    unittest.main()
