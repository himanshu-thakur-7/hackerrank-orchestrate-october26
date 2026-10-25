"""Record-list JSON: {"records": [...]} in two shapes, recognised by record content:
* registers (record_type/result rows): checks, no Coverage;
* collection lists {"collection": ..., "captured_at": ..., "records": [data rows]}: weak Coverage
  (ADR 0014).
"""

from __future__ import annotations

import json

from ghostaudit.loaders import datarow, register
from ghostaudit.loaders.common import LoadResult, Unit, json_line_map
from ghostaudit.loaders.sql import COLLECTION_CATEGORY
from ghostaudit.store import Coverage


def load(file_id: str, captured_at: str, text: str) -> LoadResult:
    data = json.loads(text)
    lines = json_line_map(text, data)
    r = LoadResult("json:records")
    recs = data.get("records") or []
    if register.is_register(recs):
        for rec in recs:
            register.observation(file_id, rec, "register", lines.get(id(rec), ""), captured_at, r)
        return r
    coll = data.get("collection")
    system = datarow.COLLECTION_SYSTEM.get(coll)
    if system is None:
        r.unparsed.append(
            Unit(
                file_id,
                "file",
                f"collection={coll!r} keys={sorted(data)}",
                f"unknown collection {coll!r}",
            )
        )
        return r
    cap = data.get("captured_at") or captured_at
    for rec in recs:
        datarow.observation(
            file_id,
            rec,
            system,
            coll,
            COLLECTION_CATEGORY.get(coll),
            cap,
            lines.get(id(rec), ""),
            r,
        )
    r.coverage.append(Coverage(file_id, cap, system, coll))
    return r
