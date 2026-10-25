"""L0 contract gate: hard, format-level and rule-level checks on an output CSV.

check(output_path, requests_path, manifest_path) -> list[str]
An empty list means the file passes. Each violation starts with a stable code (e.g. "L0.header").
"""

import csv
import io
import json
from pathlib import Path

# warnings that only say an optional dependency is absent on this machine (never a property of the
# file)
OPTIONAL_DEPENDENCY_WARNINGS = ("L0.pandas SKIPPED",)

HEADER = ["case_id", "deletion_status", "steps_json"]
STATUSES = ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")
KEYS = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}
# (phase, operation, state) in contract order; the index is the operation rank used by the sort key
TRIPLES = [
    ("FINDING", "REPORT_REMAINING_RECORD", "PRESENT"),
    ("FINDING", "REPORT_EXPOSED_PII", "PRESENT"),
    ("FINDING", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE"),
    ("FINDING", "REPORT_RESTORE_RISK", "ACTIVE"),
    ("REMEDIATION", "DISABLE_DATA_FLOW", "DISABLED"),
    ("REMEDIATION", "BLOCK_RESTORE", "BLOCKED"),
    ("REMEDIATION", "DELETE_RECORD", "ABSENT"),
    ("REMEDIATION", "REDACT_RECORD", "REDACTED"),
    ("REMEDIATION", "ANONYMIZE_RECORD", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_RECORD_ABSENT", "ABSENT"),
    ("VERIFICATION", "VERIFY_RECORD_PRESENT", "PRESENT"),
    ("VERIFICATION", "VERIFY_RECORD_REDACTED", "REDACTED"),
    ("VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
    ("VERIFICATION", "VERIFY_RESTORE_BLOCKED", "BLOCKED"),
]
OP_RANK = {op: i for i, (_, op, _) in enumerate(TRIPLES)}
TRIPLE_SET = set(TRIPLES)
# remediation -> the finding(s) that justify it and the verification that must follow it
REMEDIATION_PAIRS = {
    "DISABLE_DATA_FLOW": ({"REPORT_ACTIVE_DATA_FLOW"}, "VERIFY_DATA_FLOW_DISABLED"),
    "BLOCK_RESTORE": ({"REPORT_RESTORE_RISK"}, "VERIFY_RESTORE_BLOCKED"),
    "DELETE_RECORD": ({"REPORT_REMAINING_RECORD"}, "VERIFY_RECORD_ABSENT"),
    "REDACT_RECORD": ({"REPORT_EXPOSED_PII"}, "VERIFY_RECORD_REDACTED"),
    "ANONYMIZE_RECORD": ({"REPORT_EXPOSED_PII"}, "VERIFY_RECORD_ANONYMIZED"),
}


def check(output_path, requests_path, manifest_path, warnings=None):
    """Return the list of violations. Non-fatal notes (e.g. a skipped optional check) go to
    `warnings`."""
    raw = Path(output_path).read_bytes()
    v = _format(raw, warnings if warnings is not None else [])
    if v:
        return v
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))[1:]
    requests = _read_csv(requests_path)
    v += _cases(rows, requests)
    audit_at = {r["case_id"]: r["audit_at"] for r in requests}
    times = _evidence_times(Path(manifest_path))
    for case_id, status, steps_json in rows:
        if case_id in audit_at:
            v += _row(case_id, status, steps_json, audit_at[case_id], times)
    # ADR 0015 (proposed): INCOMPLETE with [] means nothing grounded could be reported; allowed, but
    # counted
    empty = [c for c, st, sj in rows if st == "INCOMPLETE" and sj.strip() == "[]"]
    if empty and warnings is not None:
        warnings.append(
            f"L0.empty_incomplete: {len(empty)} INCOMPLETE row(s) with no steps (ADR 0015): "
            f"{', '.join(empty)}"
        )
    return v


def _evidence_times(manifest_path):
    """Every citable participant-visible id -> the time it became available."""
    t = {r["file_id"]: r["captured_at"] for r in _read_csv(manifest_path)}
    d = manifest_path.parent
    for name, key, ts in (
        ("system_activity.csv", "activity_id", "event_time"),
        ("user_audit_log.csv", "audit_id", "event_time"),
    ):
        if (d / name).exists():
            t.update({r[key]: r[ts] for r in _read_csv(d / name)})
    return t


def _parse(case_id, status, steps_json):
    """(steps, []) for a parsable row, or (None, [violation]) for a bad status or JSON."""
    if status not in STATUSES:
        return None, [
            f"L0.status: {case_id}: deletion_status '{status}' is not one of {', '.join(STATUSES)}"
        ]
    try:
        steps = json.loads(steps_json)
    except json.JSONDecodeError as e:
        return None, [f"L0.json: {case_id}: steps_json is not valid JSON ({e.msg} at char {e.pos})"]
    if not isinstance(steps, list):
        return None, [f"L0.json: {case_id}: steps_json must be a JSON array"]
    return steps, []


def _key_violations(case_id, steps):
    v = []
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict) or set(s) != KEYS:
            extra = sorted(set(s) - KEYS) if isinstance(s, dict) else []
            missing = sorted(KEYS - set(s)) if isinstance(s, dict) else sorted(KEYS)
            v.append(
                f"L0.keys: {case_id} step {i}: needs exactly the 7 keys; extra={extra} "
                f"missing={missing}"
            )
    return v


