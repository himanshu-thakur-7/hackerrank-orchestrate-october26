"""--explain: every observation, link, rule and decision behind one case's row (docs/03_DESIGN.md
§6)."""

import json


def render(engine, request, intent):
    a = engine.assess(request, intent)
    view = engine.store.as_of(request["audit_at"])
    out = [
        f"CASE {a.case_id}  email={request['email']}  audit_at={request['audit_at']}  "
        f"reported={request['reported_status']}",
        f"  request_text: {request['request_text'][:160]}",
        f"  intent: {intent.label} ({intent.source}: {intent.reason})",
    ]
    if a.subject:
        s = a.subject
        out.append(
            f"  subject: {s.user_id}  emails={sorted(s.emails)}  hashes={len(s.email_hashes)}  "
            f"phones={sorted(s.phones)}"
        )
    out.append(
        f"  visible files at audit_at: {len(view.files())} of {len(engine.store.files)}; "
        f"pending loaders: {len(engine.notes)} file(s) "
        f"({', '.join(n.split('(')[1].split(',')[0] for n in engine.notes[:15])})"
    )
    for r in a.resources:
        out.append(f"  RESOURCE {r.system_id}/{r.resource_id}  (grounding {r.grounding})")
        for o in r.links:
            hit = [t for t in o.identifiers if a.subject.matches(t)]
            out.append(f"    link   {o.file_id} {o.locator} (observed {o.observed_at}) via {hit}")
        for o in view.observations(r.resource_id):
            if o.system_id == r.system_id:
                out.append(
                    f"    obs    {o.file_id} {o.locator} {o.observed_at} {o.state:10} "
                    f"table={o.table} pii={list(o.pii_fields)} "
                    f"cat={o.category} attrs={dict(o.attrs)}"
                )
        for e in view.activity(r.resource_id):
            out.append(
                f"    claim  {e.activity_id} {e.event_time} {e.event_type} -> {e.target_system} "
                f"{e.reported_result} (claim only)"
            )
        st = r.state
        seen = (
            f"{st.state} by {st.basis} {st.file_id} {st.locator} at {st.at}" if st else "UNPROVEN"
        )
        out.append(
            f"    state  {seen}"
            + (
                f"; later omissions {list(r.later_omissions)} (ADR 0014)"
                if r.later_omissions
                else ""
            )
        )
        t = r.treatment
        out.append(
            f"    policy category={r.category} [{r.category_source}] rule={t.rule_id} "
            f"action={t.action} -> {t.kind}: {t.reason}"
        )
        for s in a.steps:
            if (s["system_id"], s["resource_id"]) == (r.system_id, r.resource_id):
                ev = s["evidence_id"] or '""'
                out.append(
                    f"    step   {s['step_no']:2} {s['phase']:12} {s['operation']:26} "
                    f"{s['state']:10} evidence={ev}"
                )
    for line in a.log:
        out.append(f"  log: {line}")
    out.append(f"  ROW {a.case_id},{a.status},{json.dumps(a.steps, separators=(',', ':'))[:300]}")
    return "\n".join(out)
