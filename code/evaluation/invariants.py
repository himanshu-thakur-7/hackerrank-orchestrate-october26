"""T16 invariants that must hold on every output row, with no labels needed.

  check(output_path, data_dir) -> {invariant id: [violation, ...]}

I1 cited evidence exists in the manifest and is captured at or before the case's audit_at (ADR 0002)
I2 every finding has its remediation and verification on the same resource; every remediation has a
finding I3 COMPLETE rows hold only VERIFICATION steps, each with evidence I4 no step cites an
activity_id or audit_id (claims are never proof, ADR 0006) I5 no case or evidence id literal in
code/ (literal audit) I6 status matches steps: NOT_APPLICABLE <=> []; COMPLETE has no finding;
INCOMPLETE has a finding, or is [] (ADR 0015) I7 the cited file names the resource (an observation
of it), or covers its system (absence by omission) I8 a resource id's prefix agrees with its
system_id wherever the prefix has an owning system I9 in INCOMPLETE rows, remediation and
verification steps are uncited (future work)
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


def check(output_path, data_dir):
    sys.path.insert(0, str(ROOT / "code"))
    from evaluation import audit
    from ghostaudit.engine import Engine
    from ghostaudit.loaders.common import system_of

    d = Path(data_dir)
    eng = Engine.from_dataset(d)
    files = eng.store.files
    named = {}
    for o in eng.store.observations:
        named.setdefault(o.file_id, set()).add((o.system_id, o.resource_id))
    covers = {}
    for c in eng.store.coverage:
        covers.setdefault(c.file_id, set()).add(c.system_id)
    audit_at = {}
    for name in ("deletion_requests.csv", "sample_deletion_requests.csv"):
        if (d / name).exists():
            with open(d / name, newline="", encoding="utf-8") as f:
                audit_at.update({r["case_id"]: r["audit_at"] for r in csv.DictReader(f)})
    v = {k: [] for k in NAMES}
    v["I5.no_literals_in_code"] = audit.scan(ROOT / "code")
    with open(output_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        c, st, steps = r["case_id"], r["deletion_status"], json.loads(r["steps_json"])
        phases = [s["phase"] for s in steps]
        for s in steps:
            ev, res = s["evidence_id"], (s["system_id"], s["resource_id"])
            where = f"{c} step {s['step_no']} {s['operation']} {s['system_id']}/{s['resource_id']}"
            if ev.startswith(("activity_", "audit_")):
                v["I4.no_claim_citation"].append(f"{where} cites {ev}")
            elif ev:
                if ev not in files:
                    v["I1.evidence_exists_pre_audit"].append(
                        f"{where}: {ev} is not in the manifest"
                    )
                elif files[ev].captured_at > audit_at.get(c, ""):
                    v["I1.evidence_exists_pre_audit"].append(
                        f"{where}: {ev} captured {files[ev].captured_at} > audit_at "
                        f"{audit_at.get(c)}"
                    )
                elif res not in named.get(ev, set()) and s["system_id"] not in covers.get(
                    ev, set()
                ):
                    v["I7.citation_names_resource"].append(
                        f"{where}: {ev} neither names nor covers it"
                    )
            sysid = system_of(s["resource_id"])
            if sysid and sysid != s["system_id"]:
                v["I8.prefix_matches_system"].append(f"{where}: prefix says {sysid}")
            if st == "INCOMPLETE" and s["phase"] != "FINDING" and ev:
                v["I9.incomplete_plan_uncited"].append(f"{where} cites {ev}")
        if st == "COMPLETE" and (
            any(p != "VERIFICATION" for p in phases) or any(not s["evidence_id"] for s in steps)
        ):
            v["I3.complete_is_cited_verification"].append(
                f"{c}: COMPLETE with {sorted(set(phases))} / uncited step"
            )
        if (
            (st == "NOT_APPLICABLE" and steps)
            or (st == "COMPLETE" and (not steps or "FINDING" in phases))
            or (st == "INCOMPLETE" and steps and "FINDING" not in phases)
        ):
            v["I6.status_matches_steps"].append(
                f"{c}: {st} with phases {sorted(set(phases)) or '[]'}"
            )
        by_res = {}
        for s in steps:
            by_res.setdefault((s["system_id"], s["resource_id"]), set()).add(s["phase"])
        for res, ph in by_res.items():
            if "FINDING" in ph and not {"REMEDIATION", "VERIFICATION"} <= ph:
                v["I2.finding_has_plan"].append(f"{c} {res[0]}/{res[1]}: {sorted(ph)}")
            if "REMEDIATION" in ph and "FINDING" not in ph:
                v["I2.finding_has_plan"].append(
                    f"{c} {res[0]}/{res[1]}: remediation without finding"
                )
    v["rows"] = len(rows)
    return v


def run(output_path, data_dir):
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