def _step_no_violation(case_id, steps):
    for i, s in enumerate(steps, 1):
        if type(s["step_no"]) is not int or s["step_no"] != i:
            return [
                f"L0.step_no: {case_id}: step at position {i} has step_no {s['step_no']!r}; must "
                f"be the integer {i}"
            ]
    return []


def _shape_violations(case_id, steps):
    """step_no 1..n, an allowed (phase, operation, state) triple, non-empty system/resource ids."""
    v = _step_no_violation(case_id, steps)
    for s in steps:
        if (s["phase"], s["operation"], s["state"]) not in TRIPLE_SET:
            v.append(
                f"L0.triple: {case_id} step {s['step_no']}: ({s['phase']}, {s['operation']}, "
                f"{s['state']}) is not an allowed phase/operation/state triple"
            )
        for k in ("system_id", "resource_id"):
            if not isinstance(s[k], str) or not s[k]:
                v.append(f"L0.keys: {case_id} step {s['step_no']}: {k} must be a non-empty string")
    return v


def _sort_violation(case_id, steps):
    """The first step out of (operation rank, system_id, resource_id) order, if any."""
    keys = [(OP_RANK[s["operation"]], s["system_id"], s["resource_id"]) for s in steps]
    for a in range(1, len(keys)):
        if keys[a] < keys[a - 1]:
            return [
                f"L0.sort: {case_id}: step {a + 1} ({steps[a]['operation']} "
                f"{steps[a]['system_id']}/{steps[a]['resource_id']}) "
                f"must not come after step {a} ({steps[a - 1]['operation']} "
                f"{steps[a - 1]['system_id']}/{steps[a - 1]['resource_id']}); "
                f"order is phase, operation rank, system_id, resource_id"
            ]
    return []


def _status_violations(case_id, status, steps):
    v = []
    phases = {s["phase"] for s in steps}
    if status == "NOT_APPLICABLE" and steps:
        v.append(
            f"L0.status: {case_id}: NOT_APPLICABLE must have steps_json [] (has {len(steps)} steps)"
        )
    if status == "COMPLETE" and not steps:
        v.append(
            f"L0.status: {case_id}: COMPLETE with an empty step list; COMPLETE needs cited "
            f"verification steps"
        )
    if status == "COMPLETE" and phases - {"VERIFICATION"}:
        v.append(
            f"L0.status: {case_id}: COMPLETE may contain only VERIFICATION steps (found "
            f"{', '.join(sorted(phases - {'VERIFICATION'}))})"
        )
    return v


def _row(case_id, status, steps_json, audit_at, times):
    """Violations of one row, checked in layers; a layer that fails stops the deeper ones."""
    steps, v = _parse(case_id, status, steps_json)
    if steps is None:
        return v
    v = _key_violations(case_id, steps) or _shape_violations(case_id, steps)
    if v:
        return v
    v = _sort_violation(case_id, steps) + _status_violations(case_id, status, steps)
    v += _evidence(case_id, status, steps, audit_at, times)
    if status == "INCOMPLETE":
        v += _pairing(case_id, steps)
    return v


def _evidence(case_id, status, steps, audit_at, times):
    v = []
    for s in steps:
        e = s["evidence_id"]
        where = f"{case_id} step {s['step_no']} ({s['operation']})"
        if e is None:
            v.append(
                f'L0.evidence: {where}: evidence_id is null; use a string ("" for '
                f"remediation/future verification)"
            )
            continue
        if not isinstance(e, str):
            v.append(f"L0.evidence: {where}: evidence_id must be a string, got {type(e).__name__}")
            continue
        must_cite = s["phase"] == "FINDING" or status == "COMPLETE"
        if must_cite:
            if not e:
                kind = "finding" if s["phase"] == "FINDING" else "COMPLETE verification"
                v.append(
                    f"L0.evidence: {where}: a {kind} must cite a file_id, activity_id or audit_id"
                )
            elif e not in times:
                v.append(
                    f"L0.evidence: {where}: evidence_id '{e}' does not exist in the participant "
                    f"data"
                )
            elif times[e] > audit_at:
                v.append(
                    f"L0.evidence: {where}: '{e}' is captured at {times[e]}, after audit_at "
                    f"{audit_at}"
                )
        elif e != "":
            v.append(
                f"L0.evidence: {where}: in an INCOMPLETE case this step describes future work; "
                f"evidence_id must be \"\" (got '{e}')"
            )
    return v


