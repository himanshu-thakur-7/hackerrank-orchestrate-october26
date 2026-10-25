"""T06 loaders: snapshot bundles, record-list JSON (registers and collection lists), record_lookup
logs. Fixtures: evidence_51 and evidence_56 verbatim; excerpts re-serialised from real evidence_31
and evidence_36 records; notification_delivery log lines 1-3 verbatim.
"""

import unittest
from pathlib import Path
from _path import DATA  # noqa: F401
from ghostaudit import loaders
from ghostaudit.store import Observation

FIX = Path(__file__).resolve().parent / "fixtures"


def load(name, fid="F1", cap="2026-09-15T12:00:00Z"):
    return loaders.load_bytes(fid, cap, (FIX / name).read_bytes())


def by_res(r):
    return {o.resource_id: o for o in r.observations}


class Bundle(unittest.TestCase):
    def setUp(self):
        self.r = load("bundle_excerpt.json")

    def test_tombstones_and_audit_events(self):
        o = by_res(self.r)
        self.assertEqual(
            o["tombstone_440"],
            Observation(
                "F1",
                "2026-09-15T12:00:00Z",
                "identity_service",
                "tombstone_440",
                "deleted_customer_references",
                "PRESENT",
                category="ACCOUNT_TOMBSTONE",
                pii_fields=(),
                identifiers=("user_541",),
                locator="line 17",
                attrs=(("account_status", "DELETED"),),
            ),
        )
        t = o["tombstone_9178"]
        self.assertEqual(
            (t.pii_fields, t.locator), (("name", "email", "phone", "email_hash"), "line 26")
        )
        self.assertEqual(
            set(t.identifiers),
            {
                "user_542",
                "addo.kofi@gmail.com",
                "+233 24 991 1328",
                "4f4b9c98a05a2dad20e52313cce7809d18c3da544754dcd46d728b0173174b26",
            },
        )
        self.assertEqual(
            (o["audit_record_6909"].category, o["audit_record_6909"].identifiers),
            ("SECURITY_AUDIT_LOG", ("user_541",)),
        )

    def test_every_data_collection_emits_coverage_including_empty_lists(self):
        self.assertEqual(
            sorted((c.system_id, c.table, c.captured_at) for c in self.r.coverage),
            [
                ("account_service", "customer_profiles", "2026-09-15T12:00:00Z"),
                ("identity_service", "deleted_customer_references", "2026-09-15T12:00:00Z"),
                ("security_service", "security_audit_events", "2026-09-15T12:00:00Z"),
            ],
        )

    def test_register_history_inside_a_bundle_is_not_coverage(self):
        r = load("bundle_register_excerpt.json", cap="2026-05-11T11:00:00Z")
        o = by_res(r)
        self.assertEqual(
            (o["account_3785"].observed_at, o["account_3785"].locator),
            ("2026-05-03T11:00:00Z", "line 11"),
        )
        self.assertIn("HYUNWOO.KANG94@GMAIL.COM", o["account_3785"].identifiers)
        self.assertEqual(
            o["account_1015"],
            Observation(
                "F1",
                "2026-05-04T10:00:00Z",
                "account_service",
                "account_1015",
                "support_storage_service.operational_record_history",
                "ABSENT",
                category="USER_PROFILE",
                identifiers=("santos.isabela@gmail.com",),
                locator="line 37",
                attrs=(("status", "NOT_FOUND"),),
            ),
        )
        self.assertEqual(o["search_9252"].state, "PRESENT")
        self.assertEqual(
            [(c.system_id, c.table) for c in r.coverage], [("account_service", "customer_profiles")]
        )


class RecordLists(unittest.TestCase):
    def test_register(self):
        r = load("register_excerpt.json", cap="2026-04-09T12:00:00Z")
        o = by_res(r)
        self.assertEqual(
            o["account_7618"],
            Observation(
                "F1",
                "2026-04-03T12:00:00Z",
                "account_service",
                "account_7618",
                "register",
                "PRESENT",
                category="USER_PROFILE",
                pii_fields=("email",),
                identifiers=("dnakamura7301@gmail.com",),
                locator="line 9",
                attrs=(("status", "FOUND"),),
            ),
        )
        self.assertEqual(o["account_1718"].state, "ABSENT")
        self.assertEqual(r.coverage, [])

    def test_collection_list(self):
        r = load("collection_list_excerpt.json", cap="2026-09-07T09:45:00Z")
        o = by_res(r)
        a = o["analytics_901"]
        self.assertEqual(
            (a.system_id, a.category, a.pii_fields, a.identifiers, a.observed_at, a.locator),
            ("analytics_platform", "ANALYTICS_PROFILE", (), (), "2026-09-07T09:45:00Z", "line 7"),
        )
        self.assertEqual(o["analytics_824"].pii_fields, ("email", "phone", "email_hash"))
        self.assertEqual([u.locator for u in r.unattributed], ["line 7"])
        self.assertEqual(
            [(c.system_id, c.table) for c in r.coverage],
            [("analytics_platform", "customer_analytics_reports")],
        )


class RecordLookupLog(unittest.TestCase):
    def test_quoted_logfmt_lookup_rows(self):
        r = load("record_lookup_excerpt.log", cap="2026-03-15T07:00:00Z")
        self.assertEqual(r.signature, "log:record_lookup")
        o = by_res(r)
        self.assertEqual(
            o["account_022"],
            Observation(
                "F1",
                "2026-03-15T07:00:00Z",
                "account_service",
                "account_022",
                "downstream_delivery_service.record_lookup",
                "ABSENT",
                category="USER_PROFILE",
                identifiers=("zofia-novak@gmail.com",),
                locator="line 1",
                attrs=(("status", "NOT_FOUND"),),
            ),
        )
        self.assertEqual(
            (o["account_1538"].state, o["account_1538"].pii_fields), ("PRESENT", ("email",))
        )
