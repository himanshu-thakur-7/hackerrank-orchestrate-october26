"""Ghost Data Still Exists — deletion audit.

python3 code/main.py                       # reads dataset/, writes ./output.csv
python3 code/main.py --requests dataset/sample_deletion_requests.csv --out /tmp/pred.csv
python3 code/main.py --report              # intent and identity counts, no file written
python3 code/main.py --intent rules        # rules-only intent (no model, no cache)
python3 code/main.py --explain <case_id>                 # trace behind one row
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CODE = Path(__file__).resolve().parent
ROOT = CODE.parent
sys.path.insert(0, str(CODE))

from ghostaudit import data, explain, identity, intent, llm_intent, usage, writer  # noqa: E402
from ghostaudit.engine import Engine  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--data", default=str(ROOT / "dataset"))
    p.add_argument("--requests", default=None, help="defaults to <data>/deletion_requests.csv")
    p.add_argument("--out", default=str(ROOT / "output.csv"))
    p.add_argument("--report", action="store_true")
    p.add_argument(
        "--intent",
        choices=("auto", "rules"),
        default="auto",
        help="auto: rules decide clear texts, the cached model (live only with OPENAI_API_KEY) "
        "decides the rest",
    )
    p.add_argument(
        "--usage-json",
        default="",
        help="also write this run's model usage totals as JSON to this path (for usage_report.md)",
    )
    p.add_argument(
        "--explain",
        default="",
        help="print the trace behind one case_id (searches both request files)",
    )
    return p.parse_args(argv)


@dataclass
class Context:
    """Everything a run needs once the inputs are loaded and every request's intent is decided."""

    data_dir: Path
    requests: list
    resolver: identity.Resolver
    tracker: usage.Tracker
    classifier: llm_intent.IntentClassifier | None
    classify: object
    intents: dict


def build_context(a):
    data_dir = Path(a.data)
    reqs = data.load_requests(a.requests or data_dir / "deletion_requests.csv")
    tracker = usage.Tracker()
    clf = None
    if a.intent != "rules":
        clf = llm_intent.IntentClassifier(
            client=llm_intent.default_client(tracker), tracker=tracker
        )
    classify = intent.classify_rules if clf is None else clf.classify
    intents = {q["case_id"]: classify(q["request_text"]) for q in reqs}
    return Context(
        data_dir, reqs, identity.Resolver.from_dataset(data_dir), tracker, clf, classify, intents
    )


def report(ctx):
    """--report: intent and identity counts; no file is written."""
    c = Counter(i.label for i in ctx.intents.values())
    nd = sorted(
        (k for k, i in ctx.intents.items() if i.label == "NOT_DELETION"), key=writer.natural_key
    )
    resolved = sum(ctx.resolver.resolve(q["email"]) is not None for q in ctx.requests)
    print(f"requests: {len(ctx.requests)}")
    print(f"intent: {c['DELETION']} DELETION / {c['NOT_DELETION']} NOT_DELETION")
    print(f"  NOT_DELETION cases: {', '.join(nd)}")
    print(f"identity: {resolved}/{len(ctx.requests)} resolved")
    return 0


def explain_case(ctx, eng, case_id):
    """--explain: the trace behind one row, searched in both request files and --requests."""
    pool = {
        q["case_id"]: q
        for f in ("deletion_requests.csv", "sample_deletion_requests.csv")
        for q in data.load_requests(ctx.data_dir / f)
    }
    pool.update({q["case_id"]: q for q in ctx.requests})
    q = pool.get(case_id)
    if q is None:
        print(f"unknown case_id {case_id}")
        return 1
    print(explain.render(eng, q, ctx.classify(q["request_text"])))
    return 0


def run(ctx, eng, a):
    """Write output.csv, print the run summaries and record model usage."""
    rows = [eng.audit(q, ctx.intents[q["case_id"]]) for q in ctx.requests]
    writer.write(a.out, rows)
    print(f"wrote {len(rows)} rows -> {a.out}")
    print(eng.linker.summary([q["case_id"] for q in ctx.requests]))
    if ctx.classifier is not None:
        ctx.classifier.save()
        print(ctx.classifier.summary())
        print(ctx.tracker.summary())
        usage.write_run_log(ROOT / "runs" / "usage", ctx.tracker)
    if a.usage_json:
        summary = {
            "requests": len(rows),
            "totals": ctx.tracker.totals(),
            "intent": ctx.classifier.counts if ctx.classifier is not None else None,
        }
        Path(a.usage_json).write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    return 0


def main(argv=None):
    a = parse_args(argv)
    ctx = build_context(a)
    if a.report:
        return report(ctx)
    eng = Engine.from_dataset(ctx.data_dir, ctx.resolver, ctx.classify)
    if a.explain:
        return explain_case(ctx, eng, a.explain)
    return run(ctx, eng, a)


if __name__ == "__main__":
    sys.exit(main())
