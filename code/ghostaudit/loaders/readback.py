"""Readback trace logs (logfmt): '<ts> level=.. service=<system> trace_id=.. event=<x>_started
resource_id=.. lookup_key=..' followed by '<x>_completed' with the state fields. The lookup key
(owner) is joined to the completed record through trace_id. Not exhaustive: no Coverage.
"""

import re
from collections import OrderedDict

from ghostaudit.loaders.common import (
    LoadResult,
    Unit,
    attrs,
    identifiers,
    logfmt,
    pii_fields,
    state_from_fields,
)
from ghostaudit.store import Observation

LINE_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) (level=\w+ service=\w+ .*)$")
# readback grammar: nothing between service= and (trace_id=) event=; observability logfmt has
# instance=/pod=/region= there
GRAMMAR_RE = re.compile(
    r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ level=\w+ service=\w+ (?:trace_id=\S+ )?event=\w+"
)


def matches(text):
    lines = [text_line for text_line in text.splitlines() if text_line.strip()]
    return (
        bool(lines)
        and all(GRAMMAR_RE.match(text_line) for text_line in lines)
        and any("lookup_key=" in text_line for text_line in lines)
    )


def _traces(file_id, text, r):
    """trace_id -> [(line no, ts, fields, raw line)] in file order. Lines outside the grammar are
    unparsed; collector lines without a trace are not records."""
    traces = OrderedDict()
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        if not m:
            r.unparsed.append(Unit(file_id, f"line {n}", line, "not a readback log line"))
            continue
        f = logfmt(m.group(2))
        if "trace_id" in f:
            traces.setdefault(f["trace_id"], []).append((n, m.group(1), f, line))
    return traces


def _trace_records(file_id, tid, lines, r):
    """Observations for the completed events of one trace, owned by the trace's lookup keys."""
    keys = [f.get("lookup_key") for _, _, f, _ in lines if f.get("event", "").endswith("_started")]
    done = [(n, ts, f, raw) for n, ts, f, raw in lines if f.get("event", "").endswith("_completed")]
    if not done:
        n, _, _, raw = lines[0]
        r.unparsed.append(Unit(file_id, f"line {n}", raw, f"trace {tid} has no completed event"))
        return
    for n, ts, f, raw in done:
        if "resource_id" not in f:
            r.unparsed.append(
                Unit(file_id, f"line {n}", raw, "completed event without resource_id")
            )
            continue
        ids = identifiers(*keys, *f.values())
        r.observations.append(
            Observation(
                file_id,
                ts,
                f["service"],
                f["resource_id"],
                f"{f['service']}.readback",
                state_from_fields(f),
                pii_fields=pii_fields(f),
                identifiers=ids,
                locator=f"line {n}",
                attrs=attrs(f),
            )
        )
        if not ids:
            r.unattributed.append(Unit(file_id, f"line {n}", raw, "no identifier"))


def load(file_id, captured_at, text):
    r = LoadResult("log:readback")
    for tid, lines in _traces(file_id, text, r).items():
        _trace_records(file_id, tid, lines, r)
    return r
