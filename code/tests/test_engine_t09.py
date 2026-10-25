"""T09 verdict + step planner at the engine seam: Engine.audit(request, intent) -> (case_id, status, steps).
One test per edge case in docs/02_DATA_NOTES.md; expected rows are written out by hand from the
matching sample_output.csv patterns (case_05, 12, 15, 17, 27, 31, 32), not recomputed."""
import unittest
from _world import DELETE, NEW, OLD_HASH, Coverage, act, engine, ob, request
from ghostaudit.intent import Intent


def step(n, phase, op, sys_, res, state, ev=""):
    return {"step_no": n, "phase": phase, "system_id": sys_, "resource_id": res, "operation": op, "state": state, "evidence_id": ev}


class Verdict(unittest.TestCase):
    def test_non_deletion_request_is_not_applicable(self):
        e = engine([("F", "2026-09-01T00:00:00Z")])
        self.assertEqual(e.audit(request(), Intent("NOT_DELETION", "export only", "rules")), ("case_900", "NOT_APPLICABLE", []))

    def test_replica_only_row_makes_the_case_incomplete(self):
        # case_05: REPORT_REMAINING_RECORD cites the snapshot; remediation and verification are uncited
        e = engine([("E54", "2026-09-02T10:00:00Z")], [
            ob("E54", "2026-09-02T10:00:00Z", "account_service", "account_005", ids=(NEW,), pii=("name",), table="customer_profiles_failover_replica")],
            coverage=[Coverage("E54", "2026-09-02T10:00:00Z", "account_service", "customer_profiles_primary")])
        self.assertEqual(e.audit(request(audit_at="2026-09-08T13:40:00Z"), DELETE), ("case_900", "INCOMPLETE", [
            step(1, "FINDING", "REPORT_REMAINING_RECORD", "account_service", "account_005", "PRESENT", "E54"),
            step(2, "REMEDIATION", "DELETE_RECORD", "account_service", "account_005", "ABSENT"),
            step(3, "VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_005", "ABSENT")]))

    def test_post_cutoff_snapshot_is_ignored_and_complete_cites_the_proving_file(self):
        # case_27: evidence_92 404 at 09-15; evidence_02 (09-17) shows the account back; audit 09-15T12:00
        e = engine([("E92", "2026-09-15T11:44:55Z"), ("E02", "2026-09-17T12:00:00Z")], [
            ob("E92", "2026-09-15T11:44:55Z", "account_service", "account_3866", "ABSENT", ids=(NEW,)),
            ob("E92", "2026-09-15T11:44:55Z", "security_service", "audit_record_3830", ids=("user_1",)),
            ob("E02", "2026-09-17T12:00:00Z", "account_service", "account_3866", ids=(NEW,), pii=("email",))])
        self.assertEqual(e.audit(request(), DELETE), ("case_900", "COMPLETE", [
            step(1, "VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_3866", "ABSENT", "E92"),
            step(2, "VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_3830", "PRESENT", "E92")]))

    def test_absence_by_omission_cites_the_covering_file(self):
        e = engine([("A", "2026-09-01T00:00:00Z"), ("B", "2026-09-10T00:00:00Z")], [
            ob("A", "2026-09-01T00:00:00Z", "account_service", "account_7", "ABSENT", ids=(NEW,))],
            coverage=[Coverage("B", "2026-09-10T00:00:00Z", "account_service", "customer_profiles")])
        self.assertEqual(e.audit(request(), DELETE)[1:], ("COMPLETE", [
            step(1, "VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_7", "ABSENT", "B")]))

    def test_redacted_tombstone_complete_and_exposed_tombstone_incomplete(self):
        # case_31 tombstone_440 (all identifiers null) vs case_32 tombstone_9178 (name, email, phone, hash)
        ok = engine([("E51", "2026-09-15T12:00:00Z")], [
            ob("E51", "2026-09-15T12:00:00Z", "identity_service", "tombstone_440", ids=("user_1",), cat="ACCOUNT_TOMBSTONE")])
        self.assertEqual(ok.audit(request(), DELETE)[1:], ("COMPLETE", [
            step(1, "VERIFICATION", "VERIFY_RECORD_REDACTED", "identity_service", "tombstone_440", "REDACTED", "E51")]))
        bad = engine([("E51", "2026-09-15T12:00:00Z")], [
            ob("E51", "2026-09-15T12:00:00Z", "identity_service", "tombstone_9178", ids=("user_1", NEW), cat="ACCOUNT_TOMBSTONE",
               pii=("name", "email", "phone", "email_hash"))])
        self.assertEqual(bad.audit(request(), DELETE)[1:], ("INCOMPLETE", [
            step(1, "FINDING", "REPORT_EXPOSED_PII", "identity_service", "tombstone_9178", "PRESENT", "E51"),
            step(2, "REMEDIATION", "REDACT_RECORD", "identity_service", "tombstone_9178", "REDACTED"),
            step(3, "VERIFICATION", "VERIFY_RECORD_REDACTED", "identity_service", "tombstone_9178", "REDACTED")]))

    def test_historical_hash_contact_flow_and_backup_in_one_plan_sorted_by_operation(self):
        # case_12 analytics_9914 + case_15 data_flow_9846 + case_17 backup_3245 + a 404 account and a retained audit record
        e = engine([("E01", "2026-09-15T11:59:39Z")], [
            ob("E01", "2026-09-15T11:51:19Z", "account_service", "account_9797", "ABSENT", ids=(NEW,)),
            ob("E01", "2026-09-15T11:58:26Z", "analytics_platform", "analytics_9914", ids=(OLD_HASH,), attrs=(("event", "contact_lookup_completed"),)),
            ob("E01", "2026-09-15T11:58:11Z", "integration_service", "data_flow_9846", "ACTIVE", ids=(NEW,)),
            ob("E01", "2026-09-15T11:54:41Z", "backup_service", "backup_3245", "RESTORABLE", ids=(NEW,)),
            ob("E01", "2026-09-15T11:55:40Z", "security_service", "audit_record_2945", ids=("user_1",))])
        self.assertEqual(e.audit(request(), DELETE)[1:], ("INCOMPLETE", [
            step(1, "FINDING", "REPORT_REMAINING_RECORD", "analytics_platform", "analytics_9914", "PRESENT", "E01"),
            step(2, "FINDING", "REPORT_ACTIVE_DATA_FLOW", "integration_service", "data_flow_9846", "ACTIVE", "E01"),
            step(3, "FINDING", "REPORT_RESTORE_RISK", "backup_service", "backup_3245", "ACTIVE", "E01"),
            step(4, "REMEDIATION", "DISABLE_DATA_FLOW", "integration_service", "data_flow_9846", "DISABLED"),
            step(5, "REMEDIATION", "BLOCK_RESTORE", "backup_service", "backup_3245", "BLOCKED"),
            step(6, "REMEDIATION", "DELETE_RECORD", "analytics_platform", "analytics_9914", "ABSENT"),
            step(7, "VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_9797", "ABSENT"),
            step(8, "VERIFICATION", "VERIFY_RECORD_ABSENT", "analytics_platform", "analytics_9914", "ABSENT"),
            step(9, "VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_2945", "PRESENT"),
            step(10, "VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", "integration_service", "data_flow_9846", "DISABLED"),
            step(11, "VERIFICATION", "VERIFY_RESTORE_BLOCKED", "backup_service", "backup_3245", "BLOCKED")]))

    def test_deletion_pending_account_is_reported_remaining(self):
        # ADR 0010: SUCCESS delete claim and reported COMPLETE, but the row is still there
        e = engine([("E63", "2026-09-15T08:00:00Z")], [
            ob("E63", "2026-09-15T08:00:00Z", "account_service", "account_3626", ids=(NEW,), pii=("email",),
               attrs=(("account_status", "DELETION_PENDING"),))],
            activity=[act("activity_1", "2026-01-20T00:00:00Z", "DELETE_RECORD", "account_service", "account_3626")])
        status, steps = e.audit(request(), DELETE)[1:]
        self.assertEqual((status, steps[0]["operation"], steps[0]["evidence_id"]), ("INCOMPLETE", "REPORT_REMAINING_RECORD", "E63"))

    def test_legal_hold_is_verified_present_with_its_file_in_a_complete_case(self):
        e = engine([("E47", "2026-09-10T00:00:00Z")], [
            ob("E47", "2026-09-10T00:00:00Z", "account_service", "account_1", "ABSENT", ids=(NEW,)),
            ob("E47", "2026-09-10T00:00:00Z", "legal_service", "legal_hold_2227", ids=("user_1",), cat="LEGAL_HOLD_RECORD")])
        self.assertEqual(e.audit(request(), DELETE)[1:], ("COMPLETE", [
            step(1, "VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_1", "ABSENT", "E47"),
            step(2, "VERIFICATION", "VERIFY_RECORD_PRESENT", "legal_service", "legal_hold_2227", "PRESENT", "E47")]))


