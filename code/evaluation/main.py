"""Evaluation CLI for the Ghost Data deletion audit.

  python3 code/evaluation/main.py contract [--file output.csv] [--requests dataset/deletion_requests.csv]
  python3 code/evaluation/main.py score [--pred PRED.csv] [--split dev|all] [--reveal-holdout] [--accept-regression REASON]
      (no --pred: runs code/main.py on the 32 samples first)
  python3 code/evaluation/main.py determinism [--cmd "python3 code/main.py"] [--file output.csv]
  python3 code/evaluation/main.py loaders [--files ID,ID] [--kind sql,json,log,...] [--spot]
  python3 code/evaluation/main.py states [--split dev|holdout|all] [--risk]
  python3 code/evaluation/main.py audit
  python3 code/evaluation/main.py selftest

Exit codes: 0 ok, 1 contract/audit/determinism failure, 2 diff gate (dev regression).
Unit tests: python3 -m unittest discover -s code/evaluation/tests -t code
"""
import argparse
import csv
import io
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

from evaluation import audit, gate, history, scorer, split  # noqa: E402

DATA = ROOT / "dataset"
MANIFEST = DATA / "evidence_files.csv"
GOLD = DATA / "sample_output.csv"
SAMPLE_REQ = DATA / "sample_deletion_requests.csv"
RUNS = Path(os.environ.get("GHOSTAUDIT_RUNS_DIR", ROOT / "runs"))
REVEAL_LOG = Path(os.environ.get("GHOSTAUDIT_REVEAL_LOG", HERE / "holdout_reveals.md"))
GATE_TOLERANCE = 0.005   # a dev headline metric may not drop by more than this between runs


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def _table(title, m):
    keys = ["status_accuracy", "identity_recall", "finding_precision", "finding_recall", "finding_f1", "policy_accuracy",
            "evidence_accuracy", "strict_step_f1", "step_f1_unordered", "field_acc_operation", "field_acc_state",
            "field_acc_evidence_id", "field_acc_step_no", "field_acc_mean", "sequence_exact", "sequence_lcs_mean",
            "row_exact", "proxy"]
    print(f"{title} ({m['cases']} cases)")
    for k in keys:
        print(f"  {k:24} {m[k]:.3f}")


def _print_warnings(w):
    for x in w:
        print("WARNING " + x)


def cmd_contract(a):
    w = []
    v = gate.check(a.file, a.requests, MANIFEST, warnings=w)
    _print_warnings(w)
    n = sum(1 for _ in csv.reader(io.StringIO(Path(a.file).read_text(encoding="utf-8", errors="replace")))) - 1
    if v:
        print(f"CONTRACT FAILED ({Path(a.file).name}): {len(v)} violation(s)")
        for x in v[:50]:
            print("  " + x)
        return 1
    print(f"CONTRACT OK ({Path(a.file).name}, {n} rows)")
    return 0


