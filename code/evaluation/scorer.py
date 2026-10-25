"""L1 scorer: compares predicted rows with labeled rows.

score(pred, gold, case_ids) -> dict of metrics, where pred/gold map case_id -> (status, [step dicts]).
A case missing from pred counts as status None with no steps.

Metric definitions (all micro-averaged over the given cases unless stated):
  status_accuracy     share of cases whose deletion_status matches
  identity_recall     share of gold (case, system_id, resource_id) pairs that appear in any predicted step
  finding_*           precision / recall / F1 over FINDING steps keyed by (case, system, resource, operation)
  policy_accuracy     per gold resource, the treatment = remediation ops if any, else verification ops; share matched
  evidence_accuracy   share of gold steps that cite evidence whose aligned predicted step cites the same id
                      (aligned = same case, phase, system, resource, operation; unaligned counts as wrong)
  strict_step_f1      F1 over full 7-field steps (step_no included)
  step_f1_unordered   F1 over steps without step_no
  field_acc_*         on steps aligned by (case, phase, system, resource): operation, state, evidence_id, step_no;
                      0.0 when steps exist but none align (no free credit), 1.0 only when both sides are empty
  sequence_exact      share of cases whose (phase, system, resource, operation, state) sequence is identical
  sequence_lcs_mean   mean per case of LCS / max(len gold, len pred); 1.0 when both are empty
  row_exact           share of cases with identical status and identical step list (pessimistic bound)
  proxy               equal-weight mean of the nine headline metrics listed in PROXY
"""
import csv
import json
from collections import defaultdict

FIELDS = ("operation", "state", "evidence_id", "step_no")
PROXY = ("status_accuracy", "identity_recall", "finding_f1", "policy_accuracy", "evidence_accuracy",
         "strict_step_f1", "field_acc_mean", "sequence_exact", "sequence_lcs_mean")


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(f)}


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


def score(pred, gold, case_ids):
    case_ids = list(case_ids)
    n = len(case_ids)
    status_ok = row_ok = seq_ok = 0
    lcs_sum = 0.0
    id_hit = id_tot = 0
    f_tp = f_pred = f_gold = 0
    pol_ok = pol_tot = 0
    ev_ok = ev_tot = 0
    s_tp = s_pred = s_gold = 0
    u_tp = u_pred = u_gold = 0
    field_ok = defaultdict(int)
    aligned = 0
    any_steps = False

    for c in case_ids:
        gs, gsteps = gold[c]
        ps, psteps = pred.get(c, (None, []))
        any_steps |= bool(gsteps or psteps)
        status_ok += ps == gs
        row_ok += ps == gs and psteps == gsteps

        seq = lambda steps: [(s["phase"], s["system_id"], s["resource_id"], s["operation"], s["state"]) for s in steps]
        gq, pq = seq(gsteps), seq(psteps)
        seq_ok += gq == pq
        lcs_sum += 1.0 if not gq and not pq else _lcs(gq, pq) / max(len(gq), len(pq))

        gres = {(s["system_id"], s["resource_id"]) for s in gsteps}
        pres = {(s["system_id"], s["resource_id"]) for s in psteps}
        id_tot += len(gres)
        id_hit += len(gres & pres)

        fkey = lambda steps: {(s["system_id"], s["resource_id"], s["operation"]) for s in steps if s["phase"] == "FINDING"}
        gf, pf = fkey(gsteps), fkey(psteps)
        f_tp += len(gf & pf); f_pred += len(pf); f_gold += len(gf)

        for r in sorted(gres):
            pol_tot += 1
            g_t = _treatment([s for s in gsteps if (s["system_id"], s["resource_id"]) == r])
            p_t = _treatment([s for s in psteps if (s["system_id"], s["resource_id"]) == r])
            pol_ok += g_t == p_t

        pev = {(s["phase"], s["system_id"], s["resource_id"], s["operation"]): s["evidence_id"] for s in psteps}
        for s in gsteps:
            if s["evidence_id"]:
                ev_tot += 1
                ev_ok += pev.get((s["phase"], s["system_id"], s["resource_id"], s["operation"])) == s["evidence_id"]

        full = lambda steps: [tuple(sorted(s.items())) for s in steps]
        noord = lambda steps: [tuple(sorted((k, v) for k, v in s.items() if k != "step_no")) for s in steps]
        for get, acc in ((full, "s"), (noord, "u")):
            gl, pl = get(gsteps), get(psteps)
            pool = list(pl)
            tp = 0
            for t in gl:
                if t in pool:
                    pool.remove(t); tp += 1
            if acc == "s":
                s_tp += tp; s_pred += len(pl); s_gold += len(gl)
            else:
                u_tp += tp; u_pred += len(pl); u_gold += len(gl)

        buckets = defaultdict(list)
        for s in psteps:
            buckets[(s["phase"], s["system_id"], s["resource_id"])].append(s)
        for s in gsteps:
            b = buckets.get((s["phase"], s["system_id"], s["resource_id"]))
            if b:
                p = b.pop(0)
                aligned += 1
                for fld in FIELDS:
                    field_ok[fld] += p[fld] == s[fld]

    m = {"cases": n}
    m["status_accuracy"] = status_ok / n if n else 1.0
    m["identity_recall"] = id_hit / id_tot if id_tot else 1.0
    m["finding_precision"], m["finding_recall"], m["finding_f1"] = _prf(f_tp, f_pred, f_gold)
    m["policy_accuracy"] = pol_ok / pol_tot if pol_tot else 1.0
    m["evidence_accuracy"] = ev_ok / ev_tot if ev_tot else 1.0
    m["strict_step_f1"] = _prf(s_tp, s_pred, s_gold)[2]
    m["step_f1_unordered"] = _prf(u_tp, u_pred, u_gold)[2]
    for fld in FIELDS:
        # nothing aligned: perfect only if neither side has any step, otherwise 0 (no free credit)
        m[f"field_acc_{fld}"] = field_ok[fld] / aligned if aligned else (0.0 if any_steps else 1.0)
    m["field_acc_mean"] = sum(m[f"field_acc_{f}"] for f in FIELDS) / len(FIELDS)
    m["sequence_exact"] = seq_ok / n if n else 1.0
    m["sequence_lcs_mean"] = lcs_sum / n if n else 1.0
    m["row_exact"] = row_ok / n if n else 1.0
    m["proxy"] = sum(m[k] for k in PROXY) / len(PROXY)
    return m


def case_diff(pred, gold, case_id):
    """Human-readable differences for one case (used for dev failure detail)."""
    gs, gsteps = gold[case_id]
    ps, psteps = pred.get(case_id, (None, []))
    key = lambda s: (s["phase"], s["system_id"], s["resource_id"], s["operation"], s["state"], s["evidence_id"])
    g, p = [key(s) for s in gsteps], [key(s) for s in psteps]
    lines = [f"{case_id}: status pred={ps} gold={gs}"] if ps != gs else []
    lines += [f"{case_id}: missing  {' '.join(k)}" for k in g if k not in p]
    lines += [f"{case_id}: extra    {' '.join(k)}" for k in p if k not in g]
    if not lines and psteps != gsteps:
        lines.append(f"{case_id}: same steps, different order or step_no")
    return lines
