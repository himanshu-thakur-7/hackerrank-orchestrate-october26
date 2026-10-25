"""Loader verification: whole-dataset summary, gold check on sample-cited (file, resource) pairs,
spot checks against raw text, and the smallest records that cannot be attributed to anyone.

Gold is used here only to EVALUATE loaders; nothing in this module is imported by the solver.
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

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
KINDS = {"sql": {"sql"}, "json": {"json:service_exports", "json:snapshots", "json:records"},
         "register-log": {"json:records", "log:record_lookup"}, "log": {"log:observability", "log:readback", "log:record_lookup"},
         "pdf": {"pdf"}, "png": {"png"}, "txt": {"txt:handover"}}


def run(root, files=None, kinds=None, spot=False):
    sys.path.insert(0, str(root / "code"))
    from ghostaudit import identity, loaders
    data = root / "dataset"
    manifest = {r["file_id"]: r for r in csv.DictReader(open(data / "evidence_files.csv", newline="", encoding="utf-8"))}
    resolver = identity.Resolver.from_dataset(data)
    results, unknown = {}, []
    for fid, row in manifest.items():
        try:
            results[fid] = loaders.load_bytes(fid, row["captured_at"], (data / row["file_path"]).read_bytes(), strict=False)
        except loaders.UnknownSignature as e:
            unknown.append(str(e))
    ok = not unknown

    print("DATASET SUMMARY (all evidence files)")
    by_sig = defaultdict(lambda: Counter())
    per_system = Counter()
    for fid, r in results.items():
        c = by_sig[r.signature]
        c["files"] += 1
        built = r.signature in loaders.LOADERS
        c["parsed" if built else "pending"] += 1
        c["observations"] += len(r.observations); c["coverage"] += len(r.coverage)
        c["unattributed"] += len(r.unattributed); c["unparsed"] += len(r.unparsed)
        for o in r.observations:
            per_system[o.system_id] += 1
    for sig in sorted(by_sig):
        c = by_sig[sig]
        status = "built" if sig in loaders.LOADERS else f"pending ({loaders.PENDING.get(sig, '?')})"
        print(f"  {sig:22} files={c['files']:3} {status:16} obs={c['observations']:4} coverage={c['coverage']:3} "
              f"unattributed={c['unattributed']:3} unparsed={c['unparsed']:3}")
    print("  observations per system: " + ", ".join(f"{k}={v}" for k, v in sorted(per_system.items())))
    print(f"  unknown signatures: {len(unknown)}")
    for u in unknown:
        print("    " + u)

    sel = set(files or [])
    if kinds:
        sigs = set().union(*(KINDS[k] for k in kinds))
        sel |= {fid for fid, r in results.items() if r.signature in sigs}
    if not sel:
        sel = {fid for fid, r in results.items() if r.signature in loaders.LOADERS}
    for fid in sorted(sel):
        if fid in results and results[fid].signature not in loaders.LOADERS:
            print(f"  NOTE {fid}: signature {results[fid].signature} not built yet")

    sql_sel = [fid for fid in sorted(sel) if fid in results and results[fid].signature == "sql"]
    if sql_sel:
        drift, files_with = 0, 0
        pending = 0
        for fid in sql_sel:
            obs = results[fid].observations
            pending += sum(1 for o in obs if dict(o.attrs).get("account_status") == "DELETION_PENDING")
            prim = {o.resource_id for o in obs if "primary" in o.table}
            rep = {o.resource_id for o in obs if "replica" in o.table}
            only = sorted(rep - prim) if prim else []
            if only:
                files_with += 1; drift += len(only)
                print(f"  drift {fid}: replica-only {', '.join(only)}")
        print(f"SQL DRIFT: {drift} replica-only resources in {files_with} files")
        print(f"DELETION_PENDING rows: {pending}")
    print("GOLD CHECK (sample steps citing the selected files)")
    gold = {r["case_id"]: json.loads(r["steps_json"]) for r in csv.DictReader(open(data / "sample_output.csv", newline="", encoding="utf-8"))}
    reqs = {r["case_id"]: r for r in csv.DictReader(open(data / "sample_deletion_requests.csv", newline="", encoding="utf-8"))}
    n = fails = 0
    owner = Counter()
    for c, steps in gold.items():
        subject = resolver.resolve(reqs[c]["email"])
        for s in steps:
            fid = s["evidence_id"]
            if fid not in sel or fid not in results:
                continue
            n += 1
            r = results[fid]
            obs = sorted((o for o in r.observations if o.resource_id == s["resource_id"] and o.system_id == s["system_id"]),
                         key=lambda o: o.observed_at)
            covered = any(cv.system_id == s["system_id"] for cv in r.coverage)
            want, pii = EXPECT[s["operation"]]
            got = obs[-1] if obs else None
            if got is None:
                good = want == "ABSENT" and covered
                why = "absent by coverage" if good else "no observation"
            else:
                st = got.state
                good = (st != "ABSENT") if want == "not_absent" else (st == want)
                if good and pii == "pii":
                    good = bool(got.pii_fields)
                if good and pii == "no_pii":
                    good = not got.pii_fields
                why = f"{got.locator} state={st} pii={list(got.pii_fields)}"
            if got is not None:
                owners = {resolver.owner_of(t) for t in got.identifiers} - {None}
                owner["owner-linked" if subject and subject.user_id in owners else ("OTHER OWNER" if owners else "no identifier")] += 1
            if not good:
                fails += 1
                print(f"  FAIL {c} {s['operation']} {s['system_id']}/{s['resource_id']} in {fid}: {why}")
    print(f"  gold-cited pairs: {n} checked, {n - fails} ok, {fails} failed; ownership of matched records: {dict(owner)}")
    ok &= fails == 0

    # whole-store check: every gold expectation at audit_at, using all built loaders (validates ADR 0014)
    from ghostaudit.store import EvidenceFile, EvidenceStore
    files = [EvidenceFile(f, row["file_path"], row["origin"], row["captured_at"]) for f, row in manifest.items()]
    store = EvidenceStore(files=files, observations=[o for r in results.values() for o in r.observations],
                          coverage=[c for r in results.values() for c in r.coverage])
    must_exist = {"REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK",
                  "VERIFY_RECORD_PRESENT", "VERIFY_RECORD_REDACTED", "VERIFY_RECORD_ANONYMIZED",
                  "VERIFY_DATA_FLOW_DISABLED", "VERIFY_RESTORE_BLOCKED"}
    st_n = st_bad = st_unproven = st_pending = 0
    for c, steps in gold.items():
        view = store.as_of(reqs[c]["audit_at"])
        for s in steps:
            if s["phase"] == "REMEDIATION" or not s["evidence_id"]:
                continue          # only cited steps assert an audit-time state; empty evidence = future check
            exist = s["operation"] in must_exist
            st_n += 1
            got = view.state(s["system_id"], s["resource_id"])
            if got is None:
                st_unproven += 1
                continue
            if (got.state == "ABSENT") == exist:
                cited = results.get(s["evidence_id"])
                pending = cited is not None and cited.signature not in loaders.LOADERS
                st_pending += pending
                st_bad += not pending
                tag = f"PENDING (cited {s['evidence_id']} is {cited.signature}, loader not built)" if pending else "CONTRADICTION"
                print(f"  STATE {tag} {c} {s['operation']} {s['system_id']}/{s['resource_id']}: store says {got.state} "
                      f"({got.basis} {got.file_id} {got.locator})")
    print(f"STORE STATE CHECK: {st_n} cited gold expectations, {st_bad} contradictions, {st_pending} pending on unbuilt loaders, "
          f"{st_unproven} unproven")
    ok &= st_bad == 0

    if spot:
        print("SPOT CHECK (first observation per built signature, against the raw file)")
        seen = set()
        for fid in sorted(results, key=lambda x: int(x.split("_")[1])):
            r = results[fid]
            if r.signature in seen or not r.observations:
                continue
            seen.add(r.signature)
            o = r.observations[0]
            ln = int(o.locator.split()[1]) if o.locator.startswith("line ") else None
            raw_lines = (data / manifest[fid]["file_path"]).read_text(encoding="utf-8").splitlines()
            raw = raw_lines[ln - 1].strip() if ln else "?"
            print(f"  [{r.signature}] {fid} {manifest[fid]['file_path']} {o.locator}")
            print(f"     raw:    {raw[:200]}")
            print(f"     parsed: system={o.system_id} resource={o.resource_id} state={o.state} observed_at={o.observed_at} "
                  f"category={o.category} pii={list(o.pii_fields)} ids={list(o.identifiers)} attrs={dict(o.attrs)}")

    print("UNATTRIBUTED (smallest 10 per built signature: no identifier, or no identifier that resolves to a known person)")
    for sig in sorted(s for s in by_sig if s in loaders.LOADERS):
        lost = []
        for fid, r in results.items():
            if r.signature != sig:
                continue
            for o in r.observations:
                if not any(resolver.owner_of(t) for t in o.identifiers):
                    lost.append((fid, o.locator, f"{o.system_id}/{o.resource_id} state={o.state} ids={list(o.identifiers)}"))
            for u in r.unparsed:
                lost.append((fid, u.locator, "UNPARSED " + u.raw[:120]))
        lost.sort(key=lambda x: (len(x[2]), x[0], x[1]))
        print(f"  {sig}: {len(lost)} record(s) not attributable to a person")
        for fid, loc, txt in lost[:10]:
            print(f"    {fid} {loc}: {txt}")
    return 0 if ok else 1
