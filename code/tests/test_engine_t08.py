"""T08 state reconstruction + policy at the engine seam: Engine.assess(request, intent).resources.
One test per edge case in docs/02_DATA_NOTES.md (scenarios are synthetic copies of the named records)."""
import unittest
from _world import DELETE, NEW, OLD, OLD_HASH, Coverage, act, engine, ob, request


def res(e, req=None):
    return {(r.system_id, r.resource_id): r for r in e.assess(req or request(), DELETE).resources}


class Discovery(unittest.TestCase):
    def test_resources_are_found_by_any_exact_identifier_current_or_historical(self):
        e = engine([("F", "2026-09-15T11:00:00Z")], [
            ob("F", "2026-09-15T10:00:00Z", "search_service", "search_1", ids=(NEW.upper(),)),
            ob("F", "2026-09-15T10:00:00Z", "search_service", "search_2", ids=(OLD,)),
            ob("F", "2026-09-15T10:00:00Z", "account_service", "account_3", ids=("+212 6 48 27 15 93",)),
            ob("F", "2026-09-15T10:00:00Z", "security_service", "audit_record_4", ids=("user_1",)),
            ob("F", "2026-09-15T10:00:00Z", "search_service", "search_9", ids=("leila.old.jr@example.com",)),   # look-alike
            ob("F", "2026-09-15T10:00:00Z", "search_service", "search_8", ids=("other@example.com",))])
        self.assertEqual(sorted(res(e)), [("account_service", "account_3"), ("search_service", "search_1"),
                                          ("search_service", "search_2"), ("security_service", "audit_record_4")])

    def test_a_resource_named_only_in_a_post_cutoff_file_is_not_discovered(self):
        # case_53 / evidence_02: the subject appears only in a file captured after audit_at
        e = engine([("LATE", "2026-09-17T12:00:00Z")], [ob("LATE", "2026-09-09T12:00:00Z", "account_service", "account_1", ids=(NEW,))])
        a = e.assess(request(), DELETE)
        self.assertEqual(a.resources, [])
        self.assertIn("UNRESOLVED_LINK(primary account: no grounded link yet, T10)", a.log)


class StateAtAuditTime(unittest.TestCase):
    def test_post_cutoff_snapshot_cannot_change_the_state(self):
        # case_27: evidence_92 (09-15) account_3866 404; evidence_02 (09-17) shows it ACTIVE again
        e = engine([("E92", "2026-09-15T11:44:55Z"), ("E02", "2026-09-17T12:00:00Z")], [
            ob("E92", "2026-09-15T11:44:55Z", "account_service", "account_3866", "ABSENT", ids=(NEW,)),
            ob("E02", "2026-09-15T09:00:00Z", "account_service", "account_3866", "PRESENT", ids=(NEW,))])
        r = res(e)[("account_service", "account_3866")]
        self.assertEqual((r.state.state, r.state.file_id, r.treatment.kind), ("ABSENT", "E92", "compliant"))

    def test_replica_only_row_is_present_under_the_logical_system(self):
        # case_05 / evidence_54: account_005 gone from customer_profiles_primary, still in _failover_replica
        e = engine([("E54", "2026-09-02T10:00:00Z")], [
            ob("E54", "2026-09-02T10:00:00Z", "account_service", "account_005", "PRESENT", ids=(NEW,), pii=("name", "phone"),
               table="customer_profiles_failover_replica", loc="line 13")],
            coverage=[Coverage("E54", "2026-09-02T10:00:00Z", "account_service", "customer_profiles_primary")])
        r = res(e)[("account_service", "account_005")]
        self.assertEqual((r.state.state, r.category, r.treatment.finding), ("PRESENT", "USER_PROFILE", "REPORT_REMAINING_RECORD"))

    def test_absence_by_omission_from_a_later_covering_snapshot(self):
        # ADR 0014: the omission proves ABSENT only because nothing visible shows the record present
        e = engine([("A", "2026-09-01T00:00:00Z"), ("B", "2026-09-10T00:00:00Z")], [
            ob("A", "2026-09-01T00:00:00Z", "account_service", "account_7", "ABSENT", ids=(NEW,))],
            coverage=[Coverage("B", "2026-09-10T00:00:00Z", "account_service", "customer_profiles")])
        r = res(e)[("account_service", "account_7")]
        self.assertEqual((r.state.state, r.state.basis, r.state.file_id), ("ABSENT", "coverage", "B"))

    def test_older_sighting_survives_a_later_omission_and_is_flagged(self):
        e = engine([("A", "2026-09-01T00:00:00Z"), ("B", "2026-09-10T00:00:00Z")], [
            ob("A", "2026-09-01T00:00:00Z", "search_service", "search_7", "PRESENT", ids=(NEW,))],
            coverage=[Coverage("B", "2026-09-10T00:00:00Z", "search_service", "search_documents")])
        r = res(e)[("search_service", "search_7")]
        self.assertEqual((r.state.state, r.later_omissions), ("PRESENT", ("B",)))


