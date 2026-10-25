"""Screenshots (signature: PNG magic bytes). Facts come from committed transcriptions keyed by the
sha256 of the image (screens_data.py); a PNG without one is an unknown signature, never skipped.
Live cached
vision extraction is the second adapter (T11). observed_at is the file's captured_at (ADR 0002)."""

import hashlib

from ghostaudit.loaders import screens_data
from ghostaudit.loaders.common import LoadResult, Unit, identifiers


class MissingTranscription(Exception):
    pass


def load(file_id, captured_at, raw):
    from ghostaudit.store import Observation

    sha = hashlib.sha256(raw).hexdigest()
    screen = screens_data.SCREENS.get(sha)
    if screen is None:
        raise MissingTranscription(
            f"{file_id}: PNG sha256 {sha} has no committed transcription (screens_data.py); "
            f"live vision extraction is T11"
        )
    r = LoadResult("png")
    for rec in screen["records"]:
        ids = identifiers(*rec["identifiers"])
        o = Observation(
            file_id,
            captured_at,
            rec["system_id"],
            rec["resource_id"],
            "screen",
            rec["state"],
            pii_fields=tuple(
                p for p in ("name", "email", "phone", "email_hash") if p in rec["pii"]
            ),
            identifiers=ids,
            locator=f"screen {rec['region']}",
            attrs=tuple(sorted(rec["attrs"].items())),
        )
        r.observations.append(o)
        if not ids:
            r.unattributed.append(Unit(file_id, o.locator, rec["resource_id"], "no identifier"))
    for u in screen["units"]:
        r.unattributed.append(Unit(file_id, f"screen {u['region']}", u["text"], "no resource id"))
    return r
