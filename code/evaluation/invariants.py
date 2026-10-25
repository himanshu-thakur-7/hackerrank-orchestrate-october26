"""Invariants that must hold on every output row, with no labels needed.

check(output_path, data_dir) -> {invariant id: [violation, ...]}

I1 cited evidence exists in the manifest and is captured at or before the case's audit_at
   (ADR 0002)
I2 every finding has its remediation and verification on the same resource; every remediation
   has a finding
I3 COMPLETE rows hold only VERIFICATION steps, each with evidence
I4 no step cites an activity_id or audit_id (claims are never proof, ADR 0006)
I5 no case or evidence id literal in code/ (literal audit)
I6 status matches steps: NOT_APPLICABLE <=> []; COMPLETE has no finding; INCOMPLETE has a
   finding, or is [] (ADR 0015)
I7 the cited file names the resource (an observation of it), or covers its system (absence by
   omission)
I8 a resource id's prefix agrees with its system_id wherever the prefix has an owning system
I9 in INCOMPLETE rows, remediation and verification steps are uncited (future work)
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = {
    "I1.evidence_exists_pre_audit": "cited evidence exists and is <= audit_at",
    "I2.finding_has_plan": "finding -> remediation + verification",
    "I3.complete_is_cited_verification": "COMPLETE = cited verification only",
    "I4.no_claim_citation": "no activity_id / audit_id cited",
    "I5.no_literals_in_code": "no case/evidence literals in code/",
    "I6.status_matches_steps": "status consistent with steps",
    "I7.citation_names_resource": "cited file names the resource (or covers it)",
    "I8.prefix_matches_system": "resource prefix matches system_id",
    "I9.incomplete_plan_uncited": "INCOMPLETE remediation/verification uncited",
}


class _Context:
    """What the citation checks need: manifest files, which file names or covers what, cutoffs."""

    def __init__(self, d):
        from ghostaudit.engine import Engine

        eng = Engine.from_dataset(d)
        self.files = eng.store.files
        self.named, self.covers, self.audit_at = {}, {}, {}
        for o in eng.store.observations:
            self.named.setdefault(o.file_id, set()).add((o.system_id, o.resource_id))
        for c in eng.store.coverage:
            self.covers.setdefault(c.file_id, set()).add(c.system_id)
        for name in ("deletion_requests.csv", "sample_deletion_requests.csv"):
            if (d / name).exists():
                with open(d / name, newline="", encoding="utf-8") as f:
                    self.audit_at.update({r["case_id"]: r["audit_at"] for r in csv.DictReader(f)})


def _citation_violation(ctx, c, s, where):
    """(invariant, message) for a cited step, or None (I1, I4, I7)."""
    ev, res = s["evidence_id"], (s["system_id"], s["resource_id"])
    if ev.startswith(("activity_", "audit_")):
        return "I4.no_claim_citation", f"{where} cites {ev}"
    if ev not in ctx.files:
        return "I1.evidence_exists_pre_audit", f"{where}: {ev} is not in the manifest"
    if ctx.files[ev].captured_at > ctx.audit_at.get(c, ""):
        return (
            "I1.evidence_exists_pre_audit",
            f"{where}: {ev} captured {ctx.files[ev].captured_at} > audit_at {ctx.audit_at.get(c)}",
        )
    if res not in ctx.named.get(ev, set()) and s["system_id"] not in ctx.covers.get(ev, set()):
        return "I7.citation_names_resource", f"{where}: {ev} neither names nor covers it"
    return None


def _check_steps(ctx, c, st, steps, v, system_of):
    for s in steps:
        ev = s["evidence_id"]
        where = f"{c} step {s['step_no']} {s['operation']} {s['system_id']}/{s['resource_id']}"
        found = _citation_violation(ctx, c, s, where) if ev else None
        if found:
            v[found[0]].append(found[1])
        sysid = system_of(s["resource_id"])
        if sysid and sysid != s["system_id"]:
            v["I8.prefix_matches_system"].append(f"{where}: prefix says {sysid}")
        if st == "INCOMPLETE" and s["phase"] != "FINDING" and ev:
            v["I9.incomplete_plan_uncited"].append(f"{where} cites {ev}")


def _status_mismatch(st, steps, phases):
    return (
        (st == "NOT_APPLICABLE" and steps)
        or (st == "COMPLETE" and (not steps or "FINDING" in phases))
        or (st == "INCOMPLETE" and steps and "FINDING" not in phases)
    )


def _check_row(c, st, steps, v):
    """Row-level invariants: I3, I6 and I2."""
    phases = [s["phase"] for s in steps]
    uncited = any(not s["evidence_id"] for s in steps)
    if st == "COMPLETE" and (any(p != "VERIFICATION" for p in phases) or uncited):
        v["I3.complete_is_cited_verification"].append(
            f"{c}: COMPLETE with {sorted(set(phases))} / uncited step"
        )
    if _status_mismatch(st, steps, phases):
        v["I6.status_matches_steps"].append(f"{c}: {st} with phases {sorted(set(phases)) or '[]'}")
    by_res = {}
    for s in steps:
        by_res.setdefault((s["system_id"], s["resource_id"]), set()).add(s["phase"])
    for res, ph in by_res.items():
        if "FINDING" in ph and not {"REMEDIATION", "VERIFICATION"} <= ph:
            v["I2.finding_has_plan"].append(f"{c} {res[0]}/{res[1]}: {sorted(ph)}")
        if "REMEDIATION" in ph and "FINDING" not in ph:
            v["I2.finding_has_plan"].append(f"{c} {res[0]}/{res[1]}: remediation without finding")


def check(output_path, data_dir):
    """{invariant id: [violations]} over every row of `output_path`; 'rows' holds the count."""
    sys.path.insert(0, str(ROOT / "code"))
    from ghostaudit.loaders.common import system_of

    from evaluation import audit

    ctx = _Context(Path(data_dir))
    v = {k: [] for k in NAMES}
    v["I5.no_literals_in_code"] = audit.scan(ROOT / "code")
    with open(output_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        c, st, steps = r["case_id"], r["deletion_status"], json.loads(r["steps_json"])
        _check_steps(ctx, c, st, steps, v, system_of)
        _check_row(c, st, steps, v)
    v["rows"] = len(rows)
    return v


def run(output_path, data_dir):
    """`main.py invariants`: print each invariant and its violations; exit 0 when none fail."""
    v = check(output_path, data_dir)
    n = v.pop("rows")
    print(f"INVARIANTS over {n} rows of {Path(output_path).name}")
    for k, desc in NAMES.items():
        bad = v[k]
        rows_bad = len({x.split()[0] for x in bad}) if not k.startswith("I5") else len(bad)
        print(
            f"  {k:36} {'OK  ' if not bad else 'FAIL'} {desc}"
            + (
                f": {rows_bad} violation(s)"
                if bad
                else ("" if k.startswith("I5") else f" ({n}/{n})")
            )
        )
        for x in bad[:5]:
            print(f"      {x}")
    return 0 if not any(v.values()) else 1
