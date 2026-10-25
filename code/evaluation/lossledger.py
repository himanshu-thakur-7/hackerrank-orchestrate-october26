"""T16 loss ledger: for EVERY evaluation case, why its row may not be the full answer.

A case is "fully grounded" when it has a linked primary account and no loss reason; every other case
gets one or more reasons. "unknown" (no account step and no logged reason) must stay at zero.

Reasons (from the engine's own assessment and log, never from gold):
  unresolved:tied        UNRESOLVED_LINK, several account candidates survive (ADR 0004)
  unresolved:window      UNRESOLVED_LINK, no account delete in the window (42 h family)
  unresolved:catalog     catalog claim with no confirming artifact (ADR 0005)
  contradicted           REJECTED_LINK, the artifact shows someone else (ADR 0005)
  unproven               a linked resource with no provable end state (ADR 0006)
  no-step:<why>          a linked resource that policy cannot plan (not observable,
                         unresolved category, ...)
  unlabeled:<rule>       decided by a rule no sample labels: DELETION_PENDING (ADR 0010),
                         legal hold (ADR 0011), INCOMPLETE [] (ADR 0015), stale link dropped
                         (ADR 0016)
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# sample-measured rates for the step-ceiling estimate (docs/03_ID_RECOVERY_PROTOTYPE.md §6, docs/02
# §4.5)
# VERIFY_RECORD_ANONYMIZED steps per deletion case lost to analytics reachable only through activity
# bursts, and audit records that appear in no file (about 3 of 32 samples)
ANALYTICS_MISSING_PER_CASE = 0.22
AUDIT_RECORD_MISSING_PER_CASE = 0.09
STEPS_PER_UNRESOLVED_ACCOUNT = (
    1 + 2 * 0.14
)  # VERIFY_ABSENT, plus finding+remediation when still present (3/22)


def _account_link_reason(line):
    return "unresolved:tied" if "survive" in line or "claimed" in line else "unresolved:window"


def _no_step_reason(line):
    why = line.split(": ", 1)[1].rstrip(")")
    return "no-step:" + why.split("(")[0].split(",")[0].strip()


# (log line prefix, reason or reason function), checked in this order
LOG_REASONS = (
    ("UNRESOLVED_LINK(primary account", _account_link_reason),
    ("UNRESOLVED_LINK(", "unresolved:catalog"),
    ("REJECTED_LINK(", "contradicted"),
    ("UNPROVEN(", "unproven"),
    ("NO_STEP(", _no_step_reason),
    ("STALE_LINK(", "unlabeled:stale link (ADR 0016)"),
)


def _log_reason(line):
    if line == "NO_GROUNDED_STEP":
        return "unlabeled:INCOMPLETE [] (ADR 0015)"
    for prefix, reason in LOG_REASONS:
        if line.startswith(prefix):
            return reason(line) if callable(reason) else reason
    return None


def _account_status(r):
    attrs = r.state.observation.attrs if r.state and r.state.observation else ()
    return dict(attrs).get("account_status")


def _resource_reasons(a, r):
    out = []
    if r.treatment.kind == "unproven" and a.status == "INCOMPLETE":
        out.append("unproven")
    if r.system_id == "account_service" and _account_status(r) == "DELETION_PENDING":
        out.append("unlabeled:DELETION_PENDING (ADR 0010)")
    if r.system_id == "legal_service" and r.treatment.verification == "VERIFY_RECORD_PRESENT":
        out.append("unlabeled:legal hold (ADR 0011)")
    return out


def reasons(a, linker_status):
    """Every loss reason of one assessed case, from its log and its resources."""
    out = [x for x in map(_log_reason, a.log) if x]
    for r in a.resources:
        out += _resource_reasons(a, r)
    return sorted(set(out))


def ceiling(counts, n_cases, emitted):
    """Step-recall ceiling estimate from ledger counts (rates measured on the samples, see module
    constants)."""
    deletion = n_cases - counts.get("resolved:non-deletion", 0)
    unres = counts.get("unresolved:tied", 0) + counts.get("unresolved:window", 0)
    missing = (
        unres * STEPS_PER_UNRESOLVED_ACCOUNT
        + counts.get("unresolved:catalog", 0)
        + ANALYTICS_MISSING_PER_CASE * deletion
        + AUDIT_RECORD_MISSING_PER_CASE * deletion
    )
    return {
        "emitted": emitted,
        "missing": missing,
        "recall": emitted / (emitted + missing) if emitted + missing else 1.0,
    }


def run(root=ROOT, write=None):
    sys.path.insert(0, str(root / "code"))
    from ghostaudit import data, intent
    from ghostaudit.engine import Engine

    d = root / "dataset"
    eng = Engine.from_dataset(d)
    ledger, per_reason = {}, defaultdict(list)
    emitted = 0
    for q in data.load_requests(d / "deletion_requests.csv"):
        a = eng.assess(q, intent.classify_rules(q["request_text"]))
        emitted += len(a.steps)
        if a.status == "NOT_APPLICABLE":
            ledger[q["case_id"]] = ["resolved:non-deletion"]
            continue
        rs = reasons(a, eng.linker.account(q["case_id"]).status)
        has_account = any(r.system_id == "account_service" for r in a.resources)
        if not rs:
            rs = ["fully grounded"] if has_account else ["unknown"]
        ledger[q["case_id"]] = rs
        for x in rs:
            per_reason[x].append(q["case_id"])
    counts = Counter(x for rs in ledger.values() for x in rs)
    print(f"LOSS LEDGER over {len(ledger)} eval cases (a case can carry several reasons)")
    for k in sorted(counts, key=lambda k: (-counts[k], k)):
        print(f"  {k:42} {counts[k]:4}")
    print(f"  unknown: {counts['unknown']}")
    # step-level ceiling: emitted grounded steps vs emitted + expected missing
    unres = counts["unresolved:tied"] + counts["unresolved:window"]
    missing = (
        unres * STEPS_PER_UNRESOLVED_ACCOUNT
        + counts["unresolved:catalog"]
        + counts["contradicted"] * 0
        + 0.22
        * (
            len(ledger) - counts["resolved:non-deletion"]
        )  # unlinked anonymized analytics (7/32 samples)
        + 0.09 * (len(ledger) - counts["resolved:non-deletion"])
    )  # unreachable audit records (3/32 samples)
    print(
        f"STEP CEILING (estimate): {emitted} steps emitted; ~{missing:.0f} gold-style steps "
        f"expected missing "
        f"({unres} unresolved accounts x {STEPS_PER_UNRESOLVED_ACCOUNT:.2f}, + unlinked anonymized "
        f"analytics ~0.22/case, "
        f"+ unreachable audit records ~0.09/case, + {counts['unresolved:catalog']} catalog) -> "
        f"step recall ceiling "
        f"~{emitted / (emitted + missing):.2f}"
    )
    if write:
        lines = [
            "# Loss ledger (generated by `python3 code/evaluation/main.py lossledger`)",
            "",
            "| Reason | Cases | Case ids |",
            "| --- | --- | --- |",
        ]
        for k in sorted(per_reason, key=lambda k: (-len(per_reason[k]), k)):
            ids = per_reason[k]
            lines.append(f"| {k} | {len(ids)} | {', '.join(ids)} |")
        lines += [
            "",
            f"Non-deletion (NOT_APPLICABLE, resolved): {counts['resolved:non-deletion']}. Unknown: "
            f"{counts['unknown']}.",
            f"Step ceiling estimate: {emitted} emitted, ~{missing:.0f} expected missing, recall "
            f"ceiling ~{emitted / (emitted + missing):.2f}.",
            "",
        ]
        Path(write).write_text("\n".join(lines), encoding="utf-8")
        print(f"written: {write}")
    return 0 if counts["unknown"] == 0 else 1, ledger
