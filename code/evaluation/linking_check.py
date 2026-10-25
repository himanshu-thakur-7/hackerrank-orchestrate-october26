"""T10 acceptance: primary-account linking vs the labeled samples, eval tie counts, and every rejected or
unresolved link with its reason. Gold is used here only to EVALUATE; the solver never imports this."""

import csv
import json
import sys
from collections import Counter


def run(root):
    sys.path.insert(0, str(root / "code"))
    from ghostaudit import data, intent
    from ghostaudit.engine import Engine

    d = root / "dataset"
    eng = Engine.from_dataset(d)
    lk = eng.linker
    gold = {
        r["case_id"]: json.loads(r["steps_json"])
        for r in csv.DictReader(open(d / "sample_output.csv", newline="", encoding="utf-8"))
    }
    samples = data.load_requests(d / "sample_deletion_requests.csv")
    evals = data.load_requests(d / "deletion_requests.csv")
    res = Counter()
    print("SAMPLE ACCOUNTS (activity linking vs gold account_service resources)")
    for q in samples:
        g = sorted(
            {s["resource_id"] for s in gold[q["case_id"]] if s["system_id"] == "account_service"}
        )
        l = lk.account(q["case_id"])
        if l.status == "LINKED":
            v = (
                "EXACT"
                if [l.resource_id] == g
                else ("WRONG" if l.resource_id not in g else "PARTIAL")
            )
        else:
            v = l.status
        res[v] += 1
        if v != "EXACT":
            print(
                f"  {q['case_id']}: {v:12} gold={g} ours={l.resource_id} survivors={[c.resource_id for c in l.survivors]} {l.reason}"
            )
    print(
        f"  samples: {res['EXACT']}/32 exact, {res['WRONG']} wrong, {res['TIED']} tied, {res['NO_CANDIDATE']} no candidate"
    )
    ids = [q["case_id"] for q in evals]
    print("EVAL " + lk.summary(ids))
    tied = [c for c in ids if lk.account(c).status == "TIED"]
    print(f"  tied eval cases: {len(tied)}")
    print("CATALOG LINKS (all, checked against their artifact)")
    view = eng.store.as_of("9999-12-31T23:59:59Z")
    for c in lk.catalog(view, None):
        print(
            f"  {c.activity_id} {c.system_id}/{c.resource_id}: {c.status} {c.artifact} {c.reason}"
        )
    print("PER-CASE LINK LOG (eval: rejected and unresolved links; feeds the evaluation report)")
    kinds = Counter()
    rejected_steps = []
    for q in evals:
        a = eng.assess(q, intent.classify_rules(q["request_text"]))
        rejected = set()
        for line in a.log:
            if line.startswith(("REJECTED_LINK", "UNRESOLVED_LINK")):
                kinds[
                    line.split("(")[0]
                    + (
                        ":tied"
                        if "survive" in line
                        else ":claimed"
                        if "claimed" in line
                        else ":window"
                        if "no account delete" in line
                        else ":catalog"
                        if "catalog" in line
                        else ""
                    )
                ] += 1
                if line.startswith("REJECTED_LINK") or "catalog" in line:
                    print(f"  {q['case_id']}: {line}")
                if line.startswith("REJECTED_LINK"):
                    rejected.add(line.split("(", 1)[1].split()[1].rstrip(":"))
        rejected_steps += [
            (q["case_id"], s["resource_id"]) for s in a.steps if s["resource_id"] in rejected
        ]
    print(f"  totals: {dict(sorted(kinds.items()))}")
    print(
        f"  steps on resources whose catalog link was rejected (ADR 0005): {rejected_steps or 'none'}"
    )
    return 0 if res["WRONG"] == 0 and not rejected_steps else 1
