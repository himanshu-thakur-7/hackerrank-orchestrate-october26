"""T03 Evidence Store: models, indexes, and the as_of(cutoff) view (ADR 0002, 0003, 0006).

Facts are modelled on real dataset situations (named in comments) but built synthetically here;
loaders that read the real files arrive in T04-T07.
"""
import unittest
from _path import DATA  # noqa: F401  (sets sys.path)
from ghostaudit.store import ActivityEvent, Coverage, EvidenceFile, EvidenceStore, Link, Observation


def f(fid, cap):
    return EvidenceFile(fid, f"evidence/x/{fid}.dat", "test", cap)


def obs(fid, at, sys_, res, state, table="t", ids=(), pii=(), cat=None, loc=""):
    return Observation(fid, at, sys_, res, table, state, category=cat, pii_fields=tuple(pii), identifiers=tuple(ids), locator=loc)


class CutoffView(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(
            files=[f("F_early", "2026-09-15T11:44:55Z"), f("F_at", "2026-10-01T12:00:00Z"), f("F_late", "2026-10-01T12:00:01Z")],
            observations=[
                obs("F_early", "2026-09-15T10:00:00Z", "search_service", "search_1", "PRESENT", ids=("a@x.com",)),
                obs("F_at", "2026-10-01T12:00:00Z", "search_service", "search_2", "PRESENT", ids=("A@X.COM",)),
                obs("F_late", "2026-10-01T12:00:01Z", "search_service", "search_1", "ABSENT"),
            ],
            activity=[ActivityEvent("activity_1", "2026-10-01T11:00:00Z", "DELETE_RECORD", "deletion_worker", "search_service", "search_1", "SUCCESS"),
                      ActivityEvent("activity_2", "2026-10-01T13:00:00Z", "DELETE_RECORD", "deletion_worker", "search_service", "search_2", "SUCCESS")],
        )
        self.view = self.store.as_of("2026-10-01T12:00:00Z")

    def test_file_captured_after_cutoff_is_invisible(self):
        # like evidence_02 (09-17) for a 09-15 audit: its contradicting observation must not count
        self.assertEqual([o.file_id for o in self.view.observations("search_1")], ["F_early"])
        self.assertEqual(self.view.state("search_service", "search_1").state, "PRESENT")

    def test_cutoff_is_inclusive(self):
        # like evidence_03 captured exactly at case_11's audit_at 2026-10-01T12:00:00Z
        self.assertEqual([o.file_id for o in self.view.observations("search_2")], ["F_at"])

    def test_activity_is_cut_too_and_never_sets_state(self):
        self.assertEqual([a.activity_id for a in self.view.activity()], ["activity_1"])
        # a SUCCESS delete claim does not make search_1 ABSENT (ADR 0003)
        self.assertEqual(self.view.state("search_service", "search_1").state, "PRESENT")

    def test_identifier_index_is_case_insensitive_and_exact(self):
        self.assertEqual(self.view.resources_with_identifier({"a@x.com"}), {("search_service", "search_1"), ("search_service", "search_2")})
        self.assertEqual(self.view.resources_with_identifier({"a.jr@x.com"}), set())


class StateReconstruction(unittest.TestCase):
    def test_latest_observation_inside_one_file_wins(self):
        # like evidence_30: account_2088 rows=0/404 on 05-14, then rows=1/200 on 05-16, same file
        st = EvidenceStore(files=[f("F", "2026-05-16T11:58:25Z")], observations=[
            obs("F", "2026-05-14T11:58:45Z", "account_service", "account_2088", "ABSENT", loc="line 92"),
            obs("F", "2026-05-16T11:58:23Z", "account_service", "account_2088", "PRESENT", loc="line 109")])
        s = st.as_of("2026-06-01T00:00:00Z").state("account_service", "account_2088")
        self.assertEqual((s.state, s.file_id, s.locator), ("PRESENT", "F", "line 109"))

    def test_coverage_proves_absence_when_resource_is_not_listed(self):
        # like evidence_54: account_service tables cover the store; account_001 is not listed
        st = EvidenceStore(files=[f("F", "2026-09-02T23:00:00Z")],
                           observations=[obs("F", "2026-09-02T22:45:00Z", "account_service", "account_9", "PRESENT", table="profiles_primary")],
                           coverage=[Coverage("F", "2026-09-02T23:00:00Z", "account_service", "profiles_primary")])
        s = st.as_of("2026-09-03T11:30:00Z").state("account_service", "account_001")
        self.assertEqual((s.state, s.file_id, s.basis), ("ABSENT", "F", "coverage"))

    def test_replica_presence_beats_primary_absence_in_the_same_snapshot(self):
        # like evidence_54 account_005: missing from _primary, present in _failover_replica
        st = EvidenceStore(files=[f("F", "2026-09-02T23:00:00Z")],
                           observations=[obs("F", "2026-09-02T22:45:00Z", "account_service", "account_005", "PRESENT", table="profiles_failover_replica")],
                           coverage=[Coverage("F", "2026-09-02T23:00:00Z", "account_service", "profiles_primary"),
                                     Coverage("F", "2026-09-02T23:00:00Z", "account_service", "profiles_failover_replica")])
        self.assertEqual(st.as_of("2026-09-08T13:40:00Z").state("account_service", "account_005").state, "PRESENT")

    def test_no_observation_and_no_coverage_is_unproven(self):
        st = EvidenceStore(files=[f("F", "2026-09-02T23:00:00Z")])
        self.assertIsNone(st.as_of("2026-09-08T00:00:00Z").state("account_service", "account_404"))

    def test_newer_file_overrides_older_file(self):
        st = EvidenceStore(files=[f("A", "2026-09-01T00:00:00Z"), f("B", "2026-09-10T00:00:00Z")], observations=[
            obs("A", "2026-09-01T00:00:00Z", "search_service", "search_9", "PRESENT"),
            obs("B", "2026-09-10T00:00:00Z", "search_service", "search_9", "ABSENT")])
        self.assertEqual(st.as_of("2026-09-12T00:00:00Z").state("search_service", "search_9").state, "ABSENT")
        self.assertEqual(st.as_of("2026-09-05T00:00:00Z").state("search_service", "search_9").state, "PRESENT")


class Links(unittest.TestCase):
    def test_links_respect_cutoff_and_contradiction_status(self):
        st = EvidenceStore(links=[Link("marketing_001", "user_09", "CATALOG_CLAIM", "activity_4008", "2026-09-16T07:27:01Z", "CONTRADICTED"),
                                  Link("account_5762", "user_11", "CATALOG_CLAIM", "activity_4000", "2026-09-26T11:07:01Z", "OK")])
        v = st.as_of("2026-09-20T00:00:00Z")
        self.assertEqual(v.links_for_user("user_09"), [])            # contradicted links are never returned (ADR 0005)
        self.assertEqual(v.links_for_user("user_11"), [])            # not yet visible at this cutoff
        self.assertEqual([l.resource_id for l in st.as_of("2026-09-27T00:00:00Z").links_for_user("user_11")], ["account_5762"])
