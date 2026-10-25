"""T08 policy: deletion_rules.csv as data, the ordered category table (ADR 0009), and the treatment
of each (category, state) pair (docs/03_DESIGN.md §3 Stage 6 table; ADR 0010, 0011, 0012).
"""

import unittest
from _path import DATA
from ghostaudit import policy
from ghostaudit.store import ActivityEvent, Observation, StateResult


def obs(
    sys_, res, state="PRESENT", cat=None, pii=(), attrs=(), table="t", at="2026-09-01T00:00:00Z"
):
    return Observation(
        "F", at, sys_, res, table, state, category=cat, pii_fields=tuple(pii), attrs=tuple(attrs)
    )


def act(type_, res, sys_="support_platform", at="2026-09-01T00:00:00Z"):
    return ActivityEvent("activity_1", at, type_, "deletion_worker", sys_, res, "SUCCESS")


def st(state, o=None):
    return StateResult(state, "F", "observation", "2026-09-01T00:00:00Z", "line 1", o)


class Rules(unittest.TestCase):
    def test_rules_are_read_from_the_dataset_file(self):
        r = policy.Rules.from_csv(DATA / "deletion_rules.csv")
        self.assertEqual(r.action("USER_PROFILE"), ("rule_01", "DELETE"))
        self.assertEqual(r.action("SUPPORT_MESSAGE"), ("rule_05", "REDACT"))
        self.assertEqual(r.action("ANALYTICS_PROFILE"), ("rule_07", "ANONYMIZE"))
        self.assertEqual(r.action("BACKUP_ARCHIVE"), ("rule_14", "RETAIN"))
        self.assertEqual(r.action("ACCOUNT_TOMBSTONE"), ("rule_15", "REDACT"))
        self.assertEqual(r.action("NO_SUCH_CATEGORY"), (None, None))


