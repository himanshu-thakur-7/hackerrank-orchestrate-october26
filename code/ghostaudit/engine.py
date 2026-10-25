"""Case engine (docs/03_DESIGN.md §3). Interface:

  Engine.from_dataset(data_dir) -> Engine
  engine.assess(request, intent) -> CaseAssessment    (everything behind the row, for --explain)
  engine.audit(request, intent)  -> (case_id, status, steps)

Stages: intent (given) -> identity -> discovery (resources whose visible record units carry an exact
identifier of the subject: SAME_RECORD / TRACE_JOIN) -> state at audit_at (CaseView.state, ADR 0002,
0014) -> policy (category + treatment) -> verdict + steps (T09). Linking beyond discovery is T10:
anything that would need it is logged, never guessed (ADR 0004).
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ghostaudit import contract, data, identity, linking, loaders, policy
from ghostaudit import intent as intent_mod
from ghostaudit.loaders.common import system_of
from ghostaudit.store import ActivityEvent, EvidenceFile, EvidenceStore, StateResult

if TYPE_CHECKING:
    from ghostaudit.contract import Step
    from ghostaudit.data import Request
    from ghostaudit.store import CaseView, Observation

# (system_id, resource_id) -> (observations that link it to the subject, grounding)
Found = dict[tuple[str, str], tuple[list["Observation"], str]]


@dataclass
class ResourceAssessment:
    system_id: str
    resource_id: str
    links: list[Observation]  # visible observations naming the subject (the grounded link)
    state: StateResult | None
    category: str | None
    category_source: str
    treatment: policy.Treatment
    # covering files after the deciding sighting that omit it (ADR 0014 risk)
    later_omissions: tuple[str, ...] = ()
    # IDENTIFIER (same record / trace join) | SOURCE_REF | CATALOG | ACTIVITY_ACCOUNT
    grounding: str = "IDENTIFIER"
    evidence: str = ""  # file to cite for the state (CaseView.citation)


@dataclass
class CaseAssessment:
    case_id: str
    status: str
    steps: list[Step]
    subject: identity.Identity | None = None
    resources: list[ResourceAssessment] = field(default_factory=list)
    log: list[str] = field(default_factory=list)


def load_activity(path: str | Path) -> list[ActivityEvent]:
    with open(path, newline="", encoding="utf-8") as f:
        return [
            ActivityEvent(
                r["activity_id"],
                r["event_time"],
                r["event_type"],
                r["source_system"],
                r["target_system"],
                r["resource_id"],
                r["reported_result"],
                r["details"],
            )
            for r in csv.DictReader(f)
        ]


def _incomplete_plan(
    violations: list[ResourceAssessment], planned: list[ResourceAssessment]
) -> list[Step]:
    """Findings (cited) and remediation for each violation, then a future, uncited check for
    every planned resource, unproven ones included (ADR 0006 §1)."""
    steps = []
    for r in violations:
        t = r.treatment  # a violation always carries all three operations
        steps.append(contract.step(cast("str", t.finding), r.system_id, r.resource_id, r.evidence))
        steps.append(contract.step(cast("str", t.remediation), r.system_id, r.resource_id))
    for r in planned:
        steps.append(
            contract.step(cast("str", r.treatment.verification), r.system_id, r.resource_id)
        )
    return contract.ordered(steps)


def _complete_plan(a: CaseAssessment, planned: list[ResourceAssessment]) -> list[Step]:
    """Cited verifications only. An unproven resource cannot be cited, so it is omitted and
    logged (ADR 0006 edge case)."""
    steps = []
    for r in planned:
        if r.treatment.kind == "unproven":
            a.log.append(f"UNPROVEN({r.system_id}/{r.resource_id})")
            continue
        steps.append(
            contract.step(
                cast("str", r.treatment.verification), r.system_id, r.resource_id, r.evidence
            )
        )
    return contract.ordered(steps) if steps else []


def _drop_stale_links(a: CaseAssessment, request: Request, found: Found) -> None:
    """ADR 0016: a resource whose every link predates requested_at and shows it absent belongs to
    an earlier lifecycle of the id, not to this request."""
    for key, (links, _) in sorted(found.items()):
        if links and all(
            o.observed_at < request["requested_at"] and o.state == "ABSENT" for o in links
        ):
            last = links[-1]
            del found[key]
            a.log.append(
                f"STALE_LINK({key[0]}/{key[1]}: every link predates requested_at and shows it "
                f"absent; latest {last.file_id} {last.locator} at {last.observed_at}; ADR 0016)"
            )


def _add_source_refs(a: CaseAssessment, found: Found) -> None:
    """A record naming its source (source_resource_id) brings that source into scope."""
    for (_system_id, resource_id), (links, _) in sorted(found.items()):
        for o in links:
            src = dict(o.attrs).get("source_resource_id")
            if src and (owner := system_of(src)) and (owner, src) not in found:
                found[(owner, src)] = ([], "SOURCE_REF")
                a.log.append(f"SOURCE_REF({src} from {resource_id} {o.file_id} {o.locator})")


def _apply_catalog_link(a: CaseAssessment, c: linking.CatalogLink, found: Found) -> None:
    """A confirmed catalog claim links the resource; a contradicted one removes it (ADR 0005); an
    unconfirmed one is only logged."""
    key = (c.system_id, c.resource_id)
    if c.status == "CONFIRMED":
        found.setdefault(key, ([], "CATALOG"))
    elif c.status == "CONTRADICTED":
        found.pop(key, None)
        a.log.append(f"REJECTED_LINK({c.activity_id} {c.resource_id}: {c.reason}; ADR 0005)")
    else:
        a.log.append(
            f"UNRESOLVED_LINK({c.activity_id} {c.resource_id}: catalog claim not confirmed, "
            f"{c.reason})"
        )


class Engine:
    def __init__(
        self,
        store: EvidenceStore,
        resolver: identity.Resolver,
        rules: policy.Rules,
        notes: Sequence[str] = (),
        linker: linking.Linker | None = None,
    ) -> None:
        self.store, self.resolver, self.rules, self.linker = store, resolver, rules, linker
        self.notes = list(notes)  # run-level notes (e.g. evidence formats whose loader is pending)

    @classmethod
    def from_dataset(
        cls,
        data_dir: str | Path,
        resolver: identity.Resolver | None = None,
        classify: Callable[[str], intent_mod.Intent] | None = None,
    ) -> Engine:
        d = Path(data_dir)
        with open(d / "evidence_files.csv", newline="", encoding="utf-8") as f:
            manifest = list(csv.DictReader(f))
        files, obs, cov, notes = [], [], [], []
        for row in manifest:
            r = loaders.load_bytes(
                row["file_id"], row["captured_at"], (d / row["file_path"]).read_bytes(), strict=True
            )
            if r.signature not in loaders.LOADERS:
                notes.append(
                    f"PENDING_LOADER({row['file_id']}, {r.signature}, "
                    f"{loaders.PENDING.get(r.signature, '?')})"
                )
            files.append(
                EvidenceFile(row["file_id"], row["file_path"], row["origin"], row["captured_at"])
            )
            obs += r.observations
            cov += r.coverage
        store = EvidenceStore(
            files=files,
            observations=obs,
            coverage=cov,
            activity=load_activity(d / "system_activity.csv"),
        )
        resolver = resolver or identity.Resolver.from_dataset(d)
        # global one-to-one account assignment runs over every request file in the dataset (ADR
        # 0003)
        requests = [
            q
            for f in ("sample_deletion_requests.csv", "deletion_requests.csv")
            if (d / f).exists()
            for q in data.load_requests(d / f)
        ]
        classify = (
            classify or intent_mod.classify_rules
        )  # the same intent the run uses (rules, or rules + model)
        intents = {q["case_id"]: classify(q["request_text"]) for q in requests}
        lk = linking.Linker(store, resolver, requests, intents)
        return cls(store, resolver, policy.Rules.from_csv(d / "deletion_rules.csv"), notes, lk)

    def assess(self, request: Request, intent: intent_mod.Intent) -> CaseAssessment:
        case_id = request["case_id"]
        if intent.label != "DELETION":
            return CaseAssessment(
                case_id, "NOT_APPLICABLE", [], log=[f"INTENT {intent.label}: {intent.reason}"]
            )
        subject = self.resolver.resolve(request["email"])
        if subject is None:
            return CaseAssessment(case_id, "INCOMPLETE", [], log=["UNRESOLVED_SUBJECT"])
        view = self.store.as_of(request["audit_at"])
        a = CaseAssessment(case_id, "INCOMPLETE", [], subject)
        found = {
            k: (links, "IDENTIFIER")
            for k, links in view.linking_observations(subject.tokens()).items()
        }
        self._link(a, view, subject, request, found)
        for (system_id, resource_id), (links, grounding) in sorted(found.items()):
            a.resources.append(self._resource(view, system_id, resource_id, links, grounding))
        for r in a.resources:
            if r.treatment.kind == "none":
                a.log.append(f"NO_STEP({r.system_id}/{r.resource_id}: {r.treatment.reason})")
        a.status, a.steps = self._plan(a)
        return a

    def _plan(self, a: CaseAssessment) -> tuple[str, list[Step]]:
        """Verdict (ADR 0006) + steps. INCOMPLETE iff any grounded violation; COMPLETE cites
        every step."""
        planned = [r for r in a.resources if r.treatment.kind != "none"]
        violations = [r for r in planned if r.treatment.kind == "violation"]
        if violations:
            return "INCOMPLETE", _incomplete_plan(violations, planned)
        steps = _complete_plan(a, planned)
        if not steps:
            a.log.append("NO_GROUNDED_STEP")
            return "INCOMPLETE", []
        return "COMPLETE", steps

    def _link(
        self,
        a: CaseAssessment,
        view: CaseView,
        subject: identity.Identity,
        request: Request,
        found: Found,
    ) -> None:
        """Stage 4 (T10): stale links out, source references, catalog claims checked against
        artifacts, the activity account."""
        _drop_stale_links(a, request, found)
        _add_source_refs(a, found)
        if self.linker is None:
            return
        for c in self.linker.catalog(view, subject):
            _apply_catalog_link(a, c, found)
        acc = self.linker.account(request["case_id"])
        if acc.status == "LINKED":
            account = cast("str", acc.resource_id)  # set whenever the status is LINKED
            found.setdefault(("account_service", account), ([], "ACTIVITY_ACCOUNT"))
        a.log.append(acc.describe())

    def _resource(
        self,
        view: CaseView,
        system_id: str,
        resource_id: str,
        links: list[Observation],
        grounding: str = "IDENTIFIER",
    ) -> ResourceAssessment:
        observations = [o for o in view.observations(resource_id) if o.system_id == system_id]
        activity = [e for e in view.activity(resource_id) if e.target_system == system_id]
        category, source = policy.categorize(system_id, observations, activity)
        state = view.state(system_id, resource_id)
        later = (
            view.later_omissions(system_id, resource_id, state.at)
            if state and state.basis == "observation" and state.state != "ABSENT"
            else ()
        )
        return ResourceAssessment(
            system_id,
            resource_id,
            links,
            state,
            category,
            source,
            policy.treat(category, state, self.rules),
            later,
            grounding,
            view.citation(system_id, resource_id, state) if state else "",
        )

    def audit(self, request: Request, intent: intent_mod.Intent) -> tuple[str, str, list[Step]]:
        a = self.assess(request, intent)
        return a.case_id, a.status, a.steps
