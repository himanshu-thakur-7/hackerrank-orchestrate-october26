"""Service resource export JSON: {"service_exports": {<system>: {<collection>: [record, ...]}}}.

Each record is one probed resource (search records nest the hit documents). A probe list is not
exhaustive, so no Coverage is emitted.
"""
import json
import re

from ghostaudit.loaders.common import LoadResult, Unit, attrs, identifiers, pii_fields, scalar_items, state_from_fields
from ghostaudit.store import Observation

RID_RE = re.compile(r'"resource_id"\s*:\s*"([^"]+)"')


def _ordered_dicts(node, out):
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


def _line_map(text, data):
    hits = [(m.group(1), text.count("\n", 0, m.start()) + 1) for m in RID_RE.finditer(text)]
    order = []
    _ordered_dicts(data, order)
    return {id(d): f"line {ln}" for d, (rid, ln) in zip(order, hits) if d.get("resource_id") == rid}


def load(file_id, captured_at, text):
    data = json.loads(text)
    lines = _line_map(text, data)
    r = LoadResult("json:service_exports")
    for system, collections in data["service_exports"].items():
        for coll, records in collections.items():
            for rec in records:
                observed = rec.get("observed_at") or captured_at
                table = f"{system}.{coll}"
                if "hits" in rec:
                    docs = rec["hits"].get("documents") or []
                    for doc in docs:
                        fields = {**doc}
                        ids = identifiers(*(v for _, v in scalar_items(fields)), rec.get("query"))
                        _add(r, file_id, Observation(file_id, observed, system, doc["resource_id"], table, "PRESENT",
                                                     pii_fields=pii_fields(fields), identifiers=ids,
                                                     locator=lines.get(id(doc), ""), attrs=attrs(fields)), json.dumps(doc))
                    if not docs:
                        _add(r, file_id, Observation(file_id, observed, system, rec["resource_id"], table, "ABSENT",
                                                     identifiers=identifiers(rec.get("query")), locator=lines.get(id(rec), ""),
                                                     attrs=(("total_hits", str(rec["hits"].get("total", 0))),)), json.dumps(rec))
                    continue
                nested = rec.get("profile") if isinstance(rec.get("profile"), dict) else {}
                fields = {**rec, **nested}
                ids = identifiers(*(v for _, v in scalar_items(fields)))
                _add(r, file_id, Observation(file_id, observed, system, rec["resource_id"], table, state_from_fields(rec),
                                             pii_fields=pii_fields(fields), identifiers=ids,
                                             locator=lines.get(id(rec), ""), attrs=attrs(rec)), json.dumps(rec))
    return r


def _add(r, file_id, o, raw):
    r.observations.append(o)
    if not o.identifiers:
        r.unattributed.append(Unit(file_id, o.locator, raw, "no identifier"))
