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

from __future__ import annotations

import json
import re
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence

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

# (line number, timestamp, fields, raw line, (service, trace_id) or None)
LogRecord = tuple[int, str, dict[str, str], str, tuple[str, str] | None]
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


def _logfmt_fields(g: Sequence[str]) -> dict[str, str]:
    return logfmt(g[1])


def _json_fields(g: Sequence[str]) -> dict[str, str] | None:
    """Scalar JSON fields as lower-cased booleans and strings; None when the JSON is broken."""
    try:
        data = json.loads(g[1])
    except json.JSONDecodeError:
        return None
    scalars = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
    return {
        k: (str(v).lower() if isinstance(v, bool) else str(v))
        for k, v in scalars.items()
        if v is not None
    }


def _syslog_fields(g: Sequence[str]) -> dict[str, str]:
    f = logfmt(g[3])
    f.update(service=g[1], trace_id=g[2])
    return f


def _columns_fields(g: Sequence[str]) -> dict[str, str]:
    """bracket and pipe: level, service, trace and event are columns; the rest is logfmt."""
    f = logfmt(g[5])
    f.update(level=g[1], service=g[2], trace_id=g[3], event=g[4])
    return f


def _cloud_fields(g: Sequence[str]) -> dict[str, str]:
    f = logfmt(g[4].replace('\\"', '"'))
    f.update(trace_id=g[1], level=g[2], service=g[3])
    return f


FIELDS: dict[str, Callable[[Sequence[str]], dict[str, str] | None]] = {
    "logfmt": _logfmt_fields,
    "json": _json_fields,
    "syslog": _syslog_fields,
    "bracket": _columns_fields,
    "pipe": _columns_fields,
    "cloud": _cloud_fields,
}


def parse_line(line: str) -> tuple[str, dict[str, str]] | None:
    """-> (ts, fields) with fields['service'] / ['trace_id'] / ['event'] filled in, or None. The
    first dialect whose pattern matches decides; a broken JSON payload rejects the line."""
    for name, rx in DIALECTS:
        m = rx.match(line)
        if not m:
            continue
        g = m.groups()
        f = FIELDS[name](g)
        if f is None:
            return None
        if f.get("trace_id") == "-":
            del f["trace_id"]
        return (g[0], f) if f.get("service") and f.get("event") else None
    return None


def state(f: Mapping[str, str]) -> str:
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


def matches(text: str) -> bool:
    """Every line is timestamped and at least one is in a known dialect; the rest surface as
    unparsed."""
    lines = [text_line for text_line in text.splitlines() if text_line.strip()]
    return (
        bool(lines)
        and all(TS_LINE.match(text_line) for text_line in lines)
        and any(parse_line(text_line) for text_line in lines)
    )


def _owner_keys(f: Mapping[str, str]) -> list[str]:
    """The owner-key values a *_started line names (lookup_key, match_key, ..., subject_ref)."""
    return [v for k, v in f.items() if k.endswith("_key") or k == "subject_ref"]


def _scan(
    file_id: str, text: str, r: LoadResult
) -> tuple[OrderedDict[tuple[str, str], list[str]], list[LogRecord]]:
    """One pass over the lines: owner keys of each (service, trace) from its *_started lines, and
    the lines that carry a resource_id. Lines in no dialect are recorded as unparsed."""
    keys: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
    records: list[LogRecord] = []
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
            keys.setdefault(trace, []).extend(_owner_keys(f))
        if "resource_id" in f:
            records.append((n, ts, f, line, trace))
    return keys, records


def _exposed(f: Mapping[str, str]) -> tuple[str, ...]:
    """Direct identifiers the record shows: its PII fields plus the kind of a matched_value."""
    matched = (
        {kind(f["matched_value"])} & {"email", "phone", "email_hash"}
        if "matched_value" in f
        else set()
    )
    shown = set(pii_fields(f)) | matched
    return tuple(p for p in ("name", "email", "phone", "email_hash") if p in shown)


def load(file_id: str, captured_at: str, text: str) -> LoadResult:
    r = LoadResult("log:observability")
    keys, records = _scan(file_id, text, r)
    for n, ts, f, raw, trace in records:
        ids = identifiers(*(keys.get(trace, ()) if trace else ()), *f.values())
        service = f["service"]
        r.observations.append(
            Observation(
                file_id,
                ts,
                SERVICE_SYSTEM.get(service, service),
                f["resource_id"],
                f"{service}.log",
                state(f),
                pii_fields=_exposed(f),
                identifiers=ids,
                locator=f"line {n}",
                attrs=tuple(sorted(attrs(f, exclude=NOISE) + (("event", f["event"]),))),
            )
        )
        if not ids:
            r.unattributed.append(Unit(file_id, f"line {n}", raw, "no identifier"))
    return r
