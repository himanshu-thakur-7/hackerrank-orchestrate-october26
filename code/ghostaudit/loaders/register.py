"""Register rows: {system, resource_id, record_type, result, subject_reference|lookup_value,
recorded_at}.

A register is a history of checks, never a listing, so it never yields Coverage (ADR 0014).
The status vocabulary is the same as the shift handover.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from ghostaudit.loaders.common import EXCERPT_CHARS, Unit, kind
from ghostaudit.loaders.handover import EXPOSING, PII_NAME, STATUS
from ghostaudit.store import Observation

if TYPE_CHECKING:
    from ghostaudit.loaders.common import LoadResult
REGISTER_KEYS = {"system", "resource_id", "record_type", "result"}


def is_register(records: Sequence[object]) -> bool:
    """True when every record has the register keys (system, resource_id, record_type, result)."""
    return bool(records) and all(isinstance(r, dict) and set(r) >= REGISTER_KEYS for r in records)


def observation(
    file_id: str,
    rec: Mapping[str, Any],
    table: str,
    locator: str,
    default_time: str,
    result_out: LoadResult,
) -> Observation | None:
    """The Observation of one register row, appended to `result_out`.

    An unknown result is recorded as unparsed and returns None; an active backup archive is
    RESTORABLE; the subject reference is the only identifier, exposed when the status says the
    value is still shown."""
    status = str(rec.get("result", ""))
    if status not in STATUS:
        result_out.unparsed.append(
            Unit(file_id, locator, str(rec)[:EXCERPT_CHARS], f"unknown register result {status!r}")
        )
        return None
    state = STATUS[status]
    if state == "ACTIVE" and rec.get("record_type") == "BACKUP_ARCHIVE":
        state = "RESTORABLE"
    subject = rec.get("subject_reference") or rec.get("lookup_value")
    k = kind(subject)
    o = Observation(
        file_id,
        rec.get("recorded_at") or default_time,
        rec["system"],
        rec["resource_id"],
        table,
        state,
        category=rec.get("record_type"),
        pii_fields=(PII_NAME[k],) if k in PII_NAME and status in EXPOSING else (),
        identifiers=(cast("str", subject).strip(),) if k else (),
        locator=locator,
        attrs=(("status", status),),
    )
    result_out.observations.append(o)
    if not o.identifiers:
        result_out.unattributed.append(
            Unit(file_id, locator, str(rec)[:EXCERPT_CHARS], "no identifier")
        )
    return o