class UnprovenAndNothing(unittest.TestCase):
    def test_unproven_resource_is_a_future_verify_in_incomplete_and_omitted_in_complete(self):
        # ADR 0006 amended: a backup with no restore flag is unproven; activity claims never become findings
        bad = engine([("F", "2026-09-10T00:00:00Z")], [
            ob("F", "2026-09-10T00:00:00Z", "search_service", "search_1", ids=(NEW,)),
            ob("F", "2026-09-10T00:00:00Z", "backup_service", "backup_1", "PRESENT", ids=(NEW,))],
            activity=[act("activity_9", "2026-09-05T00:00:00Z", "BLOCK_RESTORE", "backup_service", "backup_1", "FAILED")])
        status, steps = bad.audit(request(), DELETE)[1:]
        self.assertEqual(status, "INCOMPLETE")
        self.assertIn(step(4, "VERIFICATION", "VERIFY_RESTORE_BLOCKED", "backup_service", "backup_1", "BLOCKED"), steps)
        self.assertFalse([s for s in steps if s["resource_id"] == "backup_1" and s["phase"] != "VERIFICATION"])
        ok = engine([("F", "2026-09-10T00:00:00Z")], [
            ob("F", "2026-09-10T00:00:00Z", "account_service", "account_1", "ABSENT", ids=(NEW,)),
            ob("F", "2026-09-10T00:00:00Z", "backup_service", "backup_1", "PRESENT", ids=(NEW,))])
        a = ok.assess(request(), DELETE)
        self.assertEqual((a.status, [s["resource_id"] for s in a.steps]), ("COMPLETE", ["account_1"]))
        self.assertIn("UNPROVEN(backup_service/backup_1)", a.log)

    def test_nothing_grounded_is_incomplete_with_no_steps_and_logged(self):
        e = engine([("F", "2026-09-10T00:00:00Z")])
        a = e.assess(request(), DELETE)
        self.assertEqual((a.status, a.steps), ("INCOMPLETE", []))
        self.assertIn("NO_GROUNDED_STEP", a.log)


if __name__ == "__main__":
    unittest.main()
