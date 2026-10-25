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
from pathlib import Path

CODE = Path(__file__).resolve().parent
ROOT = CODE.parent
sys.path.insert(0, str(CODE))

from ghostaudit import data, explain, identity, intent, llm_intent, usage, writer  # noqa: E402
from ghostaudit.engine import Engine  # noqa: E402


def main(argv=None):
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
    a = p.parse_args(argv)
    data_dir = Path(a.data)
    reqs = data.load_requests(a.requests or data_dir / "deletion_requests.csv")
    resolver = identity.Resolver.from_dataset(data_dir)
    tracker = usage.Tracker()
    clf = (
        None
        if a.intent == "rules"
        else llm_intent.IntentClassifier(client=llm_intent.default_client(tracker), tracker=tracker)
    )
    classify = intent.classify_rules if clf is None else clf.classify
    intents = {q["case_id"]: classify(q["request_text"]) for q in reqs}

    if a.report:
        c = Counter(i.label for i in intents.values())
        nd = sorted(
            (k for k, i in intents.items() if i.label == "NOT_DELETION"), key=writer.natural_key
        )
        resolved = sum(resolver.resolve(q["email"]) is not None for q in reqs)
        print(f"requests: {len(reqs)}")
        print(f"intent: {c['DELETION']} DELETION / {c['NOT_DELETION']} NOT_DELETION")
        print(f"  NOT_DELETION cases: {', '.join(nd)}")
        print(f"identity: {resolved}/{len(reqs)} resolved")
        return 0

    eng = Engine.from_dataset(data_dir, resolver, classify)
    if a.explain:
        pool = {
            q["case_id"]: q
            for f in ("deletion_requests.csv", "sample_deletion_requests.csv")
            for q in data.load_requests(data_dir / f)
        }
        pool.update({q["case_id"]: q for q in reqs})
        q = pool.get(a.explain)
        if q is None:
            print(f"unknown case_id {a.explain}")
            return 1
        print(explain.render(eng, q, classify(q["request_text"])))
        return 0
    rows = [eng.audit(q, intents[q["case_id"]]) for q in reqs]
    writer.write(a.out, rows)
    print(f"wrote {len(rows)} rows -> {a.out}")
    print(eng.linker.summary([q["case_id"] for q in reqs]))
    if clf is not None:
        clf.save()
        print(clf.summary())
        print(tracker.summary())
        usage.write_run_log(ROOT / "runs" / "usage", tracker)
    if a.usage_json:
        Path(a.usage_json).write_text(
            json.dumps(
                {
                    "requests": len(rows),
                    "totals": tracker.totals(),
                    "intent": clf.counts if clf is not None else None,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
