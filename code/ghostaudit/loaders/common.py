"""Shared helpers for loaders: value classification, PII fields, identifiers, attrs, logfmt
parsing.

Decisions: ADR 0014 (only absence signals and exhaustive files mean ABSENT)."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ghostaudit.identity import MIN_PHONE_DIGITS

if TYPE_CHECKING:
    pass
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
USER_RE = re.compile(r"^user_\d+$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
PHONE_RE = re.compile(r"^\+?[\d][\d ()\-]{7,}\d$")
ISO_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

# resource-id prefix -> owning system, for formats that print ids without a system column
PREFIX_SYSTEM = {
    "account": "account_service",
    "support": "support_platform",
    "search": "search_service",
    "analytics": "analytics_platform",
    "export": "export_service",
    "backup": "backup_service",
    "data_flow": "integration_service",
    "audit_record": "security_service",
    "legal_hold": "legal_service",
    "tombstone": "identity_service",
    "marketing": "marketing_platform",
    "object": "object_storage",
}


def system_of(resource_id: str) -> str | None:
    """Owning system of a resource id by its prefix (account_12 -> account_service), or None."""
    prefix = resource_id.rsplit("_", 1)[0]
    return PREFIX_SYSTEM.get(prefix)


NAME_FIELDS = {"full_name", "name", "display_name", "requester_name"}
EMAIL_FIELDS = {"email", "requester_email", "owner_email", "customer_email", "uploaded_by"}
PHONE_FIELDS = {"phone", "requester_phone", "owner_phone"}
HASH_FIELDS = {"email_hash"}
# How much raw text an unusable unit keeps for the loss report (enough to find it again).
EXCERPT_CHARS = 200
PII_ORDER = ("name", "email", "phone", "email_hash")
NOT_ATTRS = {"resource_id", "observed_at", "lookup_key", "trace_id", "level", "service", "event"}


@dataclass
class Unit:
    """A record unit a loader could not fully use (for the 'what is lost' report)."""

    file_id: str
    locator: str
    raw: str
    reason: str


@dataclass
class LoadResult:
    """What one file yields: observations, coverage, and the units it could not use.

    unattributed holds record units without an identifier; unparsed holds record-like lines the
    format did not understand. Both are reported by the loss ledger, never dropped."""

    signature: str
    observations: list = field(default_factory=list)
    coverage: list = field(default_factory=list)
    unattributed: list = field(default_factory=list)  # records with a resource but no identifier
    unparsed: list = field(default_factory=list)  # record-like units that could not be parsed


def null(v: object) -> bool:
    """True for None and for empty, 'null' or 'none' strings (any case, any padding)."""
    return v is None or (isinstance(v, str) and v.strip().lower() in ("", "null", "none"))


def kind(v: object) -> str | None:
    """'email' | 'user_id' | 'email_hash' | 'phone' | None for one scalar value."""
    if not isinstance(v, str) or null(v):
        return None
    t = v.strip()
    if EMAIL_RE.match(t):
        return "email"
    if USER_RE.match(t):
        return "user_id"
    if HASH_RE.match(t.lower()):
        return "email_hash"
    if PHONE_RE.match(t) and len(re.sub(r"\D", "", t)) >= MIN_PHONE_DIGITS:
        return "phone"
    return None


def pii_fields(fields: Mapping[str, Any]) -> tuple[str, ...]:
    """The direct-identifier kinds (name, email, phone, email_hash) a record still shows."""
    found = set()
    for k, v in fields.items():
        if null(v) or isinstance(v, (dict, list)):
            continue
        if k in NAME_FIELDS:
            found.add("name")
        elif k in EMAIL_FIELDS:
            found.add("email")
        elif k in PHONE_FIELDS:
            found.add("phone")
        elif k in HASH_FIELDS:
            found.add("email_hash")
    return tuple(p for p in PII_ORDER if p in found)


def identifiers(*values: object) -> tuple[str, ...]:
    """Sorted unique scalar values that are exact identifiers (email, user_id, sha256, phone)."""
    out = set()
    for v in values:
        if isinstance(v, str) and kind(v):
            out.add(v.strip())
    return tuple(sorted(out))


def scalar_items(fields: Mapping[str, Any]) -> list[tuple[str, Any]]:
    """(key, value) pairs of a record whose values are not nested dicts or lists."""
    return [(k, v) for k, v in fields.items() if not isinstance(v, (dict, list))]


def attrs(fields: Mapping[str, Any], exclude: Collection[str] = ()) -> tuple[tuple[str, str], ...]:
    """Non-identifying scalar fields of a record, as sorted (key, str value) pairs."""
    out = []
    for k, v in scalar_items(fields):
        if k in NOT_ATTRS or k in exclude or null(v):
            continue
        if k in NAME_FIELDS | EMAIL_FIELDS | PHONE_FIELDS | HASH_FIELDS:
            continue
        if isinstance(v, str) and kind(v):  # identifier-valued (customer_reference=user_N, ...)
            continue
        out.append((k, str(v).lower() if isinstance(v, bool) else str(v)))
    return tuple(sorted(out))


EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def emails_in_text(fields: Mapping[str, Any]) -> list[str]:
    """Emails embedded in free-text values (e.g. a support message body)."""
    out = []
    for _, v in scalar_items(fields):
        if isinstance(v, str) and not kind(v):
            out += [e.rstrip(".") for e in EMAIL_IN_TEXT.findall(v)]
    return out


KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')


def logfmt(text: str) -> dict[str, str]:
    """key=value pairs (values may be double-quoted) -> dict of str."""
    out = {}
    for k, v in KV_RE.findall(text):
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1].replace('\\"', '"')
        out[k] = v
    return out


def exposed_with_free_emails(fields: Mapping[str, Any]) -> tuple[tuple[str, ...], list[str]]:
    """(pii_fields, emails found in free text). An email inside free text counts as an exposed
    email even when no email field is set."""
    free = emails_in_text(fields)
    pii = pii_fields(fields)
    if free and "email" not in pii:
        pii = tuple(p for p in ("name", "email", "phone", "email_hash") if p in pii or p == "email")
    return pii, free


# Explicit absence signals (ADR 0014: these are strong evidence), checked before any flag.
ABSENCE_SIGNALS = (
    ("http_status", {"404"}),
    ("status_code", {"404"}),
    ("rows", {"0"}),
    ("result", {"miss", "not_found"}),
    ("total_hits", {"0"}),
    ("archive_present", {"false"}),
)
# (flag field, state when true, state when false), checked in this order
FLAG_STATES = (("restore_allowed", "RESTORABLE", "BLOCKED"), ("enabled", "ACTIVE", "DISABLED"))


def state_from_fields(f: Mapping[str, Any]) -> str:
    """Generic state for one record from its fields. Absence signals win, then flow/restore
    flags."""
    g = {
        k: (str(v).lower() if not isinstance(v, str) else v.lower())
        for k, v in f.items()
        if not isinstance(v, (dict, list))
    }
    if any(g.get(name) in values for name, values in ABSENCE_SIGNALS):
        return "ABSENT"
    for name, if_true, if_false in FLAG_STATES:
        if name in g:
            return if_true if g[name] in ("true", "1") else if_false
    return "PRESENT"


RID_RE = re.compile(r'"resource_id"\s*:\s*"([^"]+)"')


def _ordered_dicts(node: object, out: list[dict[str, Any]]) -> None:
    """Dicts carrying a resource_id, in the textual order of their "resource_id" key."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "resource_id":
                out.append(node)
            elif isinstance(v, (dict, list)):
                _ordered_dicts(v, out)
    elif isinstance(node, list):
        for v in node:
            _ordered_dicts(v, out)


def json_line_map(text: str, data: object) -> dict[int, str]:
    """id(dict) -> 'line N' of that dict's \"resource_id\" key, matched in textual order."""
    hits = [(m.group(1), text.count("\n", 0, m.start()) + 1) for m in RID_RE.finditer(text)]
    order: list[dict[str, Any]] = []
    _ordered_dicts(data, order)
    return {
        id(d): f"line {ln}"
        for d, (rid, ln) in zip(order, hits, strict=False)
        if d.get("resource_id") == rid
    }
