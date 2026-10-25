"""T02: CSV loading, identity resolution, rules-only intent, writer, and the baseline CLI."""
import csv, hashlib, subprocess, sys, tempfile, unittest
from pathlib import Path
from _path import ROOT, DATA, CODE
from ghostaudit import data, identity, intent, writer

EVAL_NON_DELETION = {f"case_{n}" for n in range(533, 543)}   # read from request text in docs/02_DATA_NOTES.md §1.8


class Loading(unittest.TestCase):
    def test_requests_load_with_all_fields(self):
        ev = data.load_requests(DATA / "deletion_requests.csv")
        sm = data.load_requests(DATA / "sample_deletion_requests.csv")
        self.assertEqual((len(ev), len(sm)), (518, 32))
        self.assertEqual(set(ev[0]), {"case_id", "email", "requested_at", "reported_status", "reported_at", "audit_at", "request_text"})


class Identity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = identity.Resolver.from_dataset(DATA)

    def test_uppercase_current_email_resolves(self):
        self.assertEqual(self.r.resolve("SIPHO.MOKOENA@GMAIL.COM").user_id, "user_36")

    def test_oldest_historical_email_resolves_with_full_identifier_set(self):
        i = self.r.resolve("abena.o189491@zoho.com")
        self.assertEqual(i.user_id, "user_35")
        self.assertEqual(i.emails, {"abena.o189491@zoho.com", "abena.o189466@zoho.com", "abena.o1894@zoho.com"})
        self.assertIn(hashlib.sha256(b"abena.o189491@zoho.com").hexdigest(), i.email_hashes)
        self.assertTrue(i.phones and all(p.isdigit() for p in i.phones))

    def test_look_alike_does_not_resolve(self):
        self.assertIsNone(self.r.resolve("g.silva76.jr@gmail.com"))

    def test_every_eval_request_resolves(self):
        reqs = data.load_requests(DATA / "deletion_requests.csv")
        self.assertEqual(sum(self.r.resolve(q["email"]) is not None for q in reqs), 518)

    def test_identifier_matching_is_exact(self):
        i = self.r.resolve("SIPHO.MOKOENA@GMAIL.COM")
        self.assertTrue(i.matches("sipho.mokoena@gmail.com"))
        self.assertFalse(i.matches("sipho.mokoena.jr@gmail.com"))


class Intent(unittest.TestCase):
    def test_all_labeled_samples_are_deletion(self):
        for q in data.load_requests(DATA / "sample_deletion_requests.csv"):
            self.assertEqual(intent.classify_rules(q["request_text"]).label, "DELETION", q["case_id"])

    def test_eval_non_deletion_set(self):
        reqs = data.load_requests(DATA / "deletion_requests.csv")
        got = {q["case_id"] for q in reqs if intent.classify_rules(q["request_text"]).label == "NOT_DELETION"}
        self.assertEqual(got, EVAL_NON_DELETION)

    def test_negation_and_scope_cues(self):
        for text, want in [
            ("Please delete my account.", "DELETION"),
            ("Please remove me from marketing lists only.", "NOT_DELETION"),
            ("I am not asking for deletion, just stop the emails.", "NOT_DELETION"),
            ("Bitte löschen Sie mein Konto.", "DELETION"),
            ("What data do you hold about me?", "NOT_DELETION"),
        ]:
            self.assertEqual(intent.classify_rules(text).label, want, text)


class Writer(unittest.TestCase):
    def test_numeric_order_compact_json_and_newlines(self):
        p = Path(tempfile.mkdtemp()) / "o.csv"
        step = {"step_no": 1, "phase": "VERIFICATION", "system_id": "s", "resource_id": "r",
                "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "e"}
        writer.write(p, [("case_100", "COMPLETE", [step]), ("case_33", "NOT_APPLICABLE", [])])
        raw = p.read_bytes()
        self.assertNotIn(b"\r", raw)
        rows = list(csv.reader(raw.decode().splitlines()))
        self.assertEqual([r[0] for r in rows[1:]], ["case_33", "case_100"])
        self.assertEqual(rows[2][2], '[{"step_no":1,"phase":"VERIFICATION","system_id":"s","resource_id":"r",'
                                     '"operation":"VERIFY_RECORD_ABSENT","state":"ABSENT","evidence_id":"e"}]')


class BaselineCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(CODE / "main.py"), *args], capture_output=True, text=True, cwd=ROOT)

    def test_sample_run_passes_the_gate(self):
        out = Path(tempfile.mkdtemp()) / "pred.csv"
        p = self._run("--requests", str(DATA / "sample_deletion_requests.csv"), "--out", str(out))
        self.assertEqual(p.returncode, 0, p.stderr)
        g = subprocess.run([sys.executable, str(CODE / "evaluation" / "main.py"), "contract", "--file", str(out),
                            "--requests", str(DATA / "sample_deletion_requests.csv")], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(g.returncode, 0, g.stdout)

    def test_report_counts(self):
        p = self._run("--report")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("intent: 508 DELETION / 10 NOT_DELETION", p.stdout)
        self.assertIn("identity: 518/518 resolved", p.stdout)
