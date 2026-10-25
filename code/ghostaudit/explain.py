"""--explain: every observation, link, rule and decision behind one case's row (docs/03_DESIGN.md
§6).

Decisions: ADR 0002 (the trace shows only the as_of(audit_at) view), ADR 0004 and
0006 (unresolved links and unproven states are printed, not hidden)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from ghostaudit.data import Request
    from ghostaudit.engine import CaseAssessment, Engine, ResourceAssessment
    from ghostaudit.identity import Identity
    from ghostaudit.intent import Intent
    from ghostaudit.store import CaseView


def _header(
    engine: Engine, a: CaseAssessment, request: Request, intent: Intent, view: CaseView
) -> list[str]:
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
    pending = ", ".join(n.split("(")[1].split(",")[0] for n in engine.notes[:15])
    out.append(
        f"  visible files at audit_at: {len(view.files())} of {len(engine.store.files)}; "
        f"pending loaders: {len(engine.notes)} file(s) ({pending})"
    )
    return out


def _evidence_lines(a: CaseAssessment, r: ResourceAssessment, view: CaseView) -> list[str]:
    """The links, observations and claims behind one resource."""
    out = []
    for o in r.links:
        hit = [t for t in o.identifiers if cast("Identity", a.subject).matches(t)]
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
    return out


def _decision_lines(a: CaseAssessment, r: ResourceAssessment) -> list[str]:
    """The reconstructed state, the policy decision and the steps for one resource."""
    st = r.state
    seen = f"{st.state} by {st.basis} {st.file_id} {st.locator} at {st.at}" if st else "UNPROVEN"
    later = f"; later omissions {list(r.later_omissions)} (ADR 0014)" if r.later_omissions else ""
    t = r.treatment
    out = [
        f"    state  {seen}{later}",
        f"    policy category={r.category} [{r.category_source}] rule={t.rule_id} "
        f"action={t.action} -> {t.kind}: {t.reason}",
    ]
    for s in a.steps:
        if (s["system_id"], s["resource_id"]) == (r.system_id, r.resource_id):
            ev = s["evidence_id"] or '""'
            out.append(
                f"    step   {s['step_no']:2} {s['phase']:12} {s['operation']:26} "
                f"{s['state']:10} evidence={ev}"
            )
    return out


def render(engine: Engine, request: Request, intent: Intent) -> str:
    """The full trace behind one row: subject, every resource's evidence and decision, the log
    and the row itself."""
    a = engine.assess(request, intent)
    view = engine.store.as_of(request["audit_at"])
    out = _header(engine, a, request, intent, view)
    for r in a.resources:
        out.append(f"  RESOURCE {r.system_id}/{r.resource_id}  (grounding {r.grounding})")
        out += _evidence_lines(a, r, view)
        out += _decision_lines(a, r)
    out += [f"  log: {line}" for line in a.log]
    out.append(f"  ROW {a.case_id},{a.status},{json.dumps(a.steps, separators=(',', ':'))[:300]}")
    return "\n".join(out)