class PolicyEdgeCases(unittest.TestCase):
    def test_redacted_tombstone(self):
        # evidence_51 line 17 tombstone_440: subject_reference user_541, every direct identifier null
        e = engine([("E51", "2026-09-15T12:00:00Z")], [
            ob("E51", "2026-09-15T12:00:00Z", "identity_service", "tombstone_440", ids=("user_1",), cat="ACCOUNT_TOMBSTONE",
               attrs=(("account_status", "DELETED"),))])
        r = res(e)[("identity_service", "tombstone_440")]
        self.assertEqual((r.category, r.category_source, r.treatment.kind, r.treatment.verification),
                         ("ACCOUNT_TOMBSTONE", "tag", "compliant", "VERIFY_RECORD_REDACTED"))

    def test_historical_hash_analytics_contact_is_a_secondary_identifier_to_delete(self):
        # case_12 / evidence_01 line 92: analytics_9914 keyed by the sha256 of the subject's OLD email
        e = engine([("E01", "2026-09-15T11:59:39Z")], [
            ob("E01", "2026-09-15T11:58:26Z", "analytics_platform", "analytics_9914", ids=(OLD_HASH,),
               attrs=(("event", "contact_lookup_completed"), ("rows", "1")), loc="line 92")])
        r = res(e)[("analytics_platform", "analytics_9914")]
        self.assertEqual((r.category, r.treatment.finding, r.treatment.remediation),
                         ("SECONDARY_IDENTIFIER", "REPORT_REMAINING_RECORD", "DELETE_RECORD"))

    def test_enabled_flow_and_restorable_backup(self):
        # case_15 data_flow_9846 enabled=true; case_17 backup_3245 eligible=true deletion_block=false
        e = engine([("E01", "2026-09-15T11:59:39Z")], [
            ob("E01", "2026-09-15T11:58:11Z", "integration_service", "data_flow_9846", "ACTIVE", ids=(NEW,)),
            ob("E01", "2026-09-15T11:54:41Z", "backup_service", "backup_3245", "RESTORABLE", ids=(NEW,))])
        r = res(e)
        self.assertEqual(r[("integration_service", "data_flow_9846")].treatment.finding, "REPORT_ACTIVE_DATA_FLOW")
        self.assertEqual(r[("backup_service", "backup_3245")].treatment.finding, "REPORT_RESTORE_RISK")

    def test_deletion_pending_account_is_remaining(self):
        # ADR 0010 / evidence_63 line 19 account_3626 DELETION_PENDING with the email still on the row
        e = engine([("E63", "2026-09-15T08:00:00Z")], [
            ob("E63", "2026-09-15T08:00:00Z", "account_service", "account_3626", ids=(NEW,), pii=("email",),
               attrs=(("account_status", "DELETION_PENDING"),))],
            activity=[act("activity_1", "2026-01-20T00:00:00Z", "DELETE_RECORD", "account_service", "account_3626")])
        r = res(e)[("account_service", "account_3626")]
        self.assertEqual((r.state.state, r.treatment.kind), ("PRESENT", "violation"))

    def test_pre_audit_legal_hold_is_retained_and_a_post_audit_one_is_invisible(self):
        # ADR 0011 / evidence_47 line 30 legal_hold_2227
        e = engine([("E47", "2026-09-10T00:00:00Z"), ("LATE", "2026-09-20T00:00:00Z")], [
            ob("E47", "2026-09-10T00:00:00Z", "legal_service", "legal_hold_2227", ids=("user_1",), cat="LEGAL_HOLD_RECORD"),
            ob("LATE", "2026-09-20T00:00:00Z", "legal_service", "legal_hold_9", ids=("user_1",), cat="LEGAL_HOLD_RECORD")])
        r = res(e)
        self.assertEqual(r[("legal_service", "legal_hold_2227")].treatment.verification, "VERIFY_RECORD_PRESENT")
        self.assertNotIn(("legal_service", "legal_hold_9"), r)

    def test_untagged_support_uses_the_pre_audit_activity_claim(self):
        # case_10 support_002: no tag, activity_3596 DELETE_RECORD -> attachment -> DELETE
        e = engine([("E61", "2026-09-17T22:00:19Z")], [
            ob("E61", "2026-09-17T22:00:05Z", "support_platform", "support_002", ids=(NEW,), table="support_replica.log",
               attrs=(("event", "contact_query_completed"),))],
            activity=[act("activity_3596", "2026-09-10T00:00:00Z", "DELETE_RECORD", "support_platform", "support_002"),
                      act("activity_late", "2026-09-19T00:00:00Z", "REDACT_RECORD", "support_platform", "support_002")])
        r = res(e, request(audit_at="2026-09-18T12:25:00Z"))[("support_platform", "support_002")]
        self.assertEqual((r.category, r.category_source, r.treatment.finding), ("SUPPORT_ATTACHMENT", "activity", "REPORT_REMAINING_RECORD"))


if __name__ == "__main__":
    unittest.main()
