"""Policy (docs/03_DESIGN.md §3 Stage 6): which category a resource is, and what its state requires.

  Rules.from_csv(path).action(category) -> (rule_id, action)   deletion_rules.csv read as data
  categorize(system_id, observations, activity) -> (category, source)
  treat(category, state_result, rules) -> Treatment

Category precedence (ADR 0009) is the ordered table CATEGORY_SIGNALS: explicit tag, then strong
record content (an uploaded file, a hash-keyed contact), then the deletion_worker event type (a
claim about category, never about state), then weak message text, then the system default. DATA_FLOW
is not a deletion_rules category: connectors get the data-flow operations.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ghostaudit.store import ActivityEvent, Observation, StateResult
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
# deletion_worker event type -> category, per system whose category depends on it (ADR 0009, docs/02
# §7.2-7.5)
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


def _content(system_id: str, o: Observation) -> str | None:
    """Category shown by the record's own content (strong: outranks the activity claim), or None."""
    a = dict(o.attrs)
    event = a.get("event", "")
    is_upload = event.startswith("attachment_") or "file" in a or "attachment" in o.table
    if system_id == "support_platform" and is_upload:
        # an uploaded file (docs/02 §4.6 A9; ADR 0009 "artifact content")
        return "SUPPORT_ATTACHMENT"
    if system_id == "analytics_platform" and event == "contact_lookup_completed":
        return (
            "SECONDARY_IDENTIFIER"  # a contact identifier keyed by email hash, not a profile (§7.3)
        )
    return None


def _message_content(o: Observation) -> bool:
    """Weak content: message text. Ticket exports carry a templated message_excerpt on every ticket,
    so it only
    decides when no deletion_worker claim exists (silver audit, docs/SILVER_AUDIT.md: 12 eval
    records)."""
    a = dict(o.attrs)
    return (
        a.get("event", "").startswith("message_") or "message_text" in a or "message_excerpt" in a
    )


def _by_tag(
    system_id: str, observations: list[Observation], activity: list[ActivityEvent]
) -> str | None:
    tagged = [o for o in observations if o.category]
    return tagged[-1].category if tagged else None


def _by_content(
    system_id: str, observations: list[Observation], activity: list[ActivityEvent]
) -> str | None:
    hits = [c for c in (_content(system_id, o) for o in observations) if c]
    return hits[-1] if hits else None


def _by_activity(
    system_id: str, observations: list[Observation], activity: list[ActivityEvent]
) -> str | None:
    claims = [
        ACTIVITY_CATEGORY[(system_id, a.event_type)]
        for a in activity
        if (system_id, a.event_type) in ACTIVITY_CATEGORY
    ]
    return claims[-1] if claims else None


def _by_message_content(
    system_id: str, observations: list[Observation], activity: list[ActivityEvent]
) -> str | None:
    if system_id == "support_platform" and any(_message_content(o) for o in observations):
        return "SUPPORT_MESSAGE"
    return None


def _by_system(
    system_id: str, observations: list[Observation], activity: list[ActivityEvent]
) -> str | None:
    return SYSTEM_DEFAULT.get(system_id)


CATEGORY_SIGNALS = (
    ("tag", _by_tag),
    ("content", _by_content),
    ("activity", _by_activity),
    ("message content", _by_message_content),
    ("system default", _by_system),
)


def categorize(
    system_id: str, observations: list[Observation], activity: list[ActivityEvent]
) -> tuple[str | None, str]:
    """observations and activity in time order, already cut at audit_at."""
    for source, signal in CATEGORY_SIGNALS:
        c = signal(system_id, observations, activity)
        if c:
            return c, source
    return None, "none"


class Rules:
    def __init__(self, rows: Iterable[Mapping[str, str]]) -> None:
        self._by_cat: dict[str | None, tuple[str | None, str | None]] = {
            r["data_category"]: (r["rule_id"], r["required_action"]) for r in rows
        }

    @classmethod
    def from_csv(cls, path: str | Path) -> Rules:
        with open(path, newline="", encoding="utf-8") as f:
            return cls(list(csv.DictReader(f)))

    def action(self, category: str | None) -> tuple[str | None, str | None]:
        return self._by_cat.get(category, (None, None))


@dataclass(frozen=True)
class Treatment:
    kind: str  # violation | compliant | unproven | none
    finding: str | None = None
    remediation: str | None = None
    verification: str | None = None
    rule_id: str | None = None
    action: str | None = None
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


