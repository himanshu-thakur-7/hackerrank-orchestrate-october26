"""Loader verification: whole-dataset summary, gold check on sample-cited (file, resource) pairs,
spot checks against raw text, and the smallest records that cannot be attributed to anyone.

Gold is used here only to EVALUATE loaders; nothing in this module is imported by the solver.
"""

import json
import sys
from collections import Counter, defaultdict

from ghostaudit.data import read_csv

# expected loader-level state for each gold operation that cites evidence
EXPECT = {
    "REPORT_REMAINING_RECORD": ("not_absent", None),
    "REPORT_EXPOSED_PII": ("not_absent", "pii"),
    "REPORT_ACTIVE_DATA_FLOW": ("ACTIVE", None),
    "REPORT_RESTORE_RISK": ("RESTORABLE", None),
    "VERIFY_RECORD_ABSENT": ("ABSENT", None),
    "VERIFY_RECORD_PRESENT": ("not_absent", None),
    "VERIFY_RECORD_REDACTED": ("not_absent", "no_pii"),
    "VERIFY_RECORD_ANONYMIZED": ("not_absent", "no_pii"),
    "VERIFY_DATA_FLOW_DISABLED": ("DISABLED", None),
    "VERIFY_RESTORE_BLOCKED": ("BLOCKED", None),
}
KINDS = {
    "sql": {"sql"},
    "json": {"json:service_exports", "json:snapshots", "json:records"},
    "register-log": {"json:records", "log:record_lookup"},
    "log": {"log:observability", "log:readback", "log:record_lookup"},
    "pdf": {"pdf"},
    "png": {"png"},
    "txt": {"txt:handover"},
}


MUST_EXIST = {
    "REPORT_REMAINING_RECORD",
    "REPORT_EXPOSED_PII",
    "REPORT_ACTIVE_DATA_FLOW",
    "REPORT_RESTORE_RISK",
    "VERIFY_RECORD_PRESENT",
    "VERIFY_RECORD_REDACTED",
    "VERIFY_RECORD_ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED",
    "VERIFY_RESTORE_BLOCKED",
}


def _numeric(fid):
    return int(fid.split("_")[1])


def _load_all(data, manifest, loaders):
    """Every manifest file through the loaders (non-strict): {file_id: LoadResult}, unknown list."""
    results, unknown = {}, []
    for fid, row in manifest.items():
        try:
            raw = (data / row["file_path"]).read_bytes()
            results[fid] = loaders.load_bytes(fid, row["captured_at"], raw, strict=False)
        except loaders.UnknownSignature as e:
            unknown.append(str(e))
    return results, unknown


def _signature_counts(results, loaders):
    by_sig = defaultdict(lambda: Counter())
    per_system = Counter()
    for r in results.values():
        c = by_sig[r.signature]
        c["files"] += 1
        c["parsed" if r.signature in loaders.LOADERS else "pending"] += 1
        c["observations"] += len(r.observations)
        c["coverage"] += len(r.coverage)
        c["unattributed"] += len(r.unattributed)
        c["unparsed"] += len(r.unparsed)
        per_system.update(o.system_id for o in r.observations)
    return by_sig, per_system


def _print_summary(results, unknown, loaders):
    print("DATASET SUMMARY (all evidence files)")
    by_sig, per_system = _signature_counts(results, loaders)
    for sig in sorted(by_sig):
        c = by_sig[sig]
        status = "built" if sig in loaders.LOADERS else f"pending ({loaders.PENDING.get(sig, '?')})"
        print(
            f"  {sig:22} files={c['files']:3} {status:16} obs={c['observations']:4} "
            f"coverage={c['coverage']:3} "
            f"unattributed={c['unattributed']:3} unparsed={c['unparsed']:3}"
        )
    print(
        "  observations per system: " + ", ".join(f"{k}={v}" for k, v in sorted(per_system.items()))
    )
    print(f"  unknown signatures: {len(unknown)}")
    for u in unknown:
        print("    " + u)
    return by_sig


def _selection(results, files, kinds, loaders):
    """Files to check: --files and --kind, or every file with a built loader."""
    sel = set(files or [])
    if kinds:
        sigs = set().union(*(KINDS[k] for k in kinds))
        sel |= {fid for fid, r in results.items() if r.signature in sigs}
    if not sel:
        sel = {fid for fid, r in results.items() if r.signature in loaders.LOADERS}
    for fid in sorted(sel):
        if fid in results and results[fid].signature not in loaders.LOADERS:
            print(f"  NOTE {fid}: signature {results[fid].signature} not built yet")
    return sel


