"""Evidence Store (docs/03_DESIGN.md §1-2).

Interface: EvidenceStore(...).as_of(cutoff) -> CaseView. The engine only ever sees a CaseView, so
evidence captured after audit_at cannot leak in (ADR 0002: file-level, inclusive cutoff).

State comes only from evidence (Observation, Coverage). ActivityEvent rows are claims: they are
exposed for linkage and category hints, never used to set a state (ADR 0003, 0006).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

# (observed_at, capture time, file_id, result): ordered by the first three, latest wins
Event = tuple[str, str | None, str, "StateResult"]
ABSENT = "ABSENT"


def token_key(t: str) -> str:
    """Index key for an identifier: phones by digits ('tel:<digits>'), everything else
    lowercased."""
    t = str(t).strip()
    digits = re.sub(r"\D", "", t)
    if len(digits) >= 9 and not re.search(r"[A-Za-z@]", t):
        return "tel:" + digits
    return t.lower()


def _time_order(o: Observation) -> tuple[str, str, str]:
    """Observation sort key: time, then file, then position in the file (a total, stable order)."""
    return (o.observed_at, o.file_id, o.locator)


def _file_event(fid: str, obs: list[Observation], captured_at: str | None) -> Event:
    """(time, capture time, file, StateResult) for one file's latest observations of a resource.
    At the same snapshot instant, presence in any table (e.g. a replica) beats absence elsewhere."""
    last_t = max(o.observed_at for o in obs)
    latest = [o for o in obs if o.observed_at == last_t]
    pick = next((o for o in latest if o.state != ABSENT), latest[-1])
    result = StateResult(pick.state, fid, "observation", pick.observed_at, pick.locator, pick)
    return (pick.observed_at, captured_at, fid, result)


@dataclass(frozen=True)
class EvidenceFile:
    file_id: str
    file_path: str
    origin: str
    captured_at: str


@dataclass(frozen=True)
class Observation:
    file_id: str
    observed_at: str  # record time if the file has one, else the file's captured_at
    system_id: str
    resource_id: str
    table: str  # e.g. customer_profiles_failover_replica; distinguishes replicas
    state: str  # PRESENT | ABSENT | ACTIVE | DISABLED | BLOCKED | RESTORABLE ...
    category: str | None = None  # explicit tag only (SUPPORT_MESSAGE, ...)
    pii_fields: tuple[str, ...] = ()  # direct identifiers still non-null on the record
    identifiers: tuple[str, ...] = ()  # exact identifiers seen in the record unit
    locator: str = ""  # line / json path, for --explain
    attrs: tuple[
        tuple[str, str], ...
    ] = ()  # other (key, value) fields of the record, e.g. ("status_code", "404")


@dataclass(frozen=True)
class Coverage:
    """The snapshot lists every row of `table`; a resource of `system_id` it does not list is
    ABSENT."""

    file_id: str
    captured_at: str
    system_id: str
    table: str


@dataclass(frozen=True)
class Link:
    resource_id: str
    user_id: str
    grounding: str  # SAME_RECORD | TRACE_JOIN | UNIQUE_ACTIVITY_CANDIDATE | CATALOG_CLAIM
    source_id: str  # file_id or activity_id
    at: str
    status: str = "OK"  # OK | CONTRADICTED | UNCONFIRMED


@dataclass(frozen=True)
class ActivityEvent:
    activity_id: str
    event_time: str
    event_type: str
    source_system: str
    target_system: str
    resource_id: str
    reported_result: str  # a claim, never state
    details: str = ""  # free text; for LINK_RESOURCE_IDENTITY it names the claimed person


@dataclass(frozen=True)
class StateResult:
    state: str
    file_id: str
    basis: str  # "observation" | "coverage"
    at: str
    locator: str = ""
    observation: Observation | None = None


class EvidenceStore:
    def __init__(
        self,
        files: Iterable[EvidenceFile] = (),
        observations: Iterable[Observation] = (),
        coverage: Iterable[Coverage] = (),
        links: Iterable[Link] = (),
        activity: Iterable[ActivityEvent] = (),
    ) -> None:
        self.files = {f.file_id: f for f in files}
        self.observations = list(observations)
        self.coverage = list(coverage)
        self.links = list(links)
        self.activity_events = sorted(activity, key=lambda a: (a.event_time, a.activity_id))
        self._by_resource = defaultdict(list)
        self._by_identifier = defaultdict(set)
        for o in self.observations:
            self._by_resource[o.resource_id].append(o)
            for t in o.identifiers:
                self._by_identifier[token_key(t)].add(o)
        self._coverage_by_system = defaultdict(list)
        for c in self.coverage:
            self._coverage_by_system[c.system_id].append(c)

    def captured_at(self, file_id: str) -> str | None:
        f = self.files.get(file_id)
        return f.captured_at if f else None

    def as_of(self, cutoff: str) -> CaseView:
        return CaseView(self, cutoff)


class CaseView:
    """Everything visible at `cutoff` (inclusive). Files captured later do not exist here."""

    def __init__(self, store: EvidenceStore, cutoff: str) -> None:
        self._s = store
        self.cutoff = cutoff

    def _visible(self, file_id: str) -> bool:
        cap = self._s.captured_at(file_id)
        return cap is not None and cap <= self.cutoff

    def files(self) -> list[EvidenceFile]:
        return sorted(
            (f for f in self._s.files.values() if f.captured_at <= self.cutoff),
            key=lambda f: (f.captured_at, f.file_id),
        )

    def observations(self, resource_id: str) -> list[Observation]:
        obs = [o for o in self._s._by_resource.get(resource_id, ()) if self._visible(o.file_id)]
        return sorted(
            obs, key=lambda o: (o.observed_at, self._s.captured_at(o.file_id), o.file_id, o.locator)
        )

    def linking_observations(
        self, tokens: Iterable[str]
    ) -> dict[tuple[str, str], list[Observation]]:
        """Visible observations whose identifiers contain any token exactly -> {(system_id,
        resource_id): [obs]}."""
        out = defaultdict(set)
        for t in tokens:
            for o in self._s._by_identifier.get(token_key(t), ()):
                if self._visible(o.file_id):
                    out[(o.system_id, o.resource_id)].add(o)
        return {k: sorted(v, key=_time_order) for k, v in out.items()}

    def resources_with_identifier(self, tokens: Iterable[str]) -> set[tuple[str, str]]:
        return set(self.linking_observations(tokens))

    def citation(self, system_id: str, resource_id: str, result: StateResult) -> str:
        """File to cite for `result` (docs/02 §4.3): the latest visible file that NAMES the resource
        with that
        state; a covering file only when absence is known by omission alone."""
        same = [
            o
            for o in self.observations(resource_id)
            if o.system_id == system_id and o.state == result.state
        ]
        return same[-1].file_id if same else result.file_id

    def later_omissions(self, system_id: str, resource_id: str, after: str) -> tuple[str, ...]:
        """Visible covering files captured after `after` that do not list the resource (ADR 0014
        risk)."""
        named = {o.file_id for o in self.observations(resource_id) if o.system_id == system_id}
        return tuple(
            sorted(
                {
                    c.file_id
                    for c in self._s._coverage_by_system.get(system_id, ())
                    if self._visible(c.file_id) and c.captured_at > after and c.file_id not in named
                }
            )
        )

    def state(self, system_id: str, resource_id: str) -> StateResult | None:
        """Latest evidence-backed state of a resource, or None when nothing visible proves
        anything (UNPROVEN). Explicit observations follow latest-wins; omission from a covering
        snapshot counts only when no visible observation shows the record present (ADR 0014)."""
        per_file = self._observations_per_file(system_id, resource_id)
        events = [_file_event(fid, obs, self._s.captured_at(fid)) for fid, obs in per_file.items()]
        seen_present = any(o.state != ABSENT for obs in per_file.values() for o in obs)
        if not seen_present:
            events += self._omission_events(system_id, per_file)
        if not events:
            return None
        return max(events, key=lambda e: e[:3])[3]

    def _observations_per_file(
        self, system_id: str, resource_id: str
    ) -> dict[str, list[Observation]]:
        per_file = defaultdict(list)
        for o in self.observations(resource_id):
            if o.system_id == system_id:
                per_file[o.file_id].append(o)
        return per_file

    def _omission_events(
        self, system_id: str, per_file: dict[str, list[Observation]]
    ) -> list[Event]:
        """ABSENT-by-omission events from visible covering snapshots that do not list the
        resource."""
        covering = {
            c.file_id: c
            for c in self._s._coverage_by_system.get(system_id, ())
            if self._visible(c.file_id)
        }
        return [
            (c.captured_at, c.captured_at, fid, StateResult(ABSENT, fid, "coverage", c.captured_at))
            for fid, c in covering.items()
            if fid not in per_file
        ]

    def activity(self, resource_id: str | None = None) -> list[ActivityEvent]:
        return [
            a
            for a in self._s.activity_events
            if a.event_time <= self.cutoff and (resource_id is None or a.resource_id == resource_id)
        ]

    def links_for_user(self, user_id: str) -> list[Link]:
        return [
            link
            for link in self._s.links
            if link.user_id == user_id and link.at <= self.cutoff and link.status != "CONTRADICTED"
        ]
