"""Frozen dev/holdout split of the labeled samples (22 dev / 10 holdout).

The split is made ONCE (`python3 code/evaluation/split.py --freeze`) and written to
fixtures/sample_split.txt. Afterwards it is only read, never regenerated. Tuning looks at dev
only; holdout is reported as aggregates unless --reveal-holdout is used (and that use is logged).

Strata: (gold status, evidence format), where the format is the sorted set of file
extensions the gold row cites. The holdout count per status is proportional and rounded
(INCOMPLETE 22 -> 7, COMPLETE 10 -> 3). Within a status, the holdout slots go to formats by
largest remainder, and cases are drawn with random.Random(seed) after natural-order sorting.

Decisions: ADR: none (evaluation only; gold labels are read here, never by the solver).
"""

import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE / "fixtures" / "sample_split.txt"
HOLDOUT_SIZE = 10
SEED = 20261025  # the seed the frozen split was made with (recorded in the split file)


def _natural(c):
    p, _, n = c.rpartition("_")
    return (p, int(n)) if n.isdigit() else (c, -1)


def formats(gold, manifest_path):
    """case_id -> the evidence format of its gold row (sorted cited extensions, or 'none')."""
    with open(manifest_path, newline="", encoding="utf-8") as f:
        ext = {r["file_id"]: Path(r["file_path"]).suffix.lstrip(".") for r in csv.DictReader(f)}
    out = {}
    for c, (_, steps) in gold.items():
        fs = sorted({ext.get(s["evidence_id"], "other") for s in steps if s["evidence_id"]})
        out[c] = "+".join(fs) or "none"
    return out


def _largest_remainder(sizes, total):
    whole = sum(sizes.values())
    quota = {k: total * v / whole for k, v in sizes.items()}
    alloc = {k: int(q) for k, q in quota.items()}
    rest = total - sum(alloc.values())
    for k in sorted(quota, key=lambda k: (-(quota[k] - alloc[k]), str(k)))[:rest]:
        alloc[k] += 1
    return alloc


def make_split(gold, manifest_path, seed):
    """(dev, holdout) case ids: HOLDOUT_SIZE cases stratified by (gold status, format)
    with largest-remainder allocation, drawn with random.Random(seed)."""
    rng = random.Random(seed)
    fmt = formats(gold, manifest_path)
    by_status = defaultdict(list)
    for c in sorted(gold, key=_natural):
        by_status[gold[c][0]].append(c)
    per_status = _largest_remainder({s: len(v) for s, v in by_status.items()}, HOLDOUT_SIZE)
    hold = []
    for status in sorted(by_status):
        strata = defaultdict(list)
        for c in by_status[status]:
            strata[fmt[c]].append(c)
        alloc = _largest_remainder({f: len(v) for f, v in strata.items()}, per_status[status])
        for f in sorted(strata):
            pool = list(strata[f])
            rng.shuffle(pool)
            hold += pool[: alloc[f]]
    hold = sorted(hold, key=_natural)
    dev = [c for c in sorted(gold, key=_natural) if c not in set(hold)]
    return dev, hold


def load_frozen(path=FROZEN):
    """(dev, holdout, seed) from the frozen split file."""
    dev, hold, seed = [], [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("seed="):
            seed = int(line.split("=", 1)[1])
        elif line.startswith("dev="):
            dev = [x for x in line.split("=", 1)[1].split(",") if x]
        elif line.startswith("holdout="):
            hold = [x for x in line.split("=", 1)[1].split(",") if x]
    return dev, hold, seed


def freeze(seed=SEED):
    """Make and write the split once; refuses to overwrite an existing frozen split."""
    sys.path.insert(0, str(HERE.parent))
    from evaluation import scorer

    root = HERE.parents[1]
    gold = scorer.load(root / "dataset" / "sample_output.csv")
    if FROZEN.exists():
        raise SystemExit(f"refusing to overwrite the frozen split at {FROZEN}")
    dev, hold = make_split(gold, root / "dataset" / "evidence_files.csv", seed)
    FROZEN.write_text(
        "# Frozen dev/holdout split of dataset/sample_output.csv. Made once; do not edit.\n"
        f"seed={seed}\ndev={','.join(dev)}\nholdout={','.join(hold)}\n",
        encoding="utf-8",
    )
    print(f"froze {len(dev)} dev / {len(hold)} holdout with seed {seed} -> {FROZEN}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--freeze"]:
        freeze()
    else:
        print(__doc__)