def _sql_drift(results, sel):
    """Replica-only records (deleted from the primary, kept in a replica); DELETION_PENDING rows."""
    sql_sel = [fid for fid in sorted(sel) if fid in results and results[fid].signature == "sql"]
    if not sql_sel:
        return
    drift, files_with, pending = 0, 0, 0
    for fid in sql_sel:
        obs = results[fid].observations
        pending += sum(1 for o in obs if dict(o.attrs).get("account_status") == "DELETION_PENDING")
        prim = {o.resource_id for o in obs if "primary" in o.table}
        rep = {o.resource_id for o in obs if "replica" in o.table}
        only = sorted(rep - prim) if prim else []
        if only:
            files_with += 1
            drift += len(only)
            print(f"  drift {fid}: replica-only {', '.join(only)}")
    print(f"SQL DRIFT: {drift} replica-only resources in {files_with} files")
    print(f"DELETION_PENDING rows: {pending}")


def _judge_gold_step(s, r):
    """(good, why, latest observation) for one gold step against the file it cites."""
    obs = sorted(
        (
            o
            for o in r.observations
            if o.resource_id == s["resource_id"] and o.system_id == s["system_id"]
        ),
        key=lambda o: o.observed_at,
    )
    want, pii = EXPECT[s["operation"]]
    got = obs[-1] if obs else None
    if got is None:
        good = want == "ABSENT" and any(cv.system_id == s["system_id"] for cv in r.coverage)
        return good, ("absent by coverage" if good else "no observation"), None
    st = got.state
    good = (st != "ABSENT") if want == "not_absent" else (st == want)
    if good and pii == "pii":
        good = bool(got.pii_fields)
    if good and pii == "no_pii":
        good = not got.pii_fields
    return good, f"{got.locator} state={st} pii={list(got.pii_fields)}", got


def _ownership(subject, got, resolver):
    owners = {resolver.owner_of(t) for t in got.identifiers} - {None}
    if subject and subject.user_id in owners:
        return "owner-linked"
    return "OTHER OWNER" if owners else "no identifier"


def _gold_check(results, sel, gold, reqs, resolver):
    """Every sample gold step citing a selected file, against that file's content."""
    print("GOLD CHECK (sample steps citing the selected files)")
    n = fails = 0
    owner = Counter()
    for c, steps in gold.items():
        subject = resolver.resolve(reqs[c]["email"])
        for s in steps:
            fid = s["evidence_id"]
            if fid not in sel or fid not in results:
                continue
            n += 1
            good, why, got = _judge_gold_step(s, results[fid])
            if got is not None:
                owner[_ownership(subject, got, resolver)] += 1
            if not good:
                fails += 1
                print(
                    f"  FAIL {c} {s['operation']} {s['system_id']}/{s['resource_id']} in {fid}: "
                    f"{why}"
                )
    print(
        f"  gold-cited pairs: {n} checked, {n - fails} ok, {fails} failed; ownership of matched "
        f"records: {dict(owner)}"
    )
    return fails


def _build_store(results, manifest):
    from ghostaudit.store import EvidenceFile, EvidenceStore

    files = [
        EvidenceFile(f, row["file_path"], row["origin"], row["captured_at"])
        for f, row in manifest.items()
    ]
    return EvidenceStore(
        files=files,
        observations=[o for r in results.values() for o in r.observations],
        coverage=[c for r in results.values() for c in r.coverage],
    )


def _store_check(results, manifest, gold, reqs, loaders):
    """Whole-store check: every cited gold expectation at audit_at, using all built loaders
    (validates ADR 0014). Returns the number of contradictions."""
    store = _build_store(results, manifest)
    st_n = st_bad = st_unproven = st_pending = 0
    for c, steps in gold.items():
        view = store.as_of(reqs[c]["audit_at"])
        # only cited steps assert an audit-time state; empty evidence = future check
        for s in (s for s in steps if s["phase"] != "REMEDIATION" and s["evidence_id"]):
            st_n += 1
            got = view.state(s["system_id"], s["resource_id"])
            if got is None:
                st_unproven += 1
                continue
            if (got.state == "ABSENT") == (s["operation"] in MUST_EXIST):
                cited = results.get(s["evidence_id"])
                pending = cited is not None and cited.signature not in loaders.LOADERS
                st_pending += pending
                st_bad += not pending
                _print_state_issue(c, s, got, cited, pending)
    print(
        f"STORE STATE CHECK: {st_n} cited gold expectations, {st_bad} contradictions, {st_pending} "
        f"pending on unbuilt loaders, "
        f"{st_unproven} unproven"
    )
    return st_bad


def _print_state_issue(c, s, got, cited, pending):
    tag = (
        f"PENDING (cited {s['evidence_id']} is {cited.signature}, loader not built)"
        if pending
        else "CONTRADICTION"
    )
    print(
        f"  STATE {tag} {c} {s['operation']} {s['system_id']}/{s['resource_id']}: "
        f"store says {got.state} "
        f"({got.basis} {got.file_id} {got.locator})"
    )