def cmd_score(a):
    if not a.pred:                    # run the solver on the 32 labeled samples into the run directory
        out = Path(tempfile.mkdtemp(prefix="ghostaudit_score_")) / "sample_pred.csv"
        subprocess.run([sys.executable, str(ROOT / "code" / "main.py"), "--requests", str(SAMPLE_REQ), "--out", str(out)],
                       check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
        a.pred = str(out)
    w = []
    v = gate.check(a.pred, SAMPLE_REQ, MANIFEST, warnings=w)
    _print_warnings(w)
    if v:
        print(f"CONTRACT FAILED ({Path(a.pred).name}) — not scored")
        for x in v[:50]:
            print("  " + x)
        return 1
    gold = scorer.load(GOLD)
    pred = scorer.load(a.pred)
    dev, hold, _ = split.load_frozen()
    m = {"dev": scorer.score(pred, gold, dev), "holdout": scorer.score(pred, gold, hold),
         "all": scorer.score(pred, gold, dev + hold)}
    _table("DEV", m["dev"])
    print("DEV failures:")
    detail = [l for c in dev for l in scorer.case_diff(pred, gold, c)]
    print("\n".join("  " + l for l in detail) or "  none")
    if a.split == "dev":
        print(f"HOLDOUT (aggregate only): proxy {m['holdout']['proxy']:.3f}, status_accuracy {m['holdout']['status_accuracy']:.3f}")
    else:
        _table("HOLDOUT (aggregate only)", m["holdout"])
    if a.reveal_holdout:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(REVEAL_LOG, "a", encoding="utf-8") as f:
            f.write(f"- {stamp} commit {_commit()} --reveal-holdout on {Path(a.pred).name}\n")
        print(f"HOLDOUT failures (revealed; logged to {REVEAL_LOG.name}):")
        print("\n".join("  " + l for c in hold for l in scorer.case_diff(pred, gold, c)) or "  none")
    _table("ALL", m["all"])

    runs = RUNS / "score"            # selftest runs live in RUNS/selftest and never feed this gate
    run_dir = history.record(runs, a.pred, m, _commit())
    prev = history.previous(runs, run_dir)
    print(f"RUN recorded: {run_dir}")
    if prev is None:
        print("DIFF vs previous run: (first run)")
        return 0
    lines = history.diff(prev / "output.csv", run_dir / "output.csv")
    dev_set = set(dev)
    shown = [l for l in lines if l.split(":", 1)[0] in dev_set or a.reveal_holdout]
    hidden = len(lines) - len(shown)
    print(f"DIFF vs {prev.name}: {len(lines)} change(s)" + (f" ({hidden} on holdout cases hidden)" if hidden else ""))
    print("\n".join("  " + l for l in shown) or "  none")
    import json
    old = json.loads((prev / "metrics.json").read_text()).get("dev", {})
    drops = [f"{k} {old[k]:.3f} -> {m['dev'][k]:.3f}" for k in scorer.PROXY
             if k in old and m["dev"][k] < old[k] - GATE_TOLERANCE]
    if drops and not a.accept_regression:
        print("DIFF GATE: dev regression vs previous run: " + "; ".join(drops))
        print("  rerun with --accept-regression \"<reason>\" to accept it deliberately")
        return 2
    if drops:
        print(f"DIFF GATE: regression accepted: {a.accept_regression}")
    return 0


def cmd_determinism(a):
    ok, _, msg = gate.determinism(shlex.split(a.cmd), Path(a.file))
    print(msg)
    return 0 if ok else 1


def cmd_loaders(a):
    from evaluation import loader_check
    files = [x for x in a.files.split(",") if x] if a.files else None
    kinds = [x for x in a.kind.split(",") if x] if a.kind else None
    return loader_check.run(ROOT, files, kinds, a.spot)


def cmd_states(a):
    from evaluation import states
    return states.run(ROOT, a.split, a.risk)


def cmd_audit(_):
    hits = audit.scan(ROOT / "code")
    print(f"LITERAL AUDIT: {len(hits)} hit(s)")
    for h in hits:
        print("  " + h)
    return 1 if hits else 0


def _broken_copies(tmp):
    rows = list(csv.reader(io.StringIO(GOLD.read_text(encoding="utf-8"))))
    raw = GOLD.read_text(encoding="utf-8").split("\n")
    bad_quote = tmp / "broken_quoting.csv"
    raw_q = list(raw); raw_q[3] = raw_q[3].replace('""', '"')
    bad_quote.write_text("\n".join(raw_q), encoding="utf-8")

    import json
    null_ev = tmp / "broken_null_evidence.csv"
    rn = [list(r) for r in rows]
    steps = json.loads(rn[5][2]); steps[1]["evidence_id"] = None; rn[5][2] = json.dumps(steps, separators=(",", ":"))
    with open(null_ev, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(rn)

    wrong_order = tmp / "broken_wrong_order.csv"
    ro = [list(r) for r in rows]; ro[3], ro[4] = ro[4], ro[3]
    with open(wrong_order, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(ro)
    # each broken copy names the ONE check id it targets, so it cannot "fail as expected" for another reason
    return [("bad quoting", bad_quote, "L0.csv"), ("null evidence", null_ev, "L0.evidence"), ("wrong order", wrong_order, "L0.order")]


def cmd_selftest(_):
    ok = True
    w = []
    v = gate.check(GOLD, SAMPLE_REQ, MANIFEST, warnings=w)
    _print_warnings(w)
    print(f"[1] contract gate on gold: {'CONTRACT OK (sample_output.csv, 32 rows)' if not v else 'FAILED'}")
    for x in v:
        print("    " + x)
    ok &= not v

    gold = scorer.load(GOLD)
    dev, hold, seed = split.load_frozen()
    print(f"[2] frozen split: {len(dev)} dev / {len(hold)} holdout (seed {seed})")
    worst = 1.0
    for name, ids in (("dev", dev), ("holdout", hold), ("all", dev + hold)):
        m = scorer.score(gold, gold, ids)
        vals = [x for x in m.values() if isinstance(x, float)]
        worst = min(worst, min(vals))
        print(f"    scorer gold-vs-gold {name:8}: {len(vals)} metrics, min {min(vals):.3f}, proxy {m['proxy']:.3f}")
    ok &= worst == 1.0

    tmp = Path(tempfile.mkdtemp(prefix="ghostaudit_selftest_"))
    print("[3] deliberately broken copies must fail the gate:")
    for label, p, code in _broken_copies(tmp):
        bv = gate.check(p, SAMPLE_REQ, MANIFEST, warnings=[])
        hit = next((x for x in bv if x.startswith(code + ":")), None)
        if hit:
            print(f"    {label:14} -> FAILS on {code}: {hit}")
        else:
            print(f"    {label:14} -> WRONG: expected a {code} violation, got {bv[:1] or 'no violation'}")
        ok &= hit is not None

    hits = audit.scan(ROOT / "code")
    print(f"[4] literal audit on code/: {len(hits)} hit(s)")
    ok &= not hits

    m = {"dev": scorer.score(gold, gold, dev), "holdout": scorer.score(gold, gold, hold), "all": scorer.score(gold, gold, dev + hold)}
    d = history.record(RUNS / "selftest", GOLD, m, _commit())
    prev = history.previous(RUNS / "selftest", d)
    print(f"[5] run history: wrote {d.relative_to(ROOT) if d.is_relative_to(ROOT) else d} "
          f"(metrics.json, output.csv, commit); diff vs previous: "
          f"{'first run' if prev is None else str(len(history.diff(prev / 'output.csv', d / 'output.csv'))) + ' change(s)'}")
    print("SELFTEST OK" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("contract"); c.add_argument("--file", default=str(ROOT / "output.csv")); c.add_argument("--requests", default=str(DATA / "deletion_requests.csv"))
    s = sub.add_parser("score"); s.add_argument("--pred", default=""); s.add_argument("--split", default="all", choices=("dev", "all")); s.add_argument("--reveal-holdout", action="store_true"); s.add_argument("--accept-regression", default="")
    d = sub.add_parser("determinism"); d.add_argument("--cmd", default=f"{shlex.quote(sys.executable)} code/main.py"); d.add_argument("--file", default=str(ROOT / "output.csv"))
    lo = sub.add_parser("loaders"); lo.add_argument("--files", default=""); lo.add_argument("--kind", default=""); lo.add_argument("--spot", action="store_true")
    st = sub.add_parser("states"); st.add_argument("--split", default="dev", choices=("dev", "holdout", "all")); st.add_argument("--risk", action="store_true")
    sub.add_parser("audit")
    sub.add_parser("selftest")
    a = p.parse_args(argv)
    os.chdir(ROOT)
    return {"contract": cmd_contract, "score": cmd_score, "determinism": cmd_determinism,
            "audit": cmd_audit, "selftest": cmd_selftest, "loaders": cmd_loaders, "states": cmd_states}[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
