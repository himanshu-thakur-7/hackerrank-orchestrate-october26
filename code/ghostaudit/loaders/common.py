"""Shared helpers for loaders: value classification, PII fields, identifiers, attrs, logfmt parsing."""
import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
USER_RE = re.compile(r"^user_\d+$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
PHONE_RE = re.compile(r"^\+?[\d][\d ()\-]{7,}\d$")
ISO_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

NAME_FIELDS = {"full_name", "name", "display_name", "requester_name"}
EMAIL_FIELDS = {"email", "requester_email", "owner_email", "customer_email"}
PHONE_FIELDS = {"phone", "requester_phone", "owner_phone"}
HASH_FIELDS = {"email_hash"}
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
    signature: str
    observations: list = field(default_factory=list)
    coverage: list = field(default_factory=list)
    unattributed: list = field(default_factory=list)   # records with a resource but no identifier
    unparsed: list = field(default_factory=list)       # record-like units that could not be parsed


def null(v):
    return v is None or (isinstance(v, str) and v.strip().lower() in ("", "null", "none"))


def kind(v):
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
    if PHONE_RE.match(t) and len(re.sub(r"\D", "", t)) >= 9:
        return "phone"
    return None


def pii_fields(fields):
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


def identifiers(*values):
    """Sorted unique scalar values that are exact identifiers (email, user_id, sha256, phone)."""
    out = set()
    for v in values:
        if isinstance(v, str) and kind(v):
            out.add(v.strip())
    return tuple(sorted(out))


def scalar_items(fields):
    return [(k, v) for k, v in fields.items() if not isinstance(v, (dict, list))]


def attrs(fields, exclude=()):
    """Non-identifying scalar fields of a record, as sorted (key, str value) pairs."""
    out = []
    for k, v in scalar_items(fields):
        if k in NOT_ATTRS or k in exclude or null(v):
            continue
        if k in NAME_FIELDS | EMAIL_FIELDS | PHONE_FIELDS | HASH_FIELDS:
            continue
        if isinstance(v, str) and kind(v):          # identifier-valued (customer_reference=user_N, ...)
            continue
        out.append((k, str(v).lower() if isinstance(v, bool) else str(v)))
    return tuple(sorted(out))


KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')


def logfmt(text):
    """key=value pairs (values may be double-quoted) -> dict of str."""
    out = {}
    for k, v in KV_RE.findall(text):
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1].replace('\\"', '"')
        out[k] = v
    return out


def state_from_fields(f):
    """Generic state for one record from its fields. Absence signals win, then flow/restore flags."""
    g = {k: (str(v).lower() if not isinstance(v, str) else v.lower()) for k, v in f.items() if not isinstance(v, (dict, list))}
    if g.get("http_status") == "404" or g.get("status_code") == "404" or g.get("rows") == "0" \
            or g.get("result") in ("miss", "not_found") or g.get("total_hits") == "0" or g.get("archive_present") == "false":
        return "ABSENT"
    if "restore_allowed" in g:
        return "RESTORABLE" if g["restore_allowed"] in ("true", "1") else "BLOCKED"
    if "enabled" in g:
        return "ACTIVE" if g["enabled"] in ("true", "1") else "DISABLED"
    return "PRESENT"
