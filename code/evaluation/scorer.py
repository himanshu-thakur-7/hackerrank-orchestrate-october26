"""L1 scorer: compares predicted rows with labeled rows.

score(pred, gold, case_ids) -> dict of metrics, where pred/gold map case_id -> (status, [step
dicts]). A case missing from pred counts as status None with no steps.

Metric definitions (all micro-averaged over the given cases unless stated):
  status_accuracy     share of cases whose deletion_status matches
  identity_recall     share of gold (case, system_id, resource_id) pairs that appear in any
  predicted step finding_*           precision / recall / F1 over FINDING steps keyed by (case,
  system, resource, operation) policy_accuracy     per gold resource, the treatment = remediation
  ops if any, else verification ops; share matched evidence_accuracy   share of gold steps that cite
  evidence whose aligned predicted step cites the same id
                      (aligned = same case, phase, system, resource, operation; unaligned counts as
                      wrong)
  strict_step_f1      F1 over full 7-field steps (step_no included)
  step_f1_unordered   F1 over steps without step_no
  field_acc_*         on steps aligned by (case, phase, system, resource): operation, state,
  evidence_id, step_no;
                      0.0 when steps exist but none align (no free credit), 1.0 only when both sides
                      are empty
  sequence_exact      share of cases whose (phase, system, resource, operation, state) sequence is
  identical sequence_lcs_mean   mean per case of LCS / max(len gold, len pred); 1.0 when both are
  empty row_exact           share of cases with identical status and identical step list
  (pessimistic bound) proxy               equal-weight mean of the nine headline metrics listed in
  PROXY

Decisions: ADR: none (evaluation only; gold labels are read here, never by the solver).
"""

import csv
import json
from collections import Counter, defaultdict

FIELDS = ("operation", "state", "evidence_id", "step_no")
PROXY = (
    "status_accuracy",
    "identity_recall",
    "finding_f1",
    "policy_accuracy",
    "evidence_accuracy",
    "strict_step_f1",
    "field_acc_mean",
    "sequence_exact",
    "sequence_lcs_mean",
)


def _sequence(steps):
    """Steps as ordered (phase, system, resource, operation, state) tuples, for sequence metrics."""
    return [
        (s["phase"], s["system_id"], s["resource_id"], s["operation"], s["state"]) for s in steps
    ]


def _findings(steps):
    """The (system, resource, operation) keys of the FINDING steps."""
    return {
        (s["system_id"], s["resource_id"], s["operation"]) for s in steps if s["phase"] == "FINDING"
    }


def _full_steps(steps):
    """Each step as a sorted item tuple, step_no included (strict step matching)."""
    return [tuple(sorted(s.items())) for s in steps]


def _unordered_steps(steps):
    """Each step as a sorted item tuple without step_no (order-free step matching)."""
    return [tuple(sorted((k, v) for k, v in s.items() if k != "step_no")) for s in steps]


def load(path):
    """{case_id: (status, steps)} of an output or label file."""
    with open(path, newline="", encoding="utf-8") as f:
        return {
            r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"]))
            for r in csv.DictReader(f)
        }


def _prf(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else 1.0
    r = tp / n_gold if n_gold else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def _lcs(a, b):
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[-1]))
        prev = cur
    return prev[-1]


def _treatment(steps):
    rem = frozenset(s["operation"] for s in steps if s["phase"] == "REMEDIATION")
    return rem or frozenset(s["operation"] for s in steps if s["phase"] == "VERIFICATION")


def _resources(steps):
    return {(s["system_id"], s["resource_id"]) for s in steps}


def _count_sequence(t, gsteps, psteps):
    gq, pq = _sequence(gsteps), _sequence(psteps)
    t["seq_ok"] += gq == pq
    t["lcs_sum"] += 1.0 if not gq and not pq else _lcs(gq, pq) / max(len(gq), len(pq))


def _count_identity_and_findings(t, gsteps, psteps):
    gres, pres = _resources(gsteps), _resources(psteps)
    t["id_tot"] += len(gres)
    t["id_hit"] += len(gres & pres)
    gf, pf = _findings(gsteps), _findings(psteps)
    t["f_tp"] += len(gf & pf)
    t["f_pred"] += len(pf)
    t["f_gold"] += len(gf)


def _count_policy(t, gsteps, psteps):
    """Per gold resource: does the predicted treatment (remediation, else verification) match?"""
    for r in sorted(_resources(gsteps)):
        t["pol_tot"] += 1
        g_t = _treatment([s for s in gsteps if (s["system_id"], s["resource_id"]) == r])
        p_t = _treatment([s for s in psteps if (s["system_id"], s["resource_id"]) == r])
        t["pol_ok"] += g_t == p_t


