"""Policy (docs/03_DESIGN.md §3 Stage 6): which category a resource is, and what its state requires.

  Rules.from_csv(path).action(category) -> (rule_id, action)   deletion_rules.csv read as data
  categorize(system_id, observations, activity) -> (category, source)
  treat(category, state_result, rules) -> Treatment

Category precedence (ADR 0009) is the ordered table CATEGORY_SIGNALS: explicit tag, then strong record
content (an uploaded file, a hash-keyed contact), then the deletion_worker event type (a claim about
category, never about state), then weak message text, then the system default. DATA_FLOW is not a deletion_rules category: connectors get the data-flow operations.
"""

import csv
from dataclasses import dataclass
from typing import Optional

ABSENT = "ABSENT"

SYSTEM_DEFAULT = {
    "account_service": "USER_PROFILE",
    "search_service": "SEARCH_INDEX_ENTRY",
    "export_service": "USER_EXPORT",
    "security_service": "SECURITY_AUDIT_LOG",
    "legal_service": "LEGAL_HOLD_RECORD",
    "backup_service": "BACKUP_ARCHIVE",
    "identity_service": "ACCOUNT_TOMBSTONE",
    "analytics_platform": "ANALYTICS_PROFILE",
    "integration_service": "DATA_FLOW",
}
# deletion_worker event type -> category, per system whose category depends on it (ADR 0009, docs/02 §7.2-7.5)
ACTIVITY_CATEGORY = {
    ("support_platform", "REDACT_RECORD"): "SUPPORT_MESSAGE",
    ("support_platform", "DELETE_RECORD"): "SUPPORT_ATTACHMENT",
    ("analytics_platform", "ANONYMIZE_RECORD"): "ANALYTICS_PROFILE",
    ("analytics_platform", "DELETE_RECORD"): "SECONDARY_IDENTIFIER",
}
UNOBSERVABLE = {
    "CACHE_ENTRY",
    "EMAIL_DELIVERY_LOG",
    "PRODUCT_TELEMETRY",
    "MARKETING_PROFILE",
}  # ADR 0012


def _content(system_id, o):
    """Category shown by the record's own content (strong: outranks the activity claim), or None."""
    a = dict(o.attrs)
    event = a.get("event", "")
    if system_id == "support_platform":
        if event.startswith("attachment_") or "file" in a or "attachment" in o.table:
            return "SUPPORT_ATTACHMENT"  # an uploaded file (docs/02 §4.6 A9; ADR 0009 "artifact content")
    if system_id == "analytics_platform" and event == "contact_lookup_completed":
        return (
            "SECONDARY_IDENTIFIER"  # a contact identifier keyed by email hash, not a profile (§7.3)
        )
    return None


def _message_content(o):
    """Weak content: message text. Ticket exports carry a templated message_excerpt on every ticket, so it only
    decides when no deletion_worker claim exists (silver audit, docs/SILVER_AUDIT.md: 12 eval records)."""
    a = dict(o.attrs)
    return (
        a.get("event", "").startswith("message_") or "message_text" in a or "message_excerpt" in a
    )


def _by_tag(system_id, observations, activity):
    tagged = [o for o in observations if o.category]
    return tagged[-1].category if tagged else None


def _by_content(system_id, observations, activity):
    hits = [c for c in (_content(system_id, o) for o in observations) if c]
    return hits[-1] if hits else None


def _by_activity(system_id, observations, activity):
    claims = [
        ACTIVITY_CATEGORY[(system_id, a.event_type)]
        for a in activity
        if (system_id, a.event_type) in ACTIVITY_CATEGORY
    ]
    return claims[-1] if claims else None


def _by_message_content(system_id, observations, activity):
    if system_id == "support_platform" and any(_message_content(o) for o in observations):
        return "SUPPORT_MESSAGE"
    return None


def _by_system(system_id, observations, activity):
    return SYSTEM_DEFAULT.get(system_id)


CATEGORY_SIGNALS = (
    ("tag", _by_tag),
    ("content", _by_content),
    ("activity", _by_activity),
    ("message content", _by_message_content),
    ("system default", _by_system),
)