class CategoryPrecedence(unittest.TestCase):
    """tag > content > activity event type > system default; the first signal in that order wins."""

    def test_explicit_tag_beats_everything(self):
        o = [
            obs(
                "support_platform",
                "support_4218",
                cat="SUPPORT_ATTACHMENT",
                attrs=(("event", "message_read"),),
            )
        ]
        self.assertEqual(
            policy.categorize("support_platform", o, [act("REDACT_RECORD", "support_4218")]),
            ("SUPPORT_ATTACHMENT", "tag"),
        )

    def test_content_beats_activity(self):
        # an attachment scan names a file (evidence_01 line 25 support_9538): attachment, whatever
        # the claim says
        o = [
            obs(
                "support_platform",
                "support_9538",
                attrs=(("event", "attachment_pii_scan"), ("file", "delivery_confirmation_32.pdf")),
            )
        ]
        self.assertEqual(
            policy.categorize("support_platform", o, [act("REDACT_RECORD", "support_9538")]),
            ("SUPPORT_ATTACHMENT", "content"),
        )
        # a message scan is a conversation record (evidence_01 line 15 support_9553); with no claim
        # it decides
        o = [obs("support_platform", "support_9553", attrs=(("event", "message_pii_scan"),))]
        self.assertEqual(
            policy.categorize("support_platform", o, []), ("SUPPORT_MESSAGE", "message content")
        )

    def test_message_text_does_not_override_a_delete_claim(self):
        # silver audit regression (case_431 support_3615, case_347 support_9474): a ticket export
        # carries a templated message_excerpt for every ticket, so it is weaker than the
        # deletion_worker's DELETE_RECORD (ADR 0009: only an uploaded file is content that outranks
        # the activity type)
        o = [
            obs(
                "support_platform",
                "support_3615",
                attrs=(("message_excerpt", "Customer contacted support about account access."),),
            )
        ]
        self.assertEqual(
            policy.categorize("support_platform", o, [act("DELETE_RECORD", "support_3615")]),
            ("SUPPORT_ATTACHMENT", "activity"),
        )
        self.assertEqual(
            policy.categorize("support_platform", o, []), ("SUPPORT_MESSAGE", "message content")
        )

    def test_hash_keyed_contact_lookup_is_a_secondary_identifier(self):
        # evidence_01 line 92 analytics_9914 contact_lookup_completed keyed by an email hash
        # (case_12: DELETE)
        o = [
            obs(
                "analytics_platform",
                "analytics_9914",
                attrs=(("event", "contact_lookup_completed"),),
            )
        ]
        self.assertEqual(
            policy.categorize("analytics_platform", o, []), ("SECONDARY_IDENTIFIER", "content")
        )

    def test_activity_event_type_for_untagged_support_and_analytics(self):
        o = [obs("support_platform", "support_002", attrs=(("event", "contact_query_completed"),))]
        self.assertEqual(
            policy.categorize("support_platform", o, [act("DELETE_RECORD", "support_002")]),
            ("SUPPORT_ATTACHMENT", "activity"),
        )
        self.assertEqual(
            policy.categorize("support_platform", o, [act("REDACT_RECORD", "support_002")]),
            ("SUPPORT_MESSAGE", "activity"),
        )
        a = [obs("analytics_platform", "analytics_5208")]
        self.assertEqual(
            policy.categorize(
                "analytics_platform",
                a,
                [act("ANONYMIZE_RECORD", "analytics_5208", "analytics_platform")],
            ),
            ("ANALYTICS_PROFILE", "activity"),
        )

    def test_latest_activity_claim_wins_and_non_category_events_are_ignored(self):
        o = [obs("support_platform", "support_1")]
        claims = [
            act("REDACT_RECORD", "support_1", at="2026-08-01T00:00:00Z"),
            act("DELETE_RECORD", "support_1", at="2026-08-02T00:00:00Z"),
            act("UPDATE_RECORD", "support_1", at="2026-08-03T00:00:00Z"),
        ]
        self.assertEqual(
            policy.categorize("support_platform", o, claims), ("SUPPORT_ATTACHMENT", "activity")
        )

    def test_system_default(self):
        for sys_, cat in (
            ("account_service", "USER_PROFILE"),
            ("search_service", "SEARCH_INDEX_ENTRY"),
            ("export_service", "USER_EXPORT"),
            ("security_service", "SECURITY_AUDIT_LOG"),
            ("legal_service", "LEGAL_HOLD_RECORD"),
            ("backup_service", "BACKUP_ARCHIVE"),
            ("identity_service", "ACCOUNT_TOMBSTONE"),
            ("analytics_platform", "ANALYTICS_PROFILE"),
            ("integration_service", "DATA_FLOW"),
        ):
            self.assertEqual(
                policy.categorize(sys_, [obs(sys_, "r")], []), (cat, "system default"), sys_
            )

    def test_untagged_support_with_no_signal_has_no_category(self):
        self.assertEqual(
            policy.categorize("support_platform", [obs("support_platform", "support_7")], []),
            (None, "none"),
        )


