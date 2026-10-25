"""Policy tables: each action's judge and the action chosen per category (values from deletion_rules)."""

import unittest

from _path import DATA

from ghostaudit import policy


class Judges(unittest.TestCase):
    def test_delete_is_compliant_only_when_absent(self):
        self.assertEqual(policy.JUDGES["DELETE"]("ABSENT", ()), ("compliant", "absent"))
        self.assertEqual(
            policy.JUDGES["DELETE"]("PRESENT", ()), ("violation", "PRESENT, must be absent")
        )

    def test_redact_and_anonymize_keep_the_record_without_identifiers(self):
        for action in ("REDACT", "ANONYMIZE"):
            judge = policy.JUDGES[action]
            self.assertEqual(
                judge("PRESENT", ("email", "phone")), ("violation", "exposes email, phone")
            )
            self.assertEqual(
                judge("PRESENT", ()), ("compliant", "present without direct identifiers")
            )
            self.assertEqual(judge("ABSENT", ()), ("none", "ABSENT, but policy keeps the record"))

    def test_retain_never_plans_a_deletion(self):
        self.assertEqual(
            policy.JUDGES["RETAIN"]("PRESENT", ("email",)), ("compliant", "present, retained")
        )
        self.assertEqual(policy.JUDGES["RETAIN"]("ABSENT", ()), ("none", "RETAINED_RECORD_MISSING"))

    def test_backup_and_flow_states(self):
        backup, flow = policy.JUDGES["BLOCK_RESTORE"], policy.JUDGES["DISABLE_FLOW"]
        self.assertEqual(backup("RESTORABLE", ())[0], "violation")
        self.assertEqual(backup("BLOCKED", ())[0], "compliant")
        self.assertEqual(backup("ABSENT", ())[0], "none")
        self.assertEqual(backup("PRESENT", ()), ("unproven", "PRESENT: restore access not shown"))
        self.assertEqual(flow("ACTIVE", ())[0], "violation")
        self.assertEqual(flow("DISABLED", ())[0], "compliant")
        self.assertEqual(flow("PRESENT", ())[0], "unproven")


class ActionFor(unittest.TestCase):
    def setUp(self):
        self.rules = policy.Rules.from_csv(DATA / "deletion_rules.csv")

    def test_rules_from_the_csv(self):
        self.assertEqual(policy.action_for("USER_PROFILE", self.rules), ("rule_01", "DELETE"))
        self.assertEqual(policy.action_for("SUPPORT_MESSAGE", self.rules), ("rule_05", "REDACT"))
        self.assertEqual(
            policy.action_for("ANALYTICS_PROFILE", self.rules), ("rule_07", "ANONYMIZE")
        )
        self.assertEqual(policy.action_for("LEGAL_HOLD_RECORD", self.rules), ("rule_13", "RETAIN"))

    def test_backup_retention_means_blocking_restore_and_flows_are_disabled(self):
        self.assertEqual(
            policy.action_for("BACKUP_ARCHIVE", self.rules), ("rule_14", "BLOCK_RESTORE")
        )
        self.assertEqual(policy.action_for("DATA_FLOW", self.rules), (None, "DISABLE_FLOW"))

    def test_a_violation_carries_three_steps_and_compliance_only_the_check(self):
        v = policy._treatment("violation", "why", "rule_01", "DELETE")
        self.assertEqual(
            (v.finding, v.remediation, v.verification),
            ("REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"),
        )
        c = policy._treatment("compliant", "why", "rule_01", "DELETE")
        self.assertEqual(
            (c.finding, c.remediation, c.verification), (None, None, "VERIFY_RECORD_ABSENT")
        )
        n = policy._treatment("none", "why", "rule_13", "RETAIN")
        self.assertEqual((n.kind, n.verification), ("none", None))


if __name__ == "__main__":
    unittest.main()
