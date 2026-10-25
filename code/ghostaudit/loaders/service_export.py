"""Service resource export JSON: {"service_exports": {<system>: {<collection>: [record, ...]}}}.

Each record is one probed resource (search records nest the hit documents). A probe list is not
exhaustive, so no Coverage is emitted.
"""

from __future__ import annotations

import json
from typing import Any

from ghostaudit.loaders.common import (
    LoadResult,
    Unit,
    attrs,
    identifiers,
    json_line_map,
    pii_fields,
    scalar_items,
    state_from_fields,
)
from ghostaudit.store import Observation


def _search_record(
    r: LoadResult,
    file_id: str,
    system: str,
    table: str,
    rec: dict[str, Any],
    observed: str,
    lines: dict[int, str],
) -> None:
    """A search query record: one PRESENT observation per hit document, or one ABSENT observation
    of the queried resource when the search returned nothing."""
    docs = rec["hits"].get("documents") or []
    for doc in docs:
        fields = {**doc}
        ids = identifiers(*(v for _, v in scalar_items(fields)), rec.get("query"))
        o = Observation(
            file_id,
            observed,
            system,
            doc["resource_id"],
            table,
            "PRESENT",
            pii_fields=pii_fields(fields),
            identifiers=ids,
            locator=lines.get(id(doc), ""),
            attrs=attrs(fields),
        )
        _add(r, file_id, o, json.dumps(doc))
    if not docs:
        o = Observation(
            file_id,
            observed,
            system,
            rec["resource_id"],
            table,
            "ABSENT",
            identifiers=identifiers(rec.get("query")),
            locator=lines.get(id(rec), ""),
            attrs=(("total_hits", str(rec["hits"].get("total", 0))),),
        )
        _add(r, file_id, o, json.dumps(rec))


def _plain_record(
    r: LoadResult,
    file_id: str,
    system: str,
    table: str,
    rec: dict[str, Any],
    observed: str,
    lines: dict[int, str],
) -> None:
    """A resource record; the fields of a nested "profile" count as the record's own."""
    profile = rec.get("profile")
    nested = profile if isinstance(profile, dict) else {}
    fields = {**rec, **nested}
    o = Observation(
        file_id,
        observed,
        system,
        rec["resource_id"],
        table,
        state_from_fields(rec),
        pii_fields=pii_fields(fields),
        identifiers=identifiers(*(v for _, v in scalar_items(fields))),
        locator=lines.get(id(rec), ""),
        attrs=attrs(rec),
    )
    _add(r, file_id, o, json.dumps(rec))


def load(file_id: str, captured_at: str, text: str) -> LoadResult:
    data = json.loads(text)
    lines = json_line_map(text, data)
    r = LoadResult("json:service_exports")
    for system, collections in data["service_exports"].items():
        for coll, records in collections.items():
            for rec in records:
                observed = rec.get("observed_at") or captured_at
                read = _search_record if "hits" in rec else _plain_record
                read(r, file_id, system, f"{system}.{coll}", rec, observed, lines)
    return r


def _add(r: LoadResult, file_id: str, o: Observation, raw: str) -> None:
    r.observations.append(o)
    if not o.identifiers:
        r.unattributed.append(Unit(file_id, o.locator, raw, "no identifier"))