def _count_evidence(t, gsteps, psteps):
    """Per cited gold step: does the predicted step at the same place cite the same evidence?"""
    pev = {
        (s["phase"], s["system_id"], s["resource_id"], s["operation"]): s["evidence_id"]
        for s in psteps
    }
    for s in gsteps:
        if s["evidence_id"]:
            t["ev_tot"] += 1
            key = (s["phase"], s["system_id"], s["resource_id"], s["operation"])
            t["ev_ok"] += pev.get(key) == s["evidence_id"]


def _matched(gold_items, pred_items):
    """Multiset intersection size of two lists."""
    pool, tp = list(pred_items), 0
    for x in gold_items:
        if x in pool:
            pool.remove(x)
            tp += 1
    return tp


def _count_steps(t, gsteps, psteps):
    for get, acc in ((_full_steps, "s"), (_unordered_steps, "u")):
        gl, pl = get(gsteps), get(psteps)
        t[f"{acc}_tp"] += _matched(gl, pl)
        t[f"{acc}_pred"] += len(pl)
        t[f"{acc}_gold"] += len(gl)


def _count_fields(t, field_ok, gsteps, psteps):
    """Align gold and predicted steps by (phase, system, resource), in order, and compare fields."""
    buckets = defaultdict(list)
    for s in psteps:
        buckets[(s["phase"], s["system_id"], s["resource_id"])].append(s)
    for s in gsteps:
        b = buckets.get((s["phase"], s["system_id"], s["resource_id"]))
        if b:
            p = b.pop(0)
            t["aligned"] += 1
            for fld in FIELDS:
                field_ok[fld] += p[fld] == s[fld]


def _ratio(num, den):
    return num / den if den else 1.0


def _metrics(t, field_ok, n, any_steps):
    m = {"cases": n}
    m["status_accuracy"] = _ratio(t["status_ok"], n)
    m["identity_recall"] = _ratio(t["id_hit"], t["id_tot"])
    m["finding_precision"], m["finding_recall"], m["finding_f1"] = _prf(
        t["f_tp"], t["f_pred"], t["f_gold"]
    )
    m["policy_accuracy"] = _ratio(t["pol_ok"], t["pol_tot"])
    m["evidence_accuracy"] = _ratio(t["ev_ok"], t["ev_tot"])
    m["strict_step_f1"] = _prf(t["s_tp"], t["s_pred"], t["s_gold"])[2]
    m["step_f1_unordered"] = _prf(t["u_tp"], t["u_pred"], t["u_gold"])[2]
    aligned = t["aligned"]
    for fld in FIELDS:
        # nothing aligned: perfect only if neither side has any step, otherwise 0 (no free credit)
        m[f"field_acc_{fld}"] = field_ok[fld] / aligned if aligned else (0.0 if any_steps else 1.0)
    m["field_acc_mean"] = sum(m[f"field_acc_{f}"] for f in FIELDS) / len(FIELDS)
    m["sequence_exact"] = _ratio(t["seq_ok"], n)
    m["sequence_lcs_mean"] = _ratio(t["lcs_sum"], n)
    m["row_exact"] = _ratio(t["row_ok"], n)
    m["proxy"] = sum(m[k] for k in PROXY) / len(PROXY)
    return m


def score(pred, gold, case_ids):
    """Every metric over the given cases (gold and pred: {case_id: (status, steps)})."""
    case_ids = list(case_ids)
    t, field_ok, any_steps = Counter(), defaultdict(int), False
    t["lcs_sum"] = 0.0
    for c in case_ids:
        gs, gsteps = gold[c]
        ps, psteps = pred.get(c, (None, []))
        any_steps |= bool(gsteps or psteps)
        t["status_ok"] += ps == gs
        t["row_ok"] += ps == gs and psteps == gsteps
        _count_sequence(t, gsteps, psteps)
        _count_identity_and_findings(t, gsteps, psteps)
        _count_policy(t, gsteps, psteps)
        _count_evidence(t, gsteps, psteps)
        _count_steps(t, gsteps, psteps)
        _count_fields(t, field_ok, gsteps, psteps)
    return _metrics(t, field_ok, len(case_ids), any_steps)


def case_diff(pred, gold, case_id):
    """Human-readable differences for one case (used for dev failure detail)."""
    gs, gsteps = gold[case_id]
    ps, psteps = pred.get(case_id, (None, []))

    def key(s):
        return (
            s["phase"],
            s["system_id"],
            s["resource_id"],
            s["operation"],
            s["state"],
            s["evidence_id"],
        )

    g, p = [key(s) for s in gsteps], [key(s) for s in psteps]
    lines = [f"{case_id}: status pred={ps} gold={gs}"] if ps != gs else []
    lines += [f"{case_id}: missing  {' '.join(k)}" for k in g if k not in p]
    lines += [f"{case_id}: extra    {' '.join(k)}" for k in p if k not in g]
    if not lines and psteps != gsteps:
        lines.append(f"{case_id}: same steps, different order or step_no")
    return lines