class Treatment(unittest.TestCase):
    def setUp(self):
        self.rules = policy.Rules.from_csv(DATA / "deletion_rules.csv")

    def t(self, cat, state, pii=(), attrs=()):
        o = obs("x", "r", state=state, pii=pii, attrs=attrs)
        return policy.treat(cat, st(state, o) if state else None, self.rules)

    def test_delete_categories(self):
        v = self.t("SEARCH_INDEX_ENTRY", "PRESENT")
        self.assertEqual(
            (v.kind, v.finding, v.remediation, v.verification),
            ("violation", "REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"),
        )
        c = self.t("SEARCH_INDEX_ENTRY", "ABSENT")
        self.assertEqual(
            (c.kind, c.finding, c.verification), ("compliant", None, "VERIFY_RECORD_ABSENT")
        )

    def test_deletion_pending_account_is_present(self):
        # ADR 0010: evidence_63 line 19 account_3626 account_status DELETION_PENDING
        v = self.t(
            "USER_PROFILE",
            "PRESENT",
            pii=("email",),
            attrs=(("account_status", "DELETION_PENDING"),),
        )
        self.assertEqual((v.kind, v.finding), ("violation", "REPORT_REMAINING_RECORD"))

    def test_redact_and_anonymize_depend_on_exposed_identifiers(self):
        self.assertEqual(
            self.t("SUPPORT_MESSAGE", "PRESENT", pii=("email",)).finding, "REPORT_EXPOSED_PII"
        )
        self.assertEqual(
            self.t("SUPPORT_MESSAGE", "PRESENT", pii=("email",)).remediation, "REDACT_RECORD"
        )
        self.assertEqual(
            (
                self.t("SUPPORT_MESSAGE", "PRESENT").kind,
                self.t("SUPPORT_MESSAGE", "PRESENT").verification,
            ),
            ("compliant", "VERIFY_RECORD_REDACTED"),
        )
        a = self.t("ANALYTICS_PROFILE", "PRESENT", pii=("email", "phone"))
        self.assertEqual(
            (a.finding, a.remediation, a.verification),
            ("REPORT_EXPOSED_PII", "ANONYMIZE_RECORD", "VERIFY_RECORD_ANONYMIZED"),
        )
        self.assertEqual(
            self.t("ANALYTICS_PROFILE", "PRESENT").verification, "VERIFY_RECORD_ANONYMIZED"
        )

    def test_tombstone_is_redact_never_present(self):
        self.assertEqual(
            self.t("ACCOUNT_TOMBSTONE", "PRESENT").verification, "VERIFY_RECORD_REDACTED"
        )
        e = self.t("ACCOUNT_TOMBSTONE", "PRESENT", pii=("name", "email", "phone", "email_hash"))
        self.assertEqual(
            (e.kind, e.finding, e.remediation), ("violation", "REPORT_EXPOSED_PII", "REDACT_RECORD")
        )

    def test_retained_records(self):
        self.assertEqual(
            (
                self.t("SECURITY_AUDIT_LOG", "PRESENT").kind,
                self.t("SECURITY_AUDIT_LOG", "PRESENT").verification,
            ),
            ("compliant", "VERIFY_RECORD_PRESENT"),
        )
        self.assertEqual(
            self.t("LEGAL_HOLD_RECORD", "PRESENT").verification, "VERIFY_RECORD_PRESENT"
        )  # ADR 0011
        self.assertEqual(
            self.t("SECURITY_AUDIT_LOG", "ABSENT").kind, "none"
        )  # no finding op exists for a lost retained record

    def test_backups_and_flows(self):
        r = self.t("BACKUP_ARCHIVE", "RESTORABLE")
        self.assertEqual(
            (r.kind, r.finding, r.remediation, r.verification),
            ("violation", "REPORT_RESTORE_RISK", "BLOCK_RESTORE", "VERIFY_RESTORE_BLOCKED"),
        )
        self.assertEqual(self.t("BACKUP_ARCHIVE", "BLOCKED").verification, "VERIFY_RESTORE_BLOCKED")
        f = self.t("DATA_FLOW", "ACTIVE")
        self.assertEqual(
            (f.finding, f.remediation, f.verification),
            ("REPORT_ACTIVE_DATA_FLOW", "DISABLE_DATA_FLOW", "VERIFY_DATA_FLOW_DISABLED"),
        )
        self.assertEqual(self.t("DATA_FLOW", "DISABLED").kind, "compliant")
        self.assertEqual(
            (
                self.t("BACKUP_ARCHIVE", "PRESENT").kind,
                self.t("BACKUP_ARCHIVE", "PRESENT").verification,
            ),
            ("unproven", "VERIFY_RESTORE_BLOCKED"),
        )

    def test_no_state_is_unproven_with_the_required_end_state(self):
        u = self.t("USER_PROFILE", None)
        self.assertEqual((u.kind, u.verification), ("unproven", "VERIFY_RECORD_ABSENT"))

    def test_unobservable_and_unknown_categories_produce_nothing(self):
        for cat in (
            "CACHE_ENTRY",
            "EMAIL_DELIVERY_LOG",
            "PRODUCT_TELEMETRY",
            "MARKETING_PROFILE",
            None,
        ):
            self.assertEqual(self.t(cat, "PRESENT").kind, "none", cat)


if __name__ == "__main__":
    unittest.main()
