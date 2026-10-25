"""Shift-handover text: '- <ts> | <system> | <resource> | <CATEGORY> | <STATUS> | <identifier>'
rows.

Not exhaustive (a checklist of what was checked), so it never emits Coverage.
"""

import re

from ghostaudit.loaders.common import LoadResult, Unit, kind
from ghostaudit.store import Observation

ROW_RE = re.compile(r"^- (\S+) \| (\S+) \| (\S+) \| ([A-Z_]+) \| ([A-Z_]+) \| (.*)$")
STATUS = {
    "NOT_FOUND": "ABSENT",
    "FOUND": "PRESENT",
    "IDENTIFIABLE": "PRESENT",
    "ANONYMIZED": "PRESENT",
    "REDACTED": "PRESENT",
    "ACTIVE": "ACTIVE",
    "DISABLED": "DISABLED",
    "BLOCKED": "BLOCKED",
}
EXPOSING = {"FOUND", "IDENTIFIABLE", "ACTIVE"}
PII_NAME = {"email": "email", "email_hash": "email_hash", "phone": "phone"}


def matches(text):
    return any(ROW_RE.match(line) for line in text.splitlines())


def _state(status, category):
    """A handover status as a state; an active backup means its restore is still possible."""
    state = STATUS[status]
    return "RESTORABLE" if state == "ACTIVE" and category == "BACKUP_ARCHIVE" else state


def _identity(ident, status):
    """(identifiers, exposed PII) of a row: the identifier column, exposed when the status says
    the value is still shown."""
    k = kind(ident)
    ids = (ident.strip(),) if k else ()
    pii = (PII_NAME[k],) if k in PII_NAME and status in EXPOSING else ()
    return ids, pii


def load(file_id, captured_at, text):
    r = LoadResult("txt:handover")
    for n, line in enumerate(text.splitlines(), 1):
        if not line.startswith("- "):
            continue  # title / snapshot header / prose
        m = ROW_RE.match(line)
        if not m or m.group(5) not in STATUS:
            r.unparsed.append(Unit(file_id, f"line {n}", line, "handover row not understood"))
            continue
        ts, system, res, cat, status, ident = m.groups()
        ids, pii = _identity(ident, status)
        o = Observation(
            file_id,
            ts,
            system,
            res,
            "handover",
            _state(status, cat),
            category=cat,
            pii_fields=pii,
            identifiers=ids,
            locator=f"line {n}",
            attrs=(("status", status),),
        )
        r.observations.append(o)
        if not ids:
            r.unattributed.append(Unit(file_id, f"line {n}", line, "no identifier"))
    return r
