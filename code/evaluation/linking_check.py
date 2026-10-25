"""T10 acceptance: primary-account linking vs the labeled samples, eval tie counts, and every
rejected or unresolved link with its reason. Gold is used here only to EVALUATE; the solver never
imports this."""

import json
import sys
from collections import Counter

from ghostaudit.data import read_csv


# (substring of an UNRESOLVED/REJECTED log line, suffix for its kind), checked in this order
LINK_KINDS = (
    ("survive", ":tied"),
    ("claimed", ":claimed"),
    ("no account delete", ":window"),
    ("catalog", ":catalog"),
)


def _link_kind(line):
    suffix = next((k for marker, k in LINK_KINDS if marker in line), "")
    return line.split("(")[0] + suffix


def _account_verdict(acct, g):
    if acct.status != "LINKED":
        return acct.status
    if [acct.resource_id] == g:
        return "EXACT"
    return "WRONG" if acct.resource_id not in g else "PARTIAL"


def _sample_accounts(lk, samples, gold):
    res = Counter()
    print("SAMPLE ACCOUNTS (activity linking vs gold account_service resources)")
    for q in samples:
        steps = gold[q["case_id"]]
        g = sorted({s["resource_id"] for s in steps if s["system_id"] == "account_service"})
        acct = lk.account(q["case_id"])
        v = _account_verdict(acct, g)
        res[v] += 1
        if v != "EXACT":
            print(
                f"  {q['case_id']}: {v:12} gold={g} ours={acct.resource_id} "
                f"survivors={[c.resource_id for c in acct.survivors]} {acct.reason}"
            )
    print(
        f"  samples: {res['EXACT']}/32 exact, {res['WRONG']} wrong, {res['TIED']} tied, "
        f"{res['NO_CANDIDATE']} no candidate"
    )
    return res


def _print_catalog(eng, lk):
    print("CATALOG LINKS (all, checked against their artifact)")
    view = eng.store.as_of("9999-12-31T23:59:59Z")
    for c in lk.catalog(view, None):
        print(
            f"  {c.activity_id} {c.system_id}/{c.resource_id}: {c.status} {c.artifact} {c.reason}"
        )


def _case_link_log(q, a, kinds):
    """Count and print one case's rejected / unresolved links; return the rejected resources."""
    rejected = set()
    for line in a.log:
        if not line.startswith(("REJECTED_LINK", "UNRESOLVED_LINK")):
            continue
        kinds[_link_kind(line)] += 1
        if line.startswith("REJECTED_LINK") or "catalog" in line:
            print(f"  {q['case_id']}: {line}")
        if line.startswith("REJECTED_LINK"):
            rejected.add(line.split("(", 1)[1].split()[1].rstrip(":"))
    return rejected


def _link_log(eng, evals, intent):
    print("PER-CASE LINK LOG (eval: rejected and unresolved links; feeds the evaluation report)")
    kinds, rejected_steps = Counter(), []
    for q in evals:
        a = eng.assess(q, intent.classify_rules(q["request_text"]))
        rejected = _case_link_log(q, a, kinds)
        rejected_steps += [
            (q["case_id"], s["resource_id"]) for s in a.steps if s["resource_id"] in rejected
        ]
    print(f"  totals: {dict(sorted(kinds.items()))}")
    print(
        f"  steps on resources whose catalog link was rejected (ADR 0005): "
        f"{rejected_steps or 'none'}"
    )
    return rejected_steps


def run(root):
    sys.path.insert(0, str(root / "code"))
    from ghostaudit import data, intent
    from ghostaudit.engine import Engine

    d = root / "dataset"
    eng = Engine.from_dataset(d)
    lk = eng.linker
    gold = {r["case_id"]: json.loads(r["steps_json"]) for r in read_csv(d / "sample_output.csv")}
    samples = data.load_requests(d / "sample_deletion_requests.csv")
    evals = data.load_requests(d / "deletion_requests.csv")
    res = _sample_accounts(lk, samples, gold)
    ids = [q["case_id"] for q in evals]
    print("EVAL " + lk.summary(ids))
    print(f"  tied eval cases: {len([c for c in ids if lk.account(c).status == 'TIED'])}")
    _print_catalog(eng, lk)
    rejected_steps = _link_log(eng, evals, intent)
    return 0 if res["WRONG"] == 0 and not rejected_steps else 1
