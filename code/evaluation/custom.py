"""T13 custom evaluation cases: apply the synthetic fixtures to a dataset overlay, run the real pipeline, and
compare each custom row with its hand-written expectation (and required log lines). Also checks that the
518 real rows are unchanged by the additions."""

import sys
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.overlay import Overlay, changed, run_pipeline

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"


@dataclass
class CaseResult:
    case_id: str
    title: str
    ok: bool
    problems: list = field(default_factory=list)


@dataclass
class Report:
    results: list
    real_rows_changed: list


def apply(ov, cases):
    adds = {
        "user_identities.csv": "people",
        "user_audit_log.csv": "audit",
        "deletion_requests.csv": "requests",
        "system_activity.csv": "activity",
    }
    for name, key in adds.items():
        rows = ov.rows(name)
        for c in cases:
            rows += c.get(key, [])
        ov.write_rows(name, rows)
    for c in cases:
        for fid, path, cap, text in c.get("files", []):
            ov.add_evidence(fid, path, "custom_fixture", cap, text.encode("utf-8"))


def _compare(cid, got, want):
    problems = []
    gs, gsteps = got if got else (None, [])
    ws, wsteps = want
    if gs != ws:
        problems.append(f"status: expected {ws}, got {gs}")
    strip = lambda steps: [{k: v for k, v in s.items() if k != "step_no"} for s in steps]
    if strip(gsteps) != wsteps:
        problems.append(
            f"steps: expected {[(s['operation'], s['resource_id'], s['evidence_id']) for s in wsteps]}, "
            f"got {[(s['operation'], s['resource_id'], s['evidence_id']) for s in gsteps]}"
        )
    if [s["step_no"] for s in gsteps] != list(range(1, len(gsteps) + 1)):
        problems.append("step_no not consecutive from 1")
    return problems


def run_cases(cases, check_real=True):
    sys.path.insert(0, str(ROOT / "code"))
    from ghostaudit import intent as intent_mod
    from ghostaudit import llm_intent
    from ghostaudit.engine import Engine

    base = None
    if check_real:
        with Overlay(DATA) as ov0:
            base = ov0.run()
    with Overlay(DATA) as ov:
        apply(ov, cases)
        out = ov.run()
        clf = llm_intent.IntentClassifier(client=llm_intent.default_client())
        eng = Engine.from_dataset(ov.root, classify=clf.classify)
        reqs = {q["case_id"]: q for c in cases for q in c["requests"]}
        results = []
        for c in cases:
            for cid, want in sorted(c["expect"].items()):
                problems = _compare(cid, out.get(cid), want)
                needed = c.get("log", {}).get(cid, [])
                if needed:
                    a = eng.assess(reqs[cid], clf.classify(reqs[cid]["request_text"]))
                    for frag in needed:
                        if not any(frag in line for line in a.log):
                            problems.append(f"log: no line containing {frag!r} (log: {a.log})")
                results.append(CaseResult(cid, c["title"], not problems, problems))
    real_changed = (
        []
        if base is None
        else [x for x in changed(base, {k: v for k, v in out.items() if k in base}) if x in base]
    )
    return Report(results, real_changed)


def run():
    from evaluation.fixtures.custom_cases import CASES

    rep = run_cases(CASES)
    print(
        f"CUSTOM CASES ({len(rep.results)} rows from {len(CASES)} fixtures; synthetic people and evidence, dated 2027)"
    )
    for r in rep.results:
        print(f"  {'PASS' if r.ok else 'FAIL'}  {r.case_id:10} {r.title}")
        for p in r.problems:
            print(f"        {p}")
    print(f"  real rows changed by the additions: {rep.real_rows_changed or 'none'}")
    ok = sum(r.ok for r in rep.results)
    print(f"CUSTOM: {ok}/{len(rep.results)} pass")
    return 0 if ok == len(rep.results) and not rep.real_rows_changed else 1
