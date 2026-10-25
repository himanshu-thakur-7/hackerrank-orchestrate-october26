"""Snapshot bundles: {"snapshots": [{captured_at, data_store, collection, records: [...]}]}.

Each data snapshot keeps its OWN captured_at as observed_at (ADR 0002; the store cuts by file).
Data collections, including empty ones, emit Coverage (weak evidence, ADR 0014: a labeled sample
proves an empty customer_profiles list absent). Register-style collections
(operational_record_history) are histories of checks and never emit Coverage.
"""

from __future__ import annotations

import json

from ghostaudit.loaders import datarow, register
from ghostaudit.loaders.common import LoadResult, json_line_map
from ghostaudit.loaders.sql import COLLECTION_CATEGORY
from ghostaudit.store import Coverage


def load(file_id: str, captured_at: str, text: str) -> LoadResult:
    """Parse one evidence file of this format into a LoadResult.

    Inputs: the manifest file_id and captured_at, and the decoded text. Output: Observations
    (and Coverage where the format is exhaustive); record-like units that cannot be used go to
    `unattributed` or `unparsed`, so nothing is dropped silently."""
    data = json.loads(text)
    lines = json_line_map(text, data)
    r = LoadResult("json:snapshots")
    for snap in data["snapshots"]:
        recs = snap.get("records") or []
        cap = snap.get("captured_at") or captured_at
        store, coll = snap["data_store"], snap["collection"]
        if register.is_register(recs):
            for rec in recs:
                register.observation(
                    file_id, rec, f"{store}.{coll}", lines.get(id(rec), ""), cap, r
                )
            continue
        for rec in recs:
            datarow.observation(
                file_id,
                rec,
                store,
                coll,
                COLLECTION_CATEGORY.get(coll),
                cap,
                lines.get(id(rec), ""),
                r,
            )
        r.coverage.append(Coverage(file_id, cap, store, coll))
    return r
