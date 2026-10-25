"""Loader edge cases: every record-like unit a loader cannot use is reported, never dropped.

Readback traces, record-lookup lines and register rows each have a failure mode (a line outside
the grammar, a trace that never completes, an unknown result, a row without an identifier) that
must surface as `unparsed` or `unattributed`; PDF text comes from the committed cache, then from
each backend in order, and a PDF nothing can read stops the run.
"""

import hashlib
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

from _path import DATA

from ghostaudit.errors import GhostAuditError
from ghostaudit.loaders import pdf, pdf_text_cache, readback, record_lookup, register
from ghostaudit.loaders.common import LoadResult

TS = "2026-09-01T10:00:0"
EMAIL = "ava.example@example.org"


def _reasons(units):
    return [u.reason for u in units]


class Readback(unittest.TestCase):
    def test_traces_join_the_lookup_key_and_report_what_they_cannot_use(self):
        text = "\n".join(
            [
                f"{TS}0Z level=INFO service=search_service trace_id=t1 event=lookup_started "
                f"resource_id=search_1 lookup_key={EMAIL}",
                f"{TS}1Z level=INFO service=search_service trace_id=t1 event=lookup_completed "
                "resource_id=search_1 rows=0",
                "",
                "this is not a readback line",
                f"{TS}2Z level=INFO service=search_service trace_id=t2 event=lookup_started "
                f"resource_id=search_2 lookup_key={EMAIL}",
                f"{TS}3Z level=INFO service=search_service trace_id=t3 event=lookup_completed "
                "rows=1",
            ]
        )
        r = readback.load("ev_rb", "2026-09-02T00:00:00Z", text)
        [o] = r.observations
        self.assertEqual((o.resource_id, o.state, o.identifiers), ("search_1", "ABSENT", (EMAIL,)))
        self.assertEqual(
            _reasons(r.unparsed),
            [
                "not a readback log line",
                "trace t2 has no completed event",
                "completed event without resource_id",
            ],
        )


class RecordLookup(unittest.TestCase):
    def line(self, result, subject=' subject_reference="user_1"'):
        return (
            f'{TS}0Z INFO service=lookup_svc event=record_lookup seq=1 system="backup_service" '
            f'resource_id="backup_1" record_type="BACKUP_ARCHIVE" result="{result}"{subject}'
        )

    def test_an_active_backup_is_restorable_and_bad_lines_are_reported(self):
        text = "\n".join(
            [
                self.line("ACTIVE"),
                "",
                "garbage",
                self.line("MAYBE"),
                self.line("FOUND", subject=""),
            ]
        )
        r = record_lookup.load("ev_rl", "2026-09-02T00:00:00Z", text)
        self.assertEqual(
            [(o.state, o.identifiers, o.table) for o in r.observations],
            [
                ("RESTORABLE", ("user_1",), "lookup_svc.record_lookup"),
                ("PRESENT", (), "lookup_svc.record_lookup"),
            ],
        )
        self.assertEqual(
            _reasons(r.unparsed), ["not a record_lookup line", "unknown register result 'MAYBE'"]
        )
        self.assertEqual(_reasons(r.unattributed), ["no identifier"])

    def test_an_exposing_status_reports_the_identifier_kind(self):
        out = LoadResult("test")
        rec = {
            "system": "support_platform",
            "resource_id": "support_1",
            "record_type": "SUPPORT_MESSAGE",
            "result": "IDENTIFIABLE",
            "lookup_value": EMAIL,
        }
        o = register.observation("ev_reg", rec, "register", "row 1", "2026-09-01T00:00:00Z", out)
        self.assertEqual(
            (o.state, o.pii_fields, o.identifiers, o.observed_at),
            ("PRESENT", ("email",), (EMAIL,), "2026-09-01T00:00:00Z"),
        )
        self.assertEqual(out.observations, [o])


class PdfText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = sorted((DATA / "evidence").rglob("*.pdf"))[0]
        cls.raw = cls.path.read_bytes()
        cls.cached = pdf_text_cache.TEXT[hashlib.sha256(cls.raw).hexdigest()]

    def test_backends_run_in_order_after_a_cache_miss(self):
        miss = self.raw + b"\n%cache-miss\n"  # still a PDF, but not in the committed cache
        calls = []

        def none(raw):
            calls.append("none")  # returns None: this backend cannot read the file

        def text(raw):
            calls.append("text")
            return "from the second backend"

        self.assertEqual(pdf.extract_text(miss, backends=(none, text)), "from the second backend")
        self.assertEqual(calls, ["none", "text"])
        self.assertEqual(pdf.extract_text(self.raw, backends=()), self.cached)  # cache first

    def test_a_pdf_nothing_can_read_stops_the_run(self):
        with self.assertRaises(pdf.PdfTextUnavailable) as e:
            pdf.extract_text(b"%PDF-1.7 unreadable", backends=(lambda raw: None,))
        self.assertIsInstance(e.exception, GhostAuditError)

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext is not installed here")
    def test_regenerating_the_text_cache_reproduces_the_committed_entry(self):
        out = Path(tempfile.mkdtemp(prefix="ghostaudit_pdfcache_")) / "cache.py"
        try:
            pdf.write_text_cache([self.path], out)
            text = runpy.run_path(str(out))["TEXT"]
        finally:
            shutil.rmtree(out.parent, ignore_errors=True)
        self.assertEqual(text, {hashlib.sha256(self.raw).hexdigest(): self.cached})

    def test_pypdf_backend_reads_the_document_when_installed(self):
        got = pdf._pypdf(self.raw)
        if got is None:
            self.skipTest("pypdf is not installed here")
        self.assertTrue(got.strip())


if __name__ == "__main__":
    unittest.main()