def categorize(system_id, observations, activity):
    """observations and activity in time order, already cut at audit_at."""
    for source, signal in CATEGORY_SIGNALS:
        c = signal(system_id, observations, activity)
        if c:
            return c, source
    return None, "none"


class Rules:
    def __init__(self, rows):
        self._by_cat = {r["data_category"]: (r["rule_id"], r["required_action"]) for r in rows}

    @classmethod
    def from_csv(cls, path):
        with open(path, newline="", encoding="utf-8") as f:
            return cls(list(csv.DictReader(f)))

    def action(self, category):
        return self._by_cat.get(category, (None, None))


@dataclass(frozen=True)
class Treatment:
    kind: str  # violation | compliant | unproven | none
    finding: Optional[str] = None
    remediation: Optional[str] = None
    verification: Optional[str] = None
    rule_id: Optional[str] = None
    action: Optional[str] = None
    reason: str = ""


# action -> (finding, remediation, verification) when the end state is violated
PLANS = {
    "DELETE": ("REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"),
    "REDACT": ("REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"),
    "ANONYMIZE": ("REPORT_EXPOSED_PII", "ANONYMIZE_RECORD", "VERIFY_RECORD_ANONYMIZED"),
    "RETAIN": (None, None, "VERIFY_RECORD_PRESENT"),
    "BLOCK_RESTORE": ("REPORT_RESTORE_RISK", "BLOCK_RESTORE", "VERIFY_RESTORE_BLOCKED"),
    "DISABLE_FLOW": ("REPORT_ACTIVE_DATA_FLOW", "DISABLE_DATA_FLOW", "VERIFY_DATA_FLOW_DISABLED"),
}


def treat(category, result, rules):
    """Treatment for one resource from its category and its StateResult (None = nothing visible proves anything)."""
    if category is None:
        return Treatment("none", reason="UNRESOLVED_CATEGORY")
    if category in UNOBSERVABLE:
        return Treatment("none", reason=f"NOT_OBSERVABLE({category})")
    if category == "DATA_FLOW":
        rule_id, action = None, "DISABLE_FLOW"
    else:
        rule_id, action = rules.action(category)
        if category == "BACKUP_ARCHIVE" and action == "RETAIN":
            action = "BLOCK_RESTORE"  # rule_14: retain, and restore access must be blocked
    if action not in PLANS:
        return Treatment(
            "none", rule_id=rule_id, action=action, reason=f"NO_PLAN({category}, {action})"
        )
    finding, remediation, verify = PLANS[action]
    mk = lambda kind, why, f=None, r=None: Treatment(kind, f, r, verify, rule_id, action, why)
    if result is None:
        return mk("unproven", "UNPROVEN: no visible observation or coverage")
    s = result.state
    pii = result.observation.pii_fields if result.observation else ()
    if action == "DELETE":
        return (
            mk("compliant", "absent")
            if s == ABSENT
            else mk("violation", f"{s}, must be absent", finding, remediation)
        )
    if action in ("REDACT", "ANONYMIZE"):
        if s == ABSENT:
            return Treatment(
                "none", rule_id=rule_id, action=action, reason="ABSENT, but policy keeps the record"
            )
        if pii:
            return mk("violation", f"exposes {', '.join(pii)}", finding, remediation)
        return mk("compliant", "present without direct identifiers")
    if action == "RETAIN":
        if s == ABSENT:
            return Treatment(
                "none", rule_id=rule_id, action=action, reason="RETAINED_RECORD_MISSING"
            )
        return mk("compliant", "present, retained")
    if action == "BLOCK_RESTORE":
        if s == "RESTORABLE":
            return mk("violation", "restore allowed", finding, remediation)
        if s == "BLOCKED":
            return mk("compliant", "restore blocked")
        if s == ABSENT:
            return Treatment("none", rule_id=rule_id, action=action, reason="backup absent")
        return mk("unproven", f"{s}: restore access not shown")
    if s == "ACTIVE":
        return mk("violation", "flow enabled", finding, remediation)
    if s == "DISABLED":
        return mk("compliant", "flow disabled")
    return mk("unproven", f"{s}: flow state not shown")
