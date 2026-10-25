"""Register rows: {system, resource_id, record_type, result, subject_reference|lookup_value, recorded_at}.

A register is a history of checks, never a listing, so it never yields Coverage (ADR 0014).
The status vocabulary is the same as the shift handover.
"""

from ghostaudit.loaders.common import Unit, kind
from ghostaudit.loaders.handover import EXPOSING, PII_NAME, STATUS
from ghostaudit.store import Observation

REGISTER_KEYS = {"system", "resource_id", "record_type", "result"}


def is_register(records):
    return bool(records) and all(isinstance(r, dict) and REGISTER_KEYS <= set(r) for r in records)


def observation(file_id, rec, table, locator, default_time, result_out):
    status = str(rec.get("result", ""))
    if status not in STATUS:
        result_out.unparsed.append(
            Unit(file_id, locator, str(rec)[:200], f"unknown register result {status!r}")
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
        identifiers=(subject.strip(),) if k else (),
        locator=locator,
        attrs=(("status", status),),
    )
    result_out.observations.append(o)
    if not o.identifiers:
        result_out.unattributed.append(Unit(file_id, locator, str(rec)[:200], "no identifier"))
    return o