def _judge_delete(state: str, pii: tuple[str, ...]) -> tuple[str, str]:
    """DELETE: compliant only when the record is gone."""
    if state == ABSENT:
        return "compliant", "absent"
    return "violation", f"{state}, must be absent"


def _judge_keep_without_identifiers(state: str, pii: tuple[str, ...]) -> tuple[str, str]:
    """REDACT / ANONYMIZE: the record stays, but no direct identifier may remain on it."""
    if state == ABSENT:
        return "none", "ABSENT, but policy keeps the record"
    if pii:
        return "violation", f"exposes {', '.join(pii)}"
    return "compliant", "present without direct identifiers"


def _judge_retain(state: str, pii: tuple[str, ...]) -> tuple[str, str]:
    """RETAIN: the record must still exist; a missing one is logged, never planned."""
    if state == ABSENT:
        return "none", "RETAINED_RECORD_MISSING"
    return "compliant", "present, retained"


_BACKUP_STATES = {
    "RESTORABLE": ("violation", "restore allowed"),
    "BLOCKED": ("compliant", "restore blocked"),
    ABSENT: ("none", "backup absent"),
}
_FLOW_STATES = {"ACTIVE": ("violation", "flow enabled"), "DISABLED": ("compliant", "flow disabled")}


def _judge_backup(state: str, pii: tuple[str, ...]) -> tuple[str, str]:
    """BLOCK_RESTORE (rule_14): the backup is retained but its restore access must be blocked."""
    return _BACKUP_STATES.get(state, ("unproven", f"{state}: restore access not shown"))


def _judge_flow(state: str, pii: tuple[str, ...]) -> tuple[str, str]:
    """DISABLE_FLOW: a connector must be shown disabled."""
    return _FLOW_STATES.get(state, ("unproven", f"{state}: flow state not shown"))


# action -> judge(state, exposed PII fields) -> (kind, reason); kind is violation | compliant |
# unproven | none
JUDGES = {
    "DELETE": _judge_delete,
    "REDACT": _judge_keep_without_identifiers,
    "ANONYMIZE": _judge_keep_without_identifiers,
    "RETAIN": _judge_retain,
    "BLOCK_RESTORE": _judge_backup,
    "DISABLE_FLOW": _judge_flow,
}


def action_for(category: str, rules: Rules) -> tuple[str | None, str | None]:
    """(rule_id, action) for a category. Connectors are not a deletion_rules category and always
    get DISABLE_FLOW; a retained backup (rule_14) must also have its restore access blocked."""
    if category == "DATA_FLOW":
        return None, "DISABLE_FLOW"
    rule_id, action = rules.action(category)
    if category == "BACKUP_ARCHIVE" and action == "RETAIN":
        return rule_id, "BLOCK_RESTORE"
    return rule_id, action


def _treatment(kind: str, reason: str, rule_id: str | None, action: str) -> Treatment:
    """A Treatment carrying the plan steps its kind needs: a violation gets finding, remediation and
    verification; compliant and unproven get the verification only; none gets no step."""
    finding, remediation, verify = PLANS[action]
    if kind == "none":
        return Treatment("none", rule_id=rule_id, action=action, reason=reason)
    if kind == "violation":
        return Treatment(kind, finding, remediation, verify, rule_id, action, reason)
    return Treatment(kind, None, None, verify, rule_id, action, reason)


def treat(category: str | None, result: StateResult | None, rules: Rules) -> Treatment:
    """Treatment for one resource from its category and its StateResult (None = nothing visible
    proves anything)."""
    if category is None:
        return Treatment("none", reason="UNRESOLVED_CATEGORY")
    if category in UNOBSERVABLE:
        return Treatment("none", reason=f"NOT_OBSERVABLE({category})")
    rule_id, action = action_for(category, rules)
    if action not in PLANS:
        return Treatment(
            "none", rule_id=rule_id, action=action, reason=f"NO_PLAN({category}, {action})"
        )
    if result is None:
        return _treatment(
            "unproven", "UNPROVEN: no visible observation or coverage", rule_id, action
        )
    pii = result.observation.pii_fields if result.observation else ()
    kind, reason = JUDGES[action](result.state, pii)
    return _treatment(kind, reason, rule_id, action)
