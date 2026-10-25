"""T16 silver-label audit sample: 20 eval cases stratified by loss-ledger reason, drawn with a fixed
seed.
Strata sizes are fixed below; inside a stratum, cases are shuffled with random.Random(SEED) after
natural sorting."""

import random

SEED = 20261025
STRATA = (
    ("fully grounded:COMPLETE", 4),
    ("fully grounded:INCOMPLETE", 3),
    ("unlabeled:DELETION_PENDING (ADR 0010)", 2),
    ("unlabeled:legal hold (ADR 0011)", 2),
    ("unresolved:tied", 3),
    ("unresolved:window", 2),
    ("unproven", 1),
    ("unlabeled:INCOMPLETE [] (ADR 0015)", 1),
    ("unresolved:catalog", 1),
    ("contradicted", 1),
    ("resolved:non-deletion", 1),
)


def sample(ledger, status):
    rng = random.Random(SEED)
    picked, used = [], set()

    def nat(c):
        return (len(c), c)

    for name, k in STRATA:
        reason, _, st = (
            name.partition(":") if name.startswith("fully grounded:") else (name, "", "")
        )
        pool = sorted(
            (
                c
                for c, rs in ledger.items()
                if (name.split(":")[0] if st else name) in rs
                and (not st or status[c] == st)
                and c not in used
            ),
            key=nat,
        )
        rng.shuffle(pool)
        for c in pool[:k]:
            picked.append((name, c))
            used.add(c)
    return picked
