"""State acceptance: per-resource state + treatment vs the state that the gold steps imply.

Gold is used here only to EVALUATE; nothing in this module is imported by the solver.

gold-implied state of a resource (from its steps in sample_output.csv):
  finding REPORT_REMAINING_RECORD -> PRESENT, REPORT_EXPOSED_PII -> EXPOSED,
  REPORT_ACTIVE_DATA_FLOW -> ACTIVE, REPORT_RESTORE_RISK -> RESTORABLE;
  otherwise its verification op: cited (COMPLETE) -> that compliant state;
  uncited (INCOMPLETE, no finding) -> "compliant or unproven".

Decisions: ADR 0006 and 0014 (evaluation only; gold labels are read here, never by the solver).
"""

import json
import sys
from collections import Counter

from ghostaudit.data import read_csv

# `states` passes when at least this share of the found resources agree with gold
STATE_AGREEMENT_FLOOR = 0.95
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
    """{(system_id, resource_id): (gold-implied state, verification op)} of one gold row."""
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
    """The state our treatment implies for one resource (PRESENT, EXPOSED, ..., UNPROVEN, NONE)."""
    t = r.treatment
    if t.kind == "violation":
        return FINDING_STATE[t.finding]
    if t.kind == "compliant":
        return VERIFY_STATE[t.verification]
    return t.kind.upper()  # UNPROVEN | NONE


def agree(gold_state, mine):
    """Whether our state agrees with gold; an uncited gold check accepts compliant or unproven."""
    if gold_state == "COMPLIANT_OR_UNPROVEN":
        return mine in set(VERIFY_STATE.values()) | {"UNPROVEN"}
    return gold_state == mine


def _disagreement(c, key, gs, gop, m, r):
    st = r.state
    where = (st.basis + " " + st.file_id + " " + st.locator) if st else ""
    return (
        f"  {c} {key[0]}/{key[1]}: gold {gs} ({gop}); ours {m} "
        f"({r.treatment.verification}) "
        f"category={r.category} [{r.category_source}] state={st.state if st else None} "
        f"{where} "
        f"reason={r.treatment.reason}"
    )


def _extra(c, key, r):
    return (
        f"  {c} {key[0]}/{key[1]}: ours {ours(r)} ({r.treatment.verification}) "
        f"category={r.category} "
        f"[{r.category_source}] via {r.links[0].file_id} {r.links[0].locator}"
    )


def _compare_case(c, mine, g, t):
    """Count one case's gold-implied resources against ours into `t`."""
    for key, (gs, gop) in g.items():
        t["n_gold"] += 1
        r = mine.get(key)
        if r is None:
            t["misses"][key[0]] += 1
            continue
        t["found"] += 1
        m = ours(r)
        good = agree(gs, m)
        t["ok"] += good
        t["op_ok"] += r.treatment.verification == gop
        if not good or r.treatment.verification != gop:
            t["bad"].append(_disagreement(c, key, gs, gop, m, r))
    for key, r in mine.items():
        if key not in g and r.treatment.kind != "none":
            t["extra"] += 1
            t["extras"].append(_extra(c, key, r))


def _print_states(split_name, ids, t):
    found = t["found"]
    print(f"STATES ({split_name}, {len(ids)} cases; gold-implied per-resource state vs ours)")
    print(
        f"  gold resources: {t['n_gold']}; discovered by grounded identifiers: {found}; not "
        f"discovered "
        f"(need T10 linking or T12 images/PDFs): {t['n_gold'] - found} {dict(t['misses'])}"
    )
    print(
        f"  state agreement on discovered: {t['ok']}/{found} = "
        f"{t['ok'] / found if found else 1:.3f}"
    )
    print(
        f"  end-state operation (verification op) agreement on discovered: {t['op_ok']}/{found} = "
        f"{t['op_ok'] / found if found else 1:.3f}"
    )
    print(f"  extra resources we would emit steps for (not in gold): {t['extra']}")
    print("\n".join(t["bad"]) or "  no disagreements")
    for x in t["extras"][:20]:
        print(x)


def run(root, split_name="dev", risk=False, limit=5):
    """`main.py states`: compare per-resource states on a split; exit 0 when at least
    STATE_AGREEMENT_FLOOR of the found resources agree."""
    sys.path.insert(0, str(root / "code"))
    from ghostaudit import data, intent
    from ghostaudit.engine import Engine

    from evaluation import split

    d = root / "dataset"
    eng = Engine.from_dataset(d)
    dev, hold, _ = split.load_frozen()
    ids = {"dev": dev, "holdout": hold, "all": dev + hold}[split_name]
    gold = {r["case_id"]: json.loads(r["steps_json"]) for r in read_csv(d / "sample_output.csv")}
    reqs = {q["case_id"]: q for q in data.load_requests(d / "sample_deletion_requests.csv")}
    t = {"n_gold": 0, "found": 0, "ok": 0, "op_ok": 0, "extra": 0}
    t.update(misses=Counter(), bad=[], extras=[])
    for c in ids:
        q = reqs[c]
        a = eng.assess(q, intent.classify_rules(q["request_text"]))
        mine = {(r.system_id, r.resource_id): r for r in a.resources}
        _compare_case(c, mine, gold_implied(gold[c]), t)
    _print_states(split_name, ids, t)
    if risk:
        risk_report(eng, d, limit)
    found = t["found"]
    return 0 if (not found or t["ok"] / found >= STATE_AGREEMENT_FLOOR) else 1


def _line(d, file_path, locator):
    if not locator.startswith("line "):
        return "?"
    n = int(locator.split()[1])
    lines = (d / file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[n - 1].strip()[:220] if n <= len(lines) else "?"


def risk_report(eng, d, limit):
    """ADR 0014 risk on the evaluation requests: PRESENT only because an older sighting survives
    a later omission."""
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
        f"ADR 0014 RISK (eval, {len(cases)} cases): {len(hits)} of {total} non-absent resources "
        f"stand only because an older "
        f"sighting survives a later covering file that omits them; {len(flips)} of those are "
        f"violations "
        f"(would flip to compliant under strong coverage) in {len({c for c, _ in flips})} cases"
    )
    for c, r in (flips + [h for h in hits if h not in flips])[:limit]:
        o = r.state.observation
        f = eng.store.files[o.file_id]
        print(
            f"  {c} {r.system_id}/{r.resource_id} {r.treatment.kind} ({r.category}): sighting "
            f"{o.file_id} {o.locator} "
            f"(observed {o.observed_at}); omitted by later {', '.join(r.later_omissions)}"
        )
        print(f"     {f.file_path} {o.locator}: {_line(d, f.file_path, o.locator)}")
        for fid in r.later_omissions[:2]:
            lf = eng.store.files[fid]
            print(f"     omitted in {fid} {lf.file_path} (captured {lf.captured_at})")
