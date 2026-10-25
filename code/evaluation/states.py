"""T08 acceptance: per-resource state + treatment vs the state that the gold steps imply.

Gold is used here only to EVALUATE; nothing in this module is imported by the solver.

gold-implied state of a resource (from its steps in sample_output.csv):
  finding REPORT_REMAINING_RECORD -> PRESENT, REPORT_EXPOSED_PII -> EXPOSED,
  REPORT_ACTIVE_DATA_FLOW -> ACTIVE, REPORT_RESTORE_RISK -> RESTORABLE;
  otherwise its verification op: cited (COMPLETE) -> that compliant state;
  uncited (INCOMPLETE, no finding) -> "compliant or unproven".
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

FINDING_STATE = {
    "REPORT_REMAINING_RECORD": "PRESENT",
    "REPORT_EXPOSED_PII": "EXPOSED",
    "REPORT_ACTIVE_DATA_FLOW": "ACTIVE",
    "REPORT_RESTORE_RISK": "RESTORABLE",
}
VERIFY_STATE = {
    "VERIFY_RECORD_ABSENT": "ABSENT",
    "VERIFY_RECORD_PRESENT": "RETAINED",
    "VERIFY_RECORD_REDACTED": "CLEAN",
    "VERIFY_RECORD_ANONYMIZED": "CLEAN",
    "VERIFY_DATA_FLOW_DISABLED": "DISABLED",
    "VERIFY_RESTORE_BLOCKED": "BLOCKED",
}


def gold_implied(steps):
    out = {}
    for key in sorted({(s["system_id"], s["resource_id"]) for s in steps}):
        mine = [s for s in steps if (s["system_id"], s["resource_id"]) == key]
        f = [s for s in mine if s["phase"] == "FINDING"]
        v = [s for s in mine if s["phase"] == "VERIFICATION"]
        if f:
            out[key] = (FINDING_STATE[f[0]["operation"]], v[0]["operation"] if v else None)
        elif v and v[0]["evidence_id"]:
            out[key] = (VERIFY_STATE[v[0]["operation"]], v[0]["operation"])
        else:
            out[key] = ("COMPLIANT_OR_UNPROVEN", v[0]["operation"] if v else None)
    return out


def ours(r):
    t = r.treatment
    if t.kind == "violation":
        return FINDING_STATE[t.finding]
    if t.kind == "compliant":
        return VERIFY_STATE[t.verification]
    return t.kind.upper()  # UNPROVEN | NONE


def agree(gold_state, mine):
    if gold_state == "COMPLIANT_OR_UNPROVEN":
        return mine in set(VERIFY_STATE.values()) | {"UNPROVEN"}
    return gold_state == mine


def run(root, split_name="dev", risk=False, limit=5):
    sys.path.insert(0, str(root / "code"))
    from evaluation import split
    from ghostaudit import data, intent
    from ghostaudit.engine import Engine

    d = root / "dataset"
    eng = Engine.from_dataset(d)
    dev, hold, _ = split.load_frozen()
    ids = {"dev": dev, "holdout": hold, "all": dev + hold}[split_name]
    gold = {
        r["case_id"]: json.loads(r["steps_json"])
        for r in csv.DictReader(open(d / "sample_output.csv", newline="", encoding="utf-8"))
    }
    reqs = {q["case_id"]: q for q in data.load_requests(d / "sample_deletion_requests.csv")}
    n_gold = found = ok = op_ok = extra = 0
    misses, bad, extras = Counter(), [], []
    for c in ids:
        q = reqs[c]
        a = eng.assess(q, intent.classify_rules(q["request_text"]))
        mine = {(r.system_id, r.resource_id): r for r in a.resources}
        g = gold_implied(gold[c])
        for key, (gs, gop) in g.items():
            n_gold += 1
            r = mine.get(key)
            if r is None:
                misses[key[0]] += 1
                continue
            found += 1
            m = ours(r)
            good = agree(gs, m)
            ok += good
            op_ok += r.treatment.verification == gop
            if not good or r.treatment.verification != gop:
                st = r.state
                bad.append(
                    f"  {c} {key[0]}/{key[1]}: gold {gs} ({gop}); ours {m} ({r.treatment.verification}) "
                    f"category={r.category} [{r.category_source}] state={st.state if st else None} "
                    f"{(st.basis + ' ' + st.file_id + ' ' + st.locator) if st else ''} reason={r.treatment.reason}"
                )
        for key, r in mine.items():
            if key not in g and r.treatment.kind != "none":
                extra += 1
                extras.append(
                    f"  {c} {key[0]}/{key[1]}: ours {ours(r)} ({r.treatment.verification}) category={r.category} "
                    f"[{r.category_source}] via {r.links[0].file_id} {r.links[0].locator}"
                )
    print(f"STATES ({split_name}, {len(ids)} cases; gold-implied per-resource state vs ours)")
    print(
        f"  gold resources: {n_gold}; discovered by grounded identifiers: {found}; not discovered (need T10 linking or T12 images/PDFs): {n_gold - found} {dict(misses)}"
    )
    print(f"  state agreement on discovered: {ok}/{found} = {ok / found if found else 1:.3f}")
    print(
        f"  end-state operation (verification op) agreement on discovered: {op_ok}/{found} = {op_ok / found if found else 1:.3f}"
    )
    print(f"  extra resources we would emit steps for (not in gold): {extra}")
    print("\n".join(bad) or "  no disagreements")
    for x in extras[:20]:
        print(x)
    if risk:
        risk_report(eng, d, limit)
    return 0 if (not found or ok / found >= 0.95) else 1


def _line(d, file_path, locator):
    if not locator.startswith("line "):
        return "?"
    n = int(locator.split()[1])
    lines = (d / file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[n - 1].strip()[:220] if n <= len(lines) else "?"


def risk_report(eng, d, limit):
    """ADR 0014 risk on the evaluation requests: PRESENT only because an older sighting survives a later omission."""
    from ghostaudit import data, intent

    hits, cases = [], set()
    total = 0
    for q in data.load_requests(d / "deletion_requests.csv"):
        a = eng.assess(q, intent.classify_rules(q["request_text"]))
        for r in a.resources:
            if r.state and r.state.state != "ABSENT":
                total += 1
            if r.later_omissions:
                hits.append((q["case_id"], r))
                cases.add(q["case_id"])
    flips = [(c, r) for c, r in hits if r.treatment.kind == "violation"]
    print(
        f"ADR 0014 RISK (eval, {len(cases)} cases): {len(hits)} of {total} non-absent resources stand only because an older "
        f"sighting survives a later covering file that omits them; {len(flips)} of those are violations "
        f"(would flip to compliant under strong coverage) in {len({c for c, _ in flips})} cases"
    )
    for c, r in (flips + [h for h in hits if h not in flips])[:limit]:
        o = r.state.observation
        f = eng.store.files[o.file_id]
        print(
            f"  {c} {r.system_id}/{r.resource_id} {r.treatment.kind} ({r.category}): sighting {o.file_id} {o.locator} "
            f"(observed {o.observed_at}); omitted by later {', '.join(r.later_omissions)}"
        )
        print(f"     {f.file_path} {o.locator}: {_line(d, f.file_path, o.locator)}")
        for fid in r.later_omissions[:2]:
            lf = eng.store.files[fid]
            print(f"     omitted in {fid} {lf.file_path} (captured {lf.captured_at})")
