"""Shift-handover text: '- <ts> | <system> | <resource> | <CATEGORY> | <STATUS> | <identifier>'
rows.

Not exhaustive (a checklist of what was checked), so it never emits Coverage.

Decisions: ADR 0014 (no Coverage: the format is not exhaustive), ADR 0002 (observed_at).
"""

from __future__ import annotations

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


def matches(text: str) -> bool:
    """True when `text` has this format's content signature (never decided by file name)."""
    return any(ROW_RE.match(line) for line in text.splitlines())


def _state(status: str, category: str) -> str:
    """A handover status as a state; an active backup means its restore is still possible."""
    state = STATUS[status]
    return "RESTORABLE" if state == "ACTIVE" and category == "BACKUP_ARCHIVE" else state


def _identity(ident: str, status: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(identifiers, exposed PII) of a row: the identifier column, exposed when the status says
    the value is still shown."""
    k = kind(ident)
    ids = (ident.strip(),) if k else ()
    pii = (PII_NAME[k],) if k in PII_NAME and status in EXPOSING else ()
    return ids, pii


def load(file_id: str, captured_at: str, text: str) -> LoadResult:
    """Parse one evidence file of this format into a LoadResult.

    Inputs: the manifest file_id and captured_at, and the decoded text. Output: Observations
    (and Coverage where the format is exhaustive); record-like units that cannot be used go to
    `unattributed` or `unparsed`, so nothing is dropped silently."""
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
