"""Ghost Data Still Exists — deletion audit.

  python3 code/main.py                       # reads dataset/, writes ./output.csv
  python3 code/main.py --requests dataset/sample_deletion_requests.csv --out /tmp/pred.csv
  python3 code/main.py --report              # intent and identity counts, no file written
  python3 code/main.py --explain <case_id>                 # trace behind one row
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parent
ROOT = CODE.parent
sys.path.insert(0, str(CODE))

from ghostaudit import data, explain, identity, intent, writer  # noqa: E402
from ghostaudit.engine import Engine  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default=str(ROOT / "dataset"))
    p.add_argument("--requests", default=None, help="defaults to <data>/deletion_requests.csv")
    p.add_argument("--out", default=str(ROOT / "output.csv"))
    p.add_argument("--report", action="store_true")
    p.add_argument("--explain", default="", help="print the trace behind one case_id (searches both request files)")
    a = p.parse_args(argv)
    data_dir = Path(a.data)
    reqs = data.load_requests(a.requests or data_dir / "deletion_requests.csv")
    resolver = identity.Resolver.from_dataset(data_dir)
    intents = {q["case_id"]: intent.classify_rules(q["request_text"]) for q in reqs}

    if a.report:
        c = Counter(i.label for i in intents.values())
        nd = sorted((k for k, i in intents.items() if i.label == "NOT_DELETION"), key=writer.natural_key)
        resolved = sum(resolver.resolve(q["email"]) is not None for q in reqs)
        print(f"requests: {len(reqs)}")
        print(f"intent: {c['DELETION']} DELETION / {c['NOT_DELETION']} NOT_DELETION")
        print(f"  NOT_DELETION cases: {', '.join(nd)}")
        print(f"identity: {resolved}/{len(reqs)} resolved")
        return 0

    eng = Engine.from_dataset(data_dir, resolver)
    if a.explain:
        pool = {q["case_id"]: q for f in ("deletion_requests.csv", "sample_deletion_requests.csv")
                for q in data.load_requests(data_dir / f)}
        pool.update({q["case_id"]: q for q in reqs})
        q = pool.get(a.explain)
        if q is None:
            print(f"unknown case_id {a.explain}")
            return 1
        print(explain.render(eng, q, intent.classify_rules(q["request_text"])))
        return 0
    rows = [eng.audit(q, intents[q["case_id"]]) for q in reqs]
    writer.write(a.out, rows)
    print(f"wrote {len(rows)} rows -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
