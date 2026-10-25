"""Evidence Store (docs/03_DESIGN.md §1-2).

Interface: EvidenceStore(...).as_of(cutoff) -> CaseView. The engine only ever sees a CaseView, so
evidence captured after audit_at cannot leak in (ADR 0002: file-level, inclusive cutoff).

State comes only from evidence (Observation, Coverage). ActivityEvent rows are claims: they are
exposed for linkage and category hints, never used to set a state (ADR 0003, 0006).
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

ABSENT = "ABSENT"


@dataclass(frozen=True)
class EvidenceFile:
    file_id: str
    file_path: str
    origin: str
    captured_at: str


@dataclass(frozen=True)
class Observation:
    file_id: str
    observed_at: str          # record time if the file has one, else the file's captured_at
    system_id: str
    resource_id: str
    table: str                # e.g. customer_profiles_failover_replica; distinguishes replicas
    state: str                # PRESENT | ABSENT | ACTIVE | DISABLED | BLOCKED | RESTORABLE ...
    category: Optional[str] = None      # explicit tag only (SUPPORT_MESSAGE, ...)
    pii_fields: tuple = ()              # direct identifiers still non-null on the record
    identifiers: tuple = ()             # exact identifiers seen in the record unit
    locator: str = ""                   # line / json path, for --explain
    attrs: tuple = ()                   # other (key, value) fields of the record, e.g. ("status_code", "404")


@dataclass(frozen=True)
class Coverage:
    """The snapshot lists every row of `table`; a resource of `system_id` it does not list is ABSENT."""
    file_id: str
    captured_at: str
    system_id: str
    table: str


@dataclass(frozen=True)
class Link:
    resource_id: str
    user_id: str
    grounding: str            # SAME_RECORD | TRACE_JOIN | UNIQUE_ACTIVITY_CANDIDATE | CATALOG_CLAIM
    source_id: str            # file_id or activity_id
    at: str
    status: str = "OK"        # OK | CONTRADICTED | UNCONFIRMED


@dataclass(frozen=True)
class ActivityEvent:
    activity_id: str
    event_time: str
    event_type: str
    source_system: str
    target_system: str
    resource_id: str
    reported_result: str      # a claim, never state


@dataclass(frozen=True)
class StateResult:
    state: str
    file_id: str
    basis: str                # "observation" | "coverage"
    at: str
    locator: str = ""
    observation: Optional[Observation] = None


class EvidenceStore:
    def __init__(self, files=(), observations=(), coverage=(), links=(), activity=()):
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
                self._by_identifier[str(t).strip().lower()].add(o)
        self._coverage_by_system = defaultdict(list)
        for c in self.coverage:
            self._coverage_by_system[c.system_id].append(c)

    def captured_at(self, file_id):
        f = self.files.get(file_id)
        return f.captured_at if f else None

    def as_of(self, cutoff):
        return CaseView(self, cutoff)


class CaseView:
    """Everything visible at `cutoff` (inclusive). Files captured later do not exist here."""

    def __init__(self, store, cutoff):
        self._s = store
        self.cutoff = cutoff

    def _visible(self, file_id):
        cap = self._s.captured_at(file_id)
        return cap is not None and cap <= self.cutoff

    def files(self):
        return sorted((f for f in self._s.files.values() if f.captured_at <= self.cutoff), key=lambda f: (f.captured_at, f.file_id))

    def observations(self, resource_id):
        obs = [o for o in self._s._by_resource.get(resource_id, ()) if self._visible(o.file_id)]
        return sorted(obs, key=lambda o: (o.observed_at, self._s.captured_at(o.file_id), o.file_id, o.locator))

    def resources_with_identifier(self, tokens):
        out = set()
        for t in tokens:
            for o in self._s._by_identifier.get(str(t).strip().lower(), ()):
                if self._visible(o.file_id):
                    out.add((o.system_id, o.resource_id))
        return out

    def state(self, system_id, resource_id):
        """Latest evidence-backed state of a resource, or None when nothing visible proves anything (UNPROVEN)."""
        per_file = defaultdict(list)
        for o in self.observations(resource_id):
            if o.system_id == system_id:
                per_file[o.file_id].append(o)
        events = []
        for fid, obs in per_file.items():
            last_t = max(o.observed_at for o in obs)
            latest = [o for o in obs if o.observed_at == last_t]
            # same snapshot instant: presence in any table (e.g. a replica) beats absence elsewhere
            pick = next((o for o in latest if o.state != ABSENT), latest[-1])
            events.append((pick.observed_at, self._s.captured_at(fid), fid,
                           StateResult(pick.state, fid, "observation", pick.observed_at, pick.locator, pick)))
        # ADR 0014: omission is weak evidence; it only counts when no visible observation shows presence
        seen_present = any(o.state != ABSENT for obs in per_file.values() for o in obs)
        if not seen_present:
            covering = {c.file_id: c for c in self._s._coverage_by_system.get(system_id, ()) if self._visible(c.file_id)}
            for fid, c in covering.items():
                if fid not in per_file:
                    events.append((c.captured_at, c.captured_at, fid, StateResult(ABSENT, fid, "coverage", c.captured_at)))
        if not events:
            return None
        return max(events, key=lambda e: e[:3])[3]

    def activity(self, resource_id=None):
        return [a for a in self._s.activity_events
                if a.event_time <= self.cutoff and (resource_id is None or a.resource_id == resource_id)]

    def links_for_user(self, user_id):
        return [l for l in self._s.links
                if l.user_id == user_id and l.at <= self.cutoff and l.status != "CONTRADICTED"]
