"""Case engine (docs/03_DESIGN.md §3). Interface:

  Engine.from_dataset(data_dir) -> Engine
  engine.assess(request, intent) -> CaseAssessment    (everything behind the row, for --explain)
  engine.audit(request, intent)  -> (case_id, status, steps)

Stages: intent (given) -> identity -> discovery (resources whose visible record units carry an exact
identifier of the subject: SAME_RECORD / TRACE_JOIN) -> state at audit_at (CaseView.state, ADR 0002,
0014) -> policy (category + treatment) -> verdict + steps (T09). Linking beyond discovery is T10:
anything that would need it is logged, never guessed (ADR 0004).
"""
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ghostaudit import identity, loaders, policy
from ghostaudit.store import ActivityEvent, EvidenceFile, EvidenceStore, StateResult


@dataclass
class ResourceAssessment:
    system_id: str
    resource_id: str
    links: list                       # visible observations naming the subject (the grounded link)
    state: Optional[StateResult]
    category: Optional[str]
    category_source: str
    treatment: policy.Treatment
    later_omissions: tuple = ()       # covering files after the deciding sighting that omit it (ADR 0014 risk)


@dataclass
class CaseAssessment:
    case_id: str
    status: str
    steps: list
    subject: Optional[identity.Identity] = None
    resources: list = field(default_factory=list)
    log: list = field(default_factory=list)


def load_activity(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [ActivityEvent(r["activity_id"], r["event_time"], r["event_type"], r["source_system"], r["target_system"],
                              r["resource_id"], r["reported_result"]) for r in csv.DictReader(f)]


class Engine:
    def __init__(self, store, resolver, rules, notes=()):
        self.store, self.resolver, self.rules = store, resolver, rules
        self.notes = list(notes)      # run-level notes (e.g. evidence formats whose loader is pending)

    @classmethod
    def from_dataset(cls, data_dir, resolver=None):
        d = Path(data_dir)
        with open(d / "evidence_files.csv", newline="", encoding="utf-8") as f:
            manifest = list(csv.DictReader(f))
        files, obs, cov, notes = [], [], [], []
        for row in manifest:
            r = loaders.load_bytes(row["file_id"], row["captured_at"], (d / row["file_path"]).read_bytes(), strict=False)
            if r.signature not in loaders.LOADERS:
                notes.append(f"PENDING_LOADER({row['file_id']}, {r.signature}, {loaders.PENDING.get(r.signature, '?')})")
            files.append(EvidenceFile(row["file_id"], row["file_path"], row["origin"], row["captured_at"]))
            obs += r.observations
            cov += r.coverage
        store = EvidenceStore(files=files, observations=obs, coverage=cov, activity=load_activity(d / "system_activity.csv"))
        return cls(store, resolver or identity.Resolver.from_dataset(d), policy.Rules.from_csv(d / "deletion_rules.csv"), notes)

    def assess(self, request, intent):
        case_id = request["case_id"]
        if intent.label != "DELETION":
            return CaseAssessment(case_id, "NOT_APPLICABLE", [], log=[f"INTENT {intent.label}: {intent.reason}"])
        subject = self.resolver.resolve(request["email"])
        if subject is None:
            return CaseAssessment(case_id, "INCOMPLETE", [], log=["UNRESOLVED_SUBJECT"])
        view = self.store.as_of(request["audit_at"])
        a = CaseAssessment(case_id, "INCOMPLETE", [], subject)
        for (system_id, resource_id), links in sorted(view.linking_observations(subject.tokens()).items()):
            a.resources.append(self._resource(view, system_id, resource_id, links))
        if not any(r.system_id == "account_service" for r in a.resources):
            a.log.append("UNRESOLVED_LINK(primary account: no grounded link yet, T10)")
        for r in a.resources:
            if r.treatment.kind == "none":
                a.log.append(f"NO_STEP({r.system_id}/{r.resource_id}: {r.treatment.reason})")
        return a

    def _resource(self, view, system_id, resource_id, links):
        observations = [o for o in view.observations(resource_id) if o.system_id == system_id]
        activity = [e for e in view.activity(resource_id) if e.target_system == system_id]
        category, source = policy.categorize(system_id, observations, activity)
        state = view.state(system_id, resource_id)
        later = view.later_omissions(system_id, resource_id, state.at) if state and state.basis == "observation" and state.state != "ABSENT" else ()
        return ResourceAssessment(system_id, resource_id, links, state, category, source,
                                  policy.treat(category, state, self.rules), later)

    def audit(self, request, intent):
        a = self.assess(request, intent)
        return a.case_id, a.status, a.steps


def audit(request, resolver, intent_result):
    """T02 placeholder kept for code/main.py until the T09 planner lands: every case NOT_APPLICABLE."""
    return request["case_id"], "NOT_APPLICABLE", []
