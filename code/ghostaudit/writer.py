"""output.csv writer: exact header, natural numeric case_id order, compact JSON in schema key order, \\n endings."""
import csv
import json

HEADER = ["case_id", "deletion_status", "steps_json"]
STEP_KEYS = ["step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"]


def natural_key(case_id):
    prefix, _, num = case_id.rpartition("_")
    return (prefix, int(num)) if num.isdigit() else (case_id, -1)


def steps_json(steps):
    return json.dumps([{k: s[k] for k in STEP_KEYS} for s in steps], separators=(",", ":"), ensure_ascii=False)


def write(path, rows):
    """rows: iterable of (case_id, status, steps). Written sorted by natural case_id (ADR 0001)."""
    rows = sorted(rows, key=lambda r: natural_key(r[0]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        for case_id, status, steps in rows:
            w.writerow([case_id, status, steps_json(steps)])
