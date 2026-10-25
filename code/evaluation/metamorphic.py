"""T15 metamorphic relations: transformations of dataset/ with a PREDICTED effect on output.csv.

Each relation edits an Overlay (a temporary copy; dataset/ is never written), runs the real
pipeline, and compares with the baseline. Targets are chosen from the baseline at run time, never
hard-coded. A failing relation is a bug in the pipeline, not in the relation.
"""

import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from evaluation.overlay import Overlay, changed, run_pipeline

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"
INPUT_CSVS = (
    "deletion_requests.csv",
    "sample_deletion_requests.csv",
    "user_identities.csv",
    "user_audit_log.csv",
    "system_activity.csv",
    "deletion_rules.csv",
    "evidence_files.csv",
)
LATE = "2026-12-31T00:00:00Z"  # after every audit_at in the dataset


@dataclass
class Result:
    rid: str
    name: str
    holds: bool
    expect: str
    detail: list = field(default_factory=list)


def _t(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


class Context:
    """Baseline output + in-process assessments, used to pick targets."""

    def __init__(self, data=DATA):
        sys.path.insert(0, str(ROOT / "code"))
        from ghostaudit import data as gdata
        from ghostaudit import intent
        from ghostaudit.engine import Engine

        self.data = data
        self.engine = Engine.from_dataset(data)
        self.requests = gdata.load_requests(data / "deletion_requests.csv")
        self.req = {q["case_id"]: q for q in self.requests}
        self.intent = intent
        self.assess = {
            q["case_id"]: self.engine.assess(q, intent.classify_rules(q["request_text"]))
            for q in self.requests
        }
        with Overlay(data) as ov:
            self.base = ov.run()
            self.base_bytes = (ov.root.parent / "out.csv").read_bytes()

    def cases(self, status=None):
        return [
            c
            for c in sorted(self.assess, key=lambda c: (len(c), c))
            if status is None or self.assess[c].status == status
        ]


def _identical(ctx, out, rid, name, expect, extra=()):
    diff = changed(ctx.base, out)
    return Result(
        rid,
        name,
        not diff and all(extra),
        expect,
        [f"changed cases: {diff[:10]}" + (" ..." if len(diff) > 10 else "")] if diff else [],
    )


def m1_shuffle(ctx):
    with Overlay(ctx.data) as ov:
        rng = random.Random(20261025)
        for name in INPUT_CSVS:
            rows = ov.rows(name)
            rng.shuffle(rows)
            ov.write_rows(name, rows)
        out = ov.run()
    return _identical(
        ctx,
        out,
        "M1",
        "shuffle the rows of every input CSV",
        "identical output (the writer sorts by case_id)",
    )


def m2_rename(ctx):
    with Overlay(ctx.data) as ov:
        m = ov.rows("evidence_files.csv")
        for r in m:
            old = ov.root / r["file_path"]
            new_rel = str(
                Path(r["file_path"]).parent
                / f"renamed_{r['file_id']}{Path(r['file_path']).suffix.upper()}"
            )
            old.rename(ov.root / new_rel)
            r["file_path"] = new_rel
        ov.write_rows("evidence_files.csv", m)
        out = ov.run()
    return _identical(
        ctx,
        out,
        "M2",
        "rename every evidence file and upper-case its extension",
        "identical, evidence_id included: citations are manifest file_ids and loaders dispatch by "
        "content",
    )


def m3_email_case(ctx):
    with Overlay(ctx.data) as ov:
        for name in ("deletion_requests.csv", "sample_deletion_requests.csv"):
            rows = ov.rows(name)
            for i, r in enumerate(rows):
                r["email"] = r["email"].upper() if i % 2 else r["email"].lower()
            ov.write_rows(name, rows)
        out = ov.run()
    return _identical(ctx, out, "M3", "upper/lower-case every request email", "identical")


def _subject_case(ctx, need=lambda a: True):
    for c in ctx.cases():
        a = ctx.assess[c]
        if a.subject and a.status != "NOT_APPLICABLE" and need(a):
            return c, a
    raise LookupError("no target case")


def _log(ts, service, trace, event, extra):
    return (
        f"{ts} level=INFO service={service} instance={service}-9 pod={service}-meta "
        f"region=eu-west-1 trace_id={trace} event={event} {extra}\n"
    )


def m4_decoy(ctx):
    c, a = _subject_case(ctx)
    local, dom = sorted(a.subject.emails)[0].split("@")
    decoy = f"{local}.jr@{dom}"
    assert ctx.engine.resolver.owner_of(decoy) is None, "decoy must not be a real identifier"
    q = ctx.req[c]
    cap = _iso(_t(q["audit_at"]) - timedelta(minutes=5))
    raw = _log(
        cap,
        "search_service",
        "tr-meta-decoy",
        "index_query_started",
        f'match_key="{decoy}" attempt=1',
    ) + _log(
        cap,
        "search_service",
        "tr-meta-decoy",
        "index_query_completed",
        "resource_id=search_990001 result=hit shard=1 took_ms=9",
    )
    with Overlay(ctx.data) as ov:
        ov.add_evidence("meta_decoy", "evidence/logs/meta_decoy.log", "test", cap, raw.encode())
        out = ov.run()
    stray = [
        x
        for x, (_, steps) in out.items()
        if any(s["resource_id"] == "search_990001" for s in steps)
    ]
    r = _identical(
        ctx,
        out,
        "M4",
        f"add a look-alike decoy ({decoy}) for {c}'s subject, before its audit",
        "identical; the decoy resource gets no step anywhere",
        [not stray],
    )
    r.detail += [f"steps on the decoy resource: {stray or 'none'}"]
    return r


def m5_post_audit_mention(ctx):
    c, a = _subject_case(ctx)
    email = sorted(a.subject.emails)[0]
    raw = _log(
        LATE,
        "account_service",
        "tr-meta-late",
        "profile_lookup_started",
        f'lookup_key="{email}" attempt=1',
    ) + _log(
        LATE,
        "account_service",
        "tr-meta-late",
        "profile_lookup_completed",
        "resource_id=account_990001 rows=1 http_status=200",
    )
    with Overlay(ctx.data) as ov:
        ov.add_evidence("meta_late", "evidence/logs/meta_late.log", "test", LATE, raw.encode())
        out = ov.run()
    return _identical(
        ctx,
        out,
        "M5",
        f"inject a file captured after every audit_at that names {c}'s subject",
        "identical (ADR 0002)",
    )


def _complete_with(ctx, op):
    for c in ctx.cases("COMPLETE"):
        for s in ctx.assess[c].steps:
            if s["operation"] == op and s["system_id"] == "account_service":
                return c, s
    raise LookupError(op)


def m6_post_audit_contradiction(ctx):
    c, s = _complete_with(ctx, "VERIFY_RECORD_ABSENT")
    email = sorted(ctx.assess[c].subject.emails)[0]
    raw = _log(
        LATE,
        "account_service",
        "tr-meta-contra",
        "profile_lookup_started",
        f'lookup_key="{email}" attempt=1',
    ) + _log(
        LATE,
        "account_service",
        "tr-meta-contra",
        "profile_lookup_completed",
        f"resource_id={s['resource_id']} rows=1 http_status=200",
    )
    with Overlay(ctx.data) as ov:
        ov.add_evidence("meta_contra", "evidence/logs/meta_contra.log", "test", LATE, raw.encode())
        out = ov.run()
    return _identical(
        ctx,
        out,
        "M6",
        f"inject a post-audit file saying {c}'s {s['resource_id']} is PRESENT again",
        "identical (ADR 0002)",
    )


def m7_earlier_audit(ctx):
    files = {f.file_id: f for f in ctx.engine.store.files.values()}
    for c in ctx.cases("COMPLETE"):
        cited = {s["evidence_id"] for s in ctx.assess[c].steps}
        target = max(cited, key=lambda f: files[f].captured_at)
        new_audit = _iso(_t(files[target].captured_at) - timedelta(seconds=1))
        if new_audit > ctx.req[c]["requested_at"]:
            break
    with Overlay(ctx.data) as ov:
        rows = ov.rows("deletion_requests.csv")
        for r in rows:
            if r["case_id"] == c:
                r["audit_at"] = new_audit
        ov.write_rows("deletion_requests.csv", rows)
        out = ov.run()
    status, steps = out[c]
    still = [s for s in steps if s["evidence_id"] == target]
    late = [
        s for s in steps if s["evidence_id"] and files[s["evidence_id"]].captured_at > new_audit
    ]
    others = [x for x in changed(ctx.base, out) if x != c]
    holds = not still and not late and not others
    return Result(
        "M7",
        f"move {c}'s audit_at to 1 s before {target} (its latest cited file)",
        holds,
        "that file is no longer cited; every citation <= the new audit_at; other cases unchanged",
        [
            f"{c}: {ctx.assess[c].status} -> {status}; cites now "
            f"{sorted({s['evidence_id'] for s in steps if s['evidence_id']})}",
            f"other changed cases: {others or 'none'}",
        ],
    )


def m8_replica_only(ctx):
    # precondition: the injected replica copy must be the NEWEST sighting at or before audit_at, so
    # pick an account whose latest observation is strictly earlier than audit_at and capture the
    # copy at audit_at
    def newest_before_audit(c, s):
        view = ctx.engine.store.as_of(ctx.req[c]["audit_at"])
        obs = [o for o in view.observations(s["resource_id"]) if o.system_id == "account_service"]
        return obs and obs[-1].observed_at < ctx.req[c]["audit_at"]

    c, s = next(
        (c, s)
        for c in ctx.cases("COMPLETE")
        for s in ctx.assess[c].steps
        if s["operation"] == "VERIFY_RECORD_ABSENT"
        and s["system_id"] == "account_service"
        and newest_before_audit(c, s)
    )
    q, subj = ctx.req[c], ctx.assess[c].subject
    ident = next(r for r in ctx.engine.resolver._by_user.values() if r.user_id == subj.user_id)
    email = sorted(subj.emails)[0]
    cap = q["audit_at"]  # inclusive cutoff (ADR 0002)
    name = sorted(ident.names)[0] if ident.names else "Test Person"
    cols = (
        "resource_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, full_name TEXT NOT NULL, email TEXT "
        "NOT NULL, "
        "phone TEXT NOT NULL, account_status TEXT NOT NULL, updated_at TEXT NOT NULL"
    )
    sql = (
        f"-- Ghost Data Still Exists: point-in-time database snapshot\n-- Dialect: "
        f"SQLite-compatible SQL\n"
        f"-- Captured at: {cap}\n-- Database topology: failover_replica\n\nBEGIN TRANSACTION;\n"
        f"CREATE TABLE customer_profiles_failover_replica ({cols});\n"
        f'INSERT INTO "customer_profiles_failover_replica" '
        f"VALUES('{s['resource_id']}','{subj.user_id}','{name}','{email}',"
        f"'+00 000 000 0000','ACTIVE','{cap}');\n"
        f"CREATE TABLE customer_profiles_primary ({cols});\nCOMMIT;\n"
    )
    with Overlay(ctx.data) as ov:
        ov.add_evidence(
            "meta_replica", "evidence/databases/meta_replica.sql", "test", cap, sql.encode()
        )
        out = ov.run()
    status, steps = out[c]
    found = [
        x
        for x in steps
        if x["operation"] == "REPORT_REMAINING_RECORD" and x["resource_id"] == s["resource_id"]
    ]
    holds = status == "INCOMPLETE" and bool(found) and found[0]["evidence_id"] == "meta_replica"
    others = [x for x in changed(ctx.base, out) if x != c]
    return Result(
        "M8",
        f"add a replica-only copy of {c}'s {s['resource_id']} captured at its audit_at",
        holds and not others,
        "that case becomes INCOMPLETE with REPORT_REMAINING_RECORD citing the new snapshot; others "
        "unchanged",
        [
            f"{c}: COMPLETE -> {status}; finding {found[0] if found else 'missing'}",
            f"other changed cases: {others or 'none'}",
        ],
    )


def dependents(ctx, file_id):
    """Eval cases whose assessment could read `file_id`: any observation, link, coverage or
    account candidate."""
    deps = set()
    lk = ctx.engine.linker
    for c, a in ctx.assess.items():
        if a.status == "NOT_APPLICABLE":
            continue
        view = ctx.engine.store.as_of(ctx.req[c]["audit_at"])
        if file_id not in {f.file_id for f in view.files()}:
            continue
        res = [(r.system_id, r.resource_id) for r in a.resources]
        acc = lk.account(c)
        res += [("account_service", x.resource_id) for x in acc.candidates]
        for sys_, rid in res:
            if any(o.file_id == file_id for o in view.observations(rid)):
                deps.add(c)
            if any(
                cv.file_id == file_id and cv.system_id == sys_ for cv in ctx.engine.store.coverage
            ):
                deps.add(c)
        for x in view.linking_observations(a.subject.tokens()).values():
            if any(o.file_id == file_id for o in x):
                deps.add(c)
    return deps


def m9_remove_file(ctx):
    cites = {}
    for c, a in ctx.assess.items():
        for s in a.steps:
            if s["evidence_id"]:
                cites.setdefault(s["evidence_id"], set()).add(c)
    target = max(sorted(cites), key=lambda f: len(cites[f]))
    deps = dependents(ctx, target)
    with Overlay(ctx.data) as ov:
        ov.remove_evidence(target)
        out = ov.run()
    diff = changed(ctx.base, out)
    outside = [c for c in diff if c not in deps]
    return Result(
        "M9",
        f"remove {target} (cited by {len(cites[target])} eval rows)",
        not outside,
        "only cases that read the file change",
        [
            f"{len(diff)} cases changed, all within the {len(deps)} dependents"
            if not outside
            else f"changed outside the dependents: {outside}",
            f"changed: {diff}",
        ],
    )


def m10_duplicate_text(ctx):
    na = next(c for c in ctx.cases("NOT_APPLICABLE"))
    de = next(c for c in ctx.cases("COMPLETE"))
    n = max(int(c.split("_")[1]) for c in ctx.req) + 1
    new = {f"case_{n}": na, f"case_{n + 1}": de}
    with Overlay(ctx.data) as ov:
        rows = ov.rows("deletion_requests.csv")
        for nid, src in new.items():
            r = dict(next(x for x in rows if x["case_id"] == src))
            r["case_id"] = nid
            rows.append(r)
        ov.write_rows("deletion_requests.csv", rows)
        out = ov.run()
    same = all(
        (out[nid][0] == "NOT_APPLICABLE") == (out[src][0] == "NOT_APPLICABLE")
        for nid, src in new.items()
    )
    return Result(
        "M10",
        f"duplicate the request text of {na} (non-deletion) and {de} (deletion) under new case ids",
        same,
        "identical intent (NOT_APPLICABLE iff the original is)",
        [f"{nid} <- {src}: {out[nid][0]} vs {out[src][0]}" for nid, src in new.items()]
        + [
            "note: the duplicate deletion request competes for the same account delete, so its "
            "account link may tie (ADR 0004)"
        ],
    )


def m11_break_tie(ctx):
    lk = ctx.engine.linker
    lk.account(ctx.cases()[0])
    tied = {c: acct for c, acct in lk._accounts.items() if acct.status == "TIED" and c in ctx.req}
    holders = {}
    for c, acct in lk._accounts.items():
        for x in acct.survivors:
            holders.setdefault(x.activity_id, set()).add(c)
    pick = None
    for c, acct in sorted(tied.items(), key=lambda kv: (len(kv[0]), kv[0])):
        if len(acct.survivors) == 2:
            for drop, keep in (
                (acct.survivors[0], acct.survivors[1]),
                (acct.survivors[1], acct.survivors[0]),
            ):
                if holders[keep.activity_id] == {c}:
                    pick = (c, drop, keep)
                    break
        if pick:
            break
    # every tie is shared: removing one candidate must leave all sharers unresolved (no tie-break)
    if pick is None:
        c, acct = min(tied.items(), key=lambda kv: (len(kv[0]), kv[0]))
        pick = (c, acct.survivors[0], acct.survivors[1])
    c, drop, keep = pick
    with Overlay(ctx.data) as ov:
        ov.write_rows(
            "system_activity.csv",
            [r for r in ov.rows("system_activity.csv") if r["activity_id"] != drop.activity_id],
        )
        ov.run()
        sys.path.insert(0, str(ROOT / "code"))
        from ghostaudit.engine import Engine

        e2 = Engine.from_dataset(ov.root)
        got = e2.linker.account(c)
    sharers = holders[keep.activity_id]
    expect_linked = sharers == {c}
    holds = (
        (got.status == "LINKED" and got.resource_id == keep.resource_id)
        if expect_linked
        else got.status == "TIED"
    )
    return Result(
        "M11",
        f"delete {drop.activity_id} ({drop.resource_id}), one of {c}'s tied candidates",
        holds,
        "the remaining candidate becomes the unique linked account"
        if expect_linked
        else "the remaining candidate is shared with another request, so it stays unresolved (no "
        "tie-break)",
        [
            f"{c}: {got.describe()}",
            f"remaining candidate also survives for: {sorted(sharers - {c}) or 'nobody else'}",
        ],
    )


def m12_catalog_contradiction(ctx):
    lk = ctx.engine.linker
    view = ctx.engine.store.as_of("9999-12-31T23:59:59Z")
    confirmed = [x for x in lk.catalog(view, None) if x.status == "CONFIRMED"]
    events = {a.activity_id: a for a in ctx.engine.store.activity_events}
    for link in confirmed:
        ev = events[link.activity_id]
        victim = next(
            (
                c
                for c in ctx.cases()
                if ctx.assess[c].subject
                and ctx.assess[c].status != "NOT_APPLICABLE"
                and ctx.req[c]["audit_at"] >= ev.event_time
                and ctx.assess[c].subject.user_id != link.reason.split("=")[1]
            ),
            None,
        )
        if victim:
            break
    subj = ctx.assess[victim].subject
    claim = (
        f"Data catalog linked {link.resource_id} ({link.resource_id}) to "
        f"{sorted(subj.emails)[0]} and {subj.user_id}."
    )
    with Overlay(ctx.data) as ov:
        rows = ov.rows("system_activity.csv")
        for r in rows:
            if r["activity_id"] == link.activity_id:
                r["details"] = claim
        ov.write_rows("system_activity.csv", rows)
        out = ov.run()
        from ghostaudit.engine import Engine

        e2 = Engine.from_dataset(ov.root)
        a2 = e2.assess(ctx.req[victim], ctx.intent.classify_rules(ctx.req[victim]["request_text"]))
    rejected = [acct for acct in a2.log if acct.startswith(f"REJECTED_LINK({link.activity_id} ")]
    stepped = [s for s in out[victim][1] if s["resource_id"] == link.resource_id]
    return Result(
        "M12",
        f"re-point {link.activity_id} ({link.resource_id}, shown on {link.artifact}) to {victim}'s "
        f"subject",
        bool(rejected) and not stepped and not [x for x in changed(ctx.base, out) if x != victim],
        "the screen shows someone else: the claim is REJECTED, no step on the resource, nothing "
        "else changes",
        [
            rejected[0] if rejected else "no REJECTED_LINK logged",
            f"steps on {link.resource_id}: {len(stepped)}",
            "(screens are committed transcriptions keyed by image hash, so the claim is moved "
            "instead of the pixels)",
        ],
    )


def m13_determinism(ctx):
    outs = []
    with Overlay(ctx.data) as ov:
        for seed in ("0", "4242", "random"):
            run_pipeline(
                ov.root,
                ov.root.parent / f"out_{seed}.csv",
                ov.root / "deletion_requests.csv",
                {"PYTHONHASHSEED": seed},
            )
            outs.append((ov.root.parent / f"out_{seed}.csv").read_bytes())
    same = all(o == ctx.base_bytes for o in outs)
    return Result(
        "M13",
        "run three more times with PYTHONHASHSEED=0, 4242 and random",
        same,
        "byte-identical output.csv",
        [] if same else ["outputs differ"],
    )


RELATIONS = (
    m1_shuffle,
    m2_rename,
    m3_email_case,
    m4_decoy,
    m5_post_audit_mention,
    m6_post_audit_contradiction,
    m7_earlier_audit,
    m8_replica_only,
    m9_remove_file,
    m10_duplicate_text,
    m11_break_tie,
    m12_catalog_contradiction,
    m13_determinism,
)


def run(only=None):
    ctx = Context()
    results = []
    for rel in RELATIONS:
        rid = rel.__name__.split("_")[0].upper()
        if only and rid not in only:
            continue
        try:
            r = rel(ctx)
        except Exception as e:  # a relation that cannot run is a failure, never skipped
            r = Result(
                rid, rel.__name__, False, "relation ran", [f"error: {type(e).__name__}: {e}"]
            )
        results.append(r)
        print(f"{r.rid:4} {'HOLDS' if r.holds else 'FAILS':5}  {r.name}")
        print(f"      expect: {r.expect}")
        for d in r.detail:
            print(f"      {d}")
    ok = sum(r.holds for r in results)
    print(f"METAMORPHIC: {ok}/{len(results)} relations hold")
    return 0 if ok == len(results) else 1