def _spot_check(results, data, manifest):
    print("SPOT CHECK (first observation per built signature, against the raw file)")
    seen = set()
    for fid in sorted(results, key=_numeric):
        r = results[fid]
        if r.signature in seen or not r.observations:
            continue
        seen.add(r.signature)
        o = r.observations[0]
        raw = _raw_unit(data / manifest[fid]["file_path"], r.signature, o.locator)
        print(f"  [{r.signature}] {fid} {manifest[fid]['file_path']} {o.locator}")
        print(f"     raw:    {raw[:200]}")
        print(
            f"     parsed: system={o.system_id} resource={o.resource_id} state={o.state} "
            f"observed_at={o.observed_at} "
            f"category={o.category} pii={list(o.pii_fields)} ids={list(o.identifiers)} "
            f"attrs={dict(o.attrs)}"
        )


def _document_facts(results, sel, manifest, resolver):
    doc_sel = [
        fid
        for fid in sorted(sel, key=_numeric)
        if fid in results and results[fid].signature in ("pdf", "png")
    ]
    if not doc_sel:
        return
    print("DOCUMENT AND SCREEN FACTS (compare with docs/02b)")
    for fid in doc_sel:
        r = results[fid]
        print(f"  {fid} {manifest[fid]['file_path']} [{r.signature}]")
        for o in r.observations:
            owners = sorted({resolver.owner_of(t) or "nobody" for t in o.identifiers}) or ["-"]
            print(
                f"    {o.system_id}/{o.resource_id} {o.state} ids={list(o.identifiers)} -> "
                f"{owners} pii={list(o.pii_fields)} attrs={dict(o.attrs)}"
            )
        for u in r.unattributed:
            if u.reason == "no resource id":
                print(f"    (no resource id) {u.locator}: {u.raw[:150]}")


def _unattributable(results, sig, resolver):
    """(file, locator, text) of records of one signature that no known person owns."""
    lost = []
    for fid, r in results.items():
        if r.signature != sig:
            continue
        for o in r.observations:
            if not any(resolver.owner_of(t) for t in o.identifiers):
                lost.append(
                    (
                        fid,
                        o.locator,
                        f"{o.system_id}/{o.resource_id} state={o.state} ids={list(o.identifiers)}",
                    )
                )
        lost += [(fid, u.locator, "UNPARSED " + u.raw[:120]) for u in r.unparsed]
    return sorted(lost, key=lambda x: (len(x[2]), x[0], x[1]))


def _print_unattributed(results, by_sig, resolver, loaders):
    print(
        "UNATTRIBUTED (smallest 10 per built signature: no identifier, or no identifier that "
        "resolves to a known person)"
    )
    for sig in sorted(s for s in by_sig if s in loaders.LOADERS):
        lost = _unattributable(results, sig, resolver)
        print(f"  {sig}: {len(lost)} record(s) not attributable to a person")
        for fid, loc, txt in lost[:10]:
            print(f"    {fid} {loc}: {txt}")


def run(root, files=None, kinds=None, spot=False):
    sys.path.insert(0, str(root / "code"))
    from ghostaudit import identity, loaders

    data = root / "dataset"
    manifest = {r["file_id"]: r for r in read_csv(data / "evidence_files.csv")}
    resolver = identity.Resolver.from_dataset(data)
    results, unknown = _load_all(data, manifest, loaders)
    by_sig = _print_summary(results, unknown, loaders)
    sel = _selection(results, files, kinds, loaders)
    _sql_drift(results, sel)
    gold = {r["case_id"]: json.loads(r["steps_json"]) for r in read_csv(data / "sample_output.csv")}
    reqs = {r["case_id"]: r for r in read_csv(data / "sample_deletion_requests.csv")}
    fails = _gold_check(results, sel, gold, reqs, resolver)
    st_bad = _store_check(results, manifest, gold, reqs, loaders)
    if spot:
        _spot_check(results, data, manifest)
    _document_facts(results, sel, manifest, resolver)
    _print_unattributed(results, by_sig, resolver, loaders)
    return 0 if not unknown and fails == 0 and st_bad == 0 else 1


def _raw_unit(path, signature, locator):
    """The raw text behind a locator: a file line, a PDF text line, or a screen transcription
    region."""
    if signature == "png":
        return f"(screen transcription, {locator})"
    if signature == "pdf":
        from ghostaudit.loaders import pdf

        lines = pdf.extract_text(path.read_bytes()).splitlines()
        loc = locator.replace("text ", "")
    else:
        lines = path.read_text(encoding="utf-8").splitlines()
        loc = locator
    if not loc.startswith("line "):
        return "?"
    n = int(loc.split()[1])
    return lines[n - 1].strip() if n <= len(lines) else "?"
