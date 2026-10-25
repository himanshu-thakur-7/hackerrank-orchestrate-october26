"""T05 SQL loader: typed failover/primary tables, inventory snapshots (snapshot_scope), and generic
customer_data_* tables with JSON record blobs. Fixtures are verbatim lines from real dataset files
(the generic one stitches verbatim INSERT lines from three snapshots under one schema).
"""

import unittest
from pathlib import Path
from _path import DATA  # noqa: F401
from ghostaudit import loaders
from ghostaudit.store import Coverage, EvidenceFile, EvidenceStore, Observation

FIX = Path(__file__).resolve().parent / "fixtures"


def load(name, fid="F1", cap="2026-09-21T10:00:00Z"):
    return loaders.load_bytes(fid, cap, (FIX / name).read_bytes())


def by_res(r):
    out = {}
    for o in r.observations:
        out.setdefault(o.resource_id, []).append(o)
    return out


class TypedFailover(unittest.TestCase):
    def setUp(self):
        self.r = load("sql_failover_excerpt.sql", cap="2026-09-02T23:00:00Z")

    def test_signature_and_replica_only_row(self):
        self.assertEqual(self.r.signature, "sql")
        o = by_res(self.r)["account_005"]
        self.assertEqual(
            o,
            [
                Observation(
                    "F1",
                    "2026-09-02T22:45:00Z",
                    "account_service",
                    "account_005",
                    "customer_profiles_failover_replica",
                    "PRESENT",
                    category="USER_PROFILE",
                    pii_fields=("name", "email", "phone"),
                    identifiers=("+212 6 48 27 15 93", "leila.haddad@yahoo.com", "user_05"),
                    locator="line 13",
                    attrs=(("account_status", "ACTIVE"),),
                )
            ],
        )
        self.assertEqual(len(by_res(self.r)["account_8741"]), 2)  # present in both tables

    def test_whole_table_dump_gives_coverage_and_drift_is_visible_in_the_store(self):
        self.assertEqual(
            sorted((c.system_id, c.table) for c in self.r.coverage),
            [
                ("account_service", "customer_profiles_failover_replica"),
                ("account_service", "customer_profiles_primary"),
            ],
        )
        st = EvidenceStore(
            files=[EvidenceFile("F1", "x.sql", "t", "2026-09-02T23:00:00Z")],
            observations=self.r.observations,
            coverage=self.r.coverage,
        ).as_of("2026-09-08T13:40:00Z")
        self.assertEqual(
            st.state("account_service", "account_005").state, "PRESENT"
        )  # replica drift
        self.assertEqual(
            st.state("account_service", "account_001").state, "ABSENT"
        )  # covered, not listed


class Inventory(unittest.TestCase):
    def setUp(self):
        self.r = load("sql_inventory_excerpt.sql", cap="2026-09-16T08:37:39Z")

    def test_coverage_only_for_systems_in_snapshot_scope(self):
        self.assertEqual(
            sorted((c.system_id, c.table, c.captured_at) for c in self.r.coverage),
            [
                ("account_service", "customer_profiles", "2026-09-16T08:37:39Z"),
                ("analytics_platform", "customer_analytics_profiles", "2026-09-16T08:37:39Z"),
            ],
        )

    def test_typed_rows(self):
        o = {k: v[0] for k, v in by_res(self.r).items()}
        a = o["account_9079"]
        self.assertEqual(
            (
                a.state,
                a.category,
                a.pii_fields,
                a.identifiers,
                dict(a.attrs)["account_status"],
                a.locator,
            ),
            (
                "PRESENT",
                "USER_PROFILE",
                ("email",),
                ("rafael.r9464@outlook.com",),
                "DELETION_PENDING",
                "line 14",
            ),
        )
        self.assertEqual(
            (o["backup_4978"].state, o["backup_4978"].identifiers),
            ("RESTORABLE", ("k.appiah88@gmail.com",)),
        )
        self.assertEqual(o["data_flow_2406"].state, "ACTIVE")
        self.assertEqual(
            (o["audit_record_1738"].category, o["audit_record_1738"].identifiers),
            ("SECURITY_AUDIT_LOG", ("user_68",)),
        )
        s = o["support_6334"]
        self.assertEqual(
            (s.system_id, s.pii_fields, s.identifiers, s.observed_at),
            ("support_platform", (), ("user_62",), "2026-09-16T07:51:34Z"),
        )


class GenericBlobs(unittest.TestCase):
    def setUp(self):
        self.r = load("sql_generic_excerpt.sql")

    def test_blob_rows_get_system_collection_category_and_owner(self):
        o = {k: v[0] for k, v in by_res(self.r).items()}
        a = o["account_994"]
        self.assertEqual(
            (a.table, a.system_id, a.category, a.pii_fields, a.locator, a.observed_at),
            (
                "customer_data_read_replica",
                "account_service",
                "USER_PROFILE",
                ("name", "email", "phone"),
                "line 23",
                "2026-09-21T10:00:00Z",
            ),
        )
        self.assertIn("user_53", a.identifiers)
        m = o["support_3772"]
        self.assertEqual(
            (m.category, m.pii_fields), ("SUPPORT_MESSAGE", ("email",))
        )  # email inside message_text
        self.assertEqual(m.identifiers, ("mansour.yasmine@gmail.com", "user_254"))
        att = o["support_8903"]
        self.assertEqual(
            (att.category, att.identifiers, dict(att.attrs)["ticket_id"]),
            ("SUPPORT_ATTACHMENT", ("ana-varga@proton.me",), "CS-7903"),
        )

    def test_generic_coverage_is_per_system_present_in_each_dumped_table(self):
        self.assertEqual(
            sorted((c.system_id, c.table) for c in self.r.coverage),
            [
                ("account_service", "customer_data_read_replica"),
                ("analytics_platform", "customer_data_primary"),
                ("support_platform", "customer_data_primary"),
            ],
        )

    def test_unknown_table_is_reported_not_skipped(self):
        raw = b"CREATE TABLE mystery (resource_id TEXT, x TEXT);\nINSERT INTO mystery VALUES('account_1','y');\n"
        r = loaders.load_bytes("F2", "2026-01-01T00:00:00Z", raw)
        self.assertEqual(r.observations, [])
        self.assertEqual([u.reason for u in r.unparsed], ["unknown table 'mystery' (1 row)"])
