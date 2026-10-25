"""Shared fixtures for evaluation tests: copies of the labeled sample, optionally broken."""

import csv
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "dataset"
GOLD = DATA / "sample_output.csv"
SAMPLE_REQ = DATA / "sample_deletion_requests.csv"
MANIFEST = DATA / "evidence_files.csv"


def gold_rows():
    with open(GOLD, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def write_rows(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def tmp_copy(name="out.csv", raw=None, rows=None):
    d = Path(tempfile.mkdtemp(prefix="ghostaudit_test_"))
    p = d / name
    if raw is not None:
        p.write_bytes(raw)
    else:
        write_rows(rows if rows is not None else gold_rows(), p)
    return p


def mutate_step(rows, case_id, at, **changes):
    """Return a copy of rows with one step's fields changed (None -> JSON null)."""
    out = [list(r) for r in rows]
    for r in out[1:]:
        if r[0] == case_id:
            steps = json.loads(r[2])
            for s in steps:
                if s["step_no"] == at:
                    s.update(changes)
            r[2] = json.dumps(steps, separators=(",", ":"))
    return out


def required_warnings(warnings):
    """Gate warnings minus those that only report an absent optional dependency
    (machine-dependent)."""
    from evaluation.gate import OPTIONAL_DEPENDENCY_WARNINGS

    return [w for w in warnings if not w.startswith(OPTIONAL_DEPENDENCY_WARNINGS)]