def _pairing(case_id, steps):
    v = []
    by_res = {}
    for s in steps:
        by_res.setdefault((s["system_id"], s["resource_id"]), set()).add(s["operation"])
    for s in steps:
        if s["phase"] != "REMEDIATION":
            continue
        finds, verify = REMEDIATION_PAIRS[s["operation"]]
        ops = by_res[(s["system_id"], s["resource_id"])]
        res = f"{s['system_id']}/{s['resource_id']}"
        if not ops & finds:
            v.append(
                f"L0.pairing: {case_id}: remediation {s['operation']} on {res} has no matching "
                f"finding ({' or '.join(sorted(finds))})"
            )
        if verify not in ops:
            v.append(
                f"L0.pairing: {case_id}: remediation {s['operation']} on {res} has no matching "
                f"verification {verify}"
            )
    return v


def natural_key(case_id):
    prefix, _, num = case_id.rpartition("_")
    return (prefix, int(num)) if num.isdigit() else (case_id, -1)


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _order_violation(got, want):
    """The first known case_id row that breaks natural numeric order, if any."""
    for i in range(1, len(got)):
        if got[i] in want and got[i - 1] in want and natural_key(got[i]) < natural_key(got[i - 1]):
            return [
                f"L0.order: {got[i]} (data row {i + 1}) comes after {got[i - 1]}; rows must be in "
                f"natural numeric case_id order"
            ]
    return []


def _cases(rows, requests):
    v = []
    want = [r["case_id"] for r in requests]
    got = [r[0] for r in rows]
    seen = set()
    dups = sorted({c for c in got if c in seen or seen.add(c)}, key=natural_key)
    if dups:
        v.append(f"L0.cases: duplicate case_id rows: {', '.join(dups)}")
    missing = sorted(set(want) - set(got), key=natural_key)
    if missing:
        v.append(
            f"L0.cases: missing {len(missing)} case_id(s) from the input: {', '.join(missing[:10])}"
        )
    unknown = sorted(set(got) - set(want), key=natural_key)
    if unknown:
        v.append(f"L0.cases: unknown case_id(s) not in the input: {', '.join(unknown[:10])}")
    v += _order_violation(got, set(want))
    if len(got) != len(want) and not (missing or unknown or dups):
        v.append(f"L0.cases: expected {len(want)} rows, got {len(got)}")
    return v


def _format(raw, warnings):
    if raw.startswith(b"\xef\xbb\xbf"):
        return ["L0.encoding: file starts with a UTF-8 BOM; write plain UTF-8"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return [f"L0.encoding: not valid UTF-8 at byte {e.start}"]
    if "\r" in text:
        line = text[: text.index("\r")].count("\n") + 1
        return [f"L0.line_endings: carriage return found on line {line}; use \\n only"]
    if not text.endswith("\n"):
        return ["L0.line_endings: file must end with a single \\n"]
    first = text.split("\n", 1)[0]
    if first != ",".join(HEADER):
        return [f"L0.header: expected '{','.join(HEADER)}', got '{first}'"]
    rows = list(csv.reader(io.StringIO(text)))
    for i, r in enumerate(rows, 1):
        if len(r) != 3:
            return [
                f"L0.csv: line {_physical_line(text, i)} parses to {len(r)} fields, expected 3 "
                f"(check quoting of steps_json)"
            ]
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    if buf.getvalue() != text:
        a, b = text.split("\n"), buf.getvalue().split("\n")
        n = next(
            (k for k, (x, y) in enumerate(zip(a, b, strict=False)) if x != y), min(len(a), len(b))
        )
        return [
            f"L0.csv: line {n + 1} does not round-trip through the csv module (quoting differs)"
        ]
    try:
        import pandas as pd  # optional: the stdlib csv round-trip above is the mandatory check
    except ImportError:
        warnings.append(
            f"{OPTIONAL_DEPENDENCY_WARNINGS[0]}: pandas is not installed; optional pandas "
            f"round-trip not run (stdlib csv round-trip passed)"
        )
        return []
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    if df.to_csv(index=False, lineterminator="\n") != text:
        return [
            "L0.pandas: file does not round-trip identically through pandas (dtype=str, "
            "keep_default_na=False)"
        ]
    return []


def _physical_line(text, record_no):
    """1-based physical line where CSV record number record_no starts."""
    reader = csv.reader(io.StringIO(text))
    line = 1
    for k, _ in enumerate(reader, 1):
        if k == record_no:
            return line
        line = reader.line_num + 1
    return line


def determinism(cmd, output_path, runs=2):
    """Run cmd `runs` times; pass iff each run exits 0 and output_path has the same sha256 every
    time."""
    import hashlib
    import subprocess

    hashes = []
    for k in range(runs):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            return (
                False,
                hashes,
                f"L0.determinism: run {k + 1} failed (exit {p.returncode}): "
                f"{p.stderr.strip()[-300:]}",
            )
        hashes.append(hashlib.sha256(Path(output_path).read_bytes()).hexdigest())
    if len(set(hashes)) != 1:
        return (
            False,
            hashes,
            "L0.determinism: output differs between runs: " + " vs ".join(h[:12] for h in hashes),
        )
    return True, hashes, f"L0.determinism: {runs} runs identical (sha256 {hashes[0][:12]})"
