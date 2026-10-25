"""Observability logs: service query traces in seven line dialects, all normalised to
(ts, service, trace, fields) before one shared trace join:

  logfmt   '<ts> level=X service=S ... trace_id=T event=E k=v ...'
  json     '<ts> {"severity":..,"service":S,"trace_id":T,"event":E,...}'
  syslog   '<ts> <PRI>1 node S T - - level=X k="v" ...'
  bracket  '<ts> [LEVEL] [S] [T] event: k="v" ...'
  pipe     '<ts> | LEVEL | S | T | event | k="v" ...'
  cloud    '<ts> requestId=T level=X function=S message="k=\\"v\\" ..."'

A record is a line carrying resource_id; observed_at is that line's timestamp (ADR 0002). Its owner
identifiers are its own identifier-valued fields plus the keys of the *_started line(s) of the same
(service, trace): lookup_key, match_key, subject_key, subject_ref, scan_key, owner_key. Only exact
identifiers count, so a lookup_key that is itself a resource id attributes nothing.

Not exhaustive (a trace log only shows what was queried): no Coverage.
"""

import json
import re
from collections import OrderedDict

from ghostaudit.loaders.common import (
    LoadResult,
    Unit,
    attrs,
    identifiers,
    kind,
    logfmt,
    pii_fields,
    state_from_fields,
)
from ghostaudit.store import Observation

TS = r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)"
DIALECTS = (
    ("logfmt", re.compile(TS + r" (level=\w+ service=\S+ .*)$")),
    ("json", re.compile(TS + r" (\{.*\})$")),
    ("syslog", re.compile(TS + r" <\d+>1 \S+ (\S+) (\S+) - - (.*)$")),
    ("bracket", re.compile(TS + r" \[(\w+)\] \[(\S+)\] \[(\S+)\] (\w+): (.*)$")),
    ("pipe", re.compile(TS + r" \| (\w+) \| (\S+) \| (\S+) \| (\w+) \| (.*)$")),
    ("cloud", re.compile(TS + r' requestId=(\S+) level=(\w+) function=(\S+) message="(.*)"$')),
)
# services that log on behalf of a catalogue system under another name
SERVICE_SYSTEM = {
    "support_replica": "support_platform",
    "attachment_preview": "support_platform",
    "profile_service": "account_service",
}
NOISE = {"instance", "pod", "region", "severity", "logger", "attempt"}


def parse_line(line):
    """-> (ts, fields) with fields['service'] / ['trace_id'] / ['event'] filled in, or None."""
    for name, rx in DIALECTS:
        m = rx.match(line)
        if not m:
            continue
        g = m.groups()
        if name == "logfmt":
            f = logfmt(g[1])
        elif name == "json":
            try:
                f = {k: v for k, v in json.loads(g[1]).items() if not isinstance(v, (dict, list))}
            except json.JSONDecodeError:
                return None
            f = {
                k: (str(v).lower() if isinstance(v, bool) else str(v))
                for k, v in f.items()
                if v is not None
            }
        elif name == "syslog":
            f = logfmt(g[3])
            f.update(service=g[1], trace_id=g[2])
        elif name in ("bracket", "pipe"):
            f = logfmt(g[5])
            f.update(level=g[1], service=g[2], trace_id=g[3], event=g[4])
        else:
            f = logfmt(g[4].replace('\\"', '"'))
            f.update(trace_id=g[1], level=g[2], service=g[3])
        if f.get("trace_id") == "-":
            del f["trace_id"]
        return (g[0], f) if f.get("service") and f.get("event") else None
    return None


def state(f):
    g = {k: v.lower() for k, v in f.items()}
    if "eligible" in g or "deletion_block" in g:
        return (
            "RESTORABLE"
            if g.get("eligible") == "true" and g.get("deletion_block") != "true"
            else "BLOCKED"
        )
    if g.get("decision") in ("allow", "deny"):
        return "RESTORABLE" if g["decision"] == "allow" else "BLOCKED"
    if g.get("available") == "false":
        return "ABSENT"
    return state_from_fields(f)


TS_LINE = re.compile(TS + " ")


def matches(text):
    """Every line is timestamped and at least one is in a known dialect; the rest surface as
    unparsed."""
    lines = [l for l in text.splitlines() if l.strip()]
    return (
        bool(lines) and all(TS_LINE.match(l) for l in lines) and any(parse_line(l) for l in lines)
    )


def load(file_id, captured_at, text):
    r = LoadResult("log:observability")
    keys, records = OrderedDict(), []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        p = parse_line(line)
        if p is None:
            r.unparsed.append(
                Unit(file_id, f"line {n}", line, "line matches no observability dialect")
            )
            continue
        ts, f = p
        trace = (f["service"], f["trace_id"]) if "trace_id" in f else None
        if f["event"].endswith("_started") and trace:
            keys.setdefault(trace, []).extend(
                v for k, v in f.items() if k.endswith("_key") or k == "subject_ref"
            )
        if "resource_id" in f:
            records.append((n, ts, f, line, trace))
    for n, ts, f, raw, trace in records:
        ids = identifiers(*keys.get(trace, ()), *f.values())
        exposed = (
            {kind(f["matched_value"])} & {"email", "phone", "email_hash"}
            if "matched_value" in f
            else set()
        )
        pii = tuple(
            p for p in ("name", "email", "phone", "email_hash") if p in set(pii_fields(f)) | exposed
        )
        service = f["service"]
        a = tuple(sorted(attrs(f, exclude=NOISE) + (("event", f["event"]),)))
        o = Observation(
            file_id,
            ts,
            SERVICE_SYSTEM.get(service, service),
            f["resource_id"],
            f"{service}.log",
            state(f),
            pii_fields=pii,
            identifiers=ids,
            locator=f"line {n}",
            attrs=a,
        )
        r.observations.append(o)
        if not ids:
            r.unattributed.append(Unit(file_id, f"line {n}", raw, "no identifier"))
    return r
