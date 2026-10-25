"""The dataset seam: a tiny dataset directory through Engine.from_dataset, audit and explain.

The directory has the real file layout (manifest, activity, identities, audit log, rules,
requests) and two shift-handover files: one captured before the audit that still shows the
account, and one captured after the audit that says it is gone (ADR 0002: it must not count).
Expected rows are worked out by hand from deletion_rules.csv (rule_01: USER_PROFILE -> DELETE).
"""

import csv
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from _path import DATA

from ghostaudit import explain
from ghostaudit.engine import Engine
from ghostaudit.intent import classify_rules

EMAIL = "ava.example@example.org"
AUDIT_AT = "2026-09-30T12:00:00Z"


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def tiny_dataset(root):
    """Write the tiny dataset under `root` and return its requests by case id."""
    ev = root / "evidence" / "documents"
    ev.mkdir(parents=True)
    (ev / "handover_a.txt").write_text(
        "Shift handover\n"
        f"- 2026-09-10T09:00:00Z | account_service | account_1 | USER_PROFILE | FOUND | {EMAIL}\n",
        encoding="utf-8",
    )
    (ev / "handover_late.txt").write_text(
        "Shift handover\n"
        "- 2026-10-10T09:00:00Z | account_service | account_1 | USER_PROFILE | NOT_FOUND | "
        f"{EMAIL}\n",
        encoding="utf-8",
    )
    _write_csv(
        root / "evidence_files.csv",
        ["file_id", "file_path", "origin", "captured_at"],
        [
            ["ev_a", "evidence/documents/handover_a.txt", "ops", "2026-09-10T10:00:00Z"],
            ["ev_late", "evidence/documents/handover_late.txt", "ops", "2026-10-10T10:00:00Z"],
        ],
    )
    _write_csv(
        root / "system_activity.csv",
        [
            "activity_id",
            "event_time",
            "event_type",
            "source_system",
            "target_system",
            "resource_id",
            "reported_result",
            "details",
        ],
        [],
    )
    _write_csv(
        root / "user_identities.csv",
        ["user_id", "name", "email", "phone", "email_hash", "updated_at"],
        [
            [
                "user_1",
                "Ava Example",
                EMAIL,
                "+44 20 7946 0000",
                hashlib.sha256(EMAIL.encode()).hexdigest(),
                "2026-01-01T00:00:00Z",
            ]
        ],
    )
    _write_csv(
        root / "user_audit_log.csv",
        ["audit_id", "user_id", "event_time", "field_name", "old_value", "new_value"],
        [],
    )
    shutil.copyfile(DATA / "deletion_rules.csv", root / "deletion_rules.csv")
    base = ["2026-09-01T00:00:00Z", "COMPLETE", "2026-09-02T00:00:00Z", AUDIT_AT]
    requests = [
        ["c1", EMAIL, *base, "Please delete my account and all my data."],
        ["c2", EMAIL, *base, "Please send me a copy of my data."],
        ["c3", "nobody@example.org", *base, "Please delete my account."],
    ]
    header = ["case_id", "email", "requested_at", "reported_status", "reported_at", "audit_at"]
    _write_csv(root / "deletion_requests.csv", header + ["request_text"], requests)
    return {r[0]: dict(zip(header + ["request_text"], r, strict=True)) for r in requests}


class DatasetSeam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ghostaudit_seam_"))
        cls.requests = tiny_dataset(cls.tmp)
        cls.engine = Engine.from_dataset(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def audit(self, case_id):
        q = self.requests[case_id]
        return self.engine.audit(q, classify_rules(q["request_text"]))

    def test_a_record_still_shown_before_the_audit_is_incomplete(self):
        case_id, status, steps = self.audit("c1")
        self.assertEqual((case_id, status), ("c1", "INCOMPLETE"))
        self.assertEqual(
            [(s["step_no"], s["operation"], s["resource_id"], s["evidence_id"]) for s in steps],
            [
                (1, "REPORT_REMAINING_RECORD", "account_1", "ev_a"),
                (2, "DELETE_RECORD", "account_1", ""),
                (3, "VERIFY_RECORD_ABSENT", "account_1", ""),
            ],
        )

    def test_a_non_deletion_request_and_an_unknown_email(self):
        self.assertEqual(self.audit("c2")[1:], ("NOT_APPLICABLE", []))
        self.assertEqual(self.audit("c3")[1:], ("INCOMPLETE", []))
        q = self.requests["c3"]
        a = self.engine.assess(q, classify_rules(q["request_text"]))
        self.assertEqual(a.log, ["UNRESOLVED_SUBJECT"])

    def test_explain_shows_the_cutoff_view_and_every_decision(self):
        q = self.requests["c1"]
        text = explain.render(self.engine, q, classify_rules(q["request_text"]))
        for expected in (
            f"CASE c1  email={EMAIL}  audit_at={AUDIT_AT}",
            "intent: DELETION",
            "subject: user_1",
            "visible files at audit_at: 1 of 2",
            "link   ev_a line 2",
            "state  PRESENT by observation ev_a line 2",
            "rule=rule_01 action=DELETE -> violation",
            "REPORT_REMAINING_RECORD",
        ):
            self.assertIn(expected, text)
        self.assertNotIn("ev_late", text)  # captured after audit_at: not in the view (ADR 0002)


if __name__ == "__main__":
    unittest.main()
