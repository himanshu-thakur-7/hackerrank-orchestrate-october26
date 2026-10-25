"""Linking beyond the subject's own identifiers (docs/03_DESIGN.md §3 Stage 4; ADR 0003, 0004, 0005).

  Linker(store, resolver, requests, intents)
    .account(case_id)        -> AccountLink   primary account from activity, unique survivor only
    .distribution()          -> {candidate count: deletion requests}, after all filters
    .catalog(view, subject)  -> [CatalogLink] LINK_RESOURCE_IDENTITY claims checked against their artifact

Account candidates are DELETE_RECORD -> account_service activity rows (claims used only as a linkage
key, never as state) that pass, in order:
  1. the window: event_time in [reported_at - 1.5 h, reported_at - 0.5 h] (ACCOUNT_DELETE_WINDOW_HOURS),
     and at or before audit_at;
  2. reported_result agrees with reported_status (RESULT_OF);
  3. the pre-audit identity filter: drop a candidate that visible evidence ties to another person; if
     visible evidence ties one to this subject, keep only those;
  4. global one-to-one elimination over every deletion request (samples + evaluation): a request left
     with one candidate claims it, and it is removed from every other request, until nothing changes.
Only a unique survivor is linked. Anything else is logged with its reason and candidate set; there is
no tie-break (ADR 0004), in particular never by case_id order. The distance to reported_at is reported
for each candidate, but it is not used to choose.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from ghostaudit.loaders.common import EMAIL_IN_TEXT

ACCOUNT_DELETE_WINDOW_HOURS = (
    0.5,
    1.5,
)  # the primary-account delete lands this long before reported_at (docs/03 §1)
RESULT_OF = {"COMPLETE": "SUCCESS", "PARTIALLY_COMPLETE": "PARTIAL", "NOT_STARTED": "FAILED"}
_T = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Candidate:
    activity_id: str
    resource_id: str
    event_time: str
    hours_before_report: float
    result: str


@dataclass
class AccountLink:
    case_id: str
    status: str  # LINKED | TIED | NO_CANDIDATE | NOT_A_DELETION
    resource_id: Optional[str] = None
    activity_id: Optional[str] = None
    candidates: tuple = ()  # after window + result
    survivors: tuple = ()  # after identity filter + global elimination
    reason: str = ""
    filtered: list = field(default_factory=list)  # (resource_id, why dropped)

    def describe(self):
        if self.status == "LINKED":
            c = next(c for c in self.survivors if c.resource_id == self.resource_id)
            return f"LINKED_ACCOUNT({self.resource_id} via {self.activity_id}, {c.hours_before_report:.2f} h before reported_at)"
        cands = ", ".join(f"{c.resource_id}/{c.activity_id}" for c in self.survivors) or "none"
        return f"UNRESOLVED_LINK(primary account: {self.reason}; candidates [{cands}])"


@dataclass(frozen=True)
class CatalogLink:
    activity_id: str
    system_id: str
    resource_id: str
    status: str  # CONFIRMED | CONTRADICTED | UNCONFIRMED
    artifact: str = ""  # file_id checked
    reason: str = ""


class Linker:
    def __init__(self, store, resolver, requests, intents):
        self.store, self.resolver = store, resolver
        self.requests = {q["case_id"]: q for q in requests}
        self.intents = intents
        self._accounts = None
        self._deletes = [
            a
            for a in store.activity_events
            if a.event_type == "DELETE_RECORD" and a.target_system == "account_service"
        ]
        self._catalog = [
            a for a in store.activity_events if a.event_type == "LINK_RESOURCE_IDENTITY"
        ]

    # ---- primary account -------------------------------------------------------------------
    def _candidates(self, q):
        rep = _T(q["reported_at"])
        lo, hi = ACCOUNT_DELETE_WINDOW_HOURS
        want = RESULT_OF.get(q["reported_status"])
        out = []
        for a in self._deletes:
            t = _T(a.event_time)
            if (
                rep - timedelta(hours=hi) <= t <= rep - timedelta(hours=lo)
                and a.event_time <= q["audit_at"]
                and a.reported_result == want
            ):
                out.append(
                    Candidate(
                        a.activity_id,
                        a.resource_id,
                        a.event_time,
                        round((rep - t).total_seconds() / 3600, 2),
                        a.reported_result,
                    )
                )
        return out

    def _owners(self, view, resource_id):
        owners = set()
        for o in view.observations(resource_id):
            if o.system_id == "account_service":
                owners |= {self.resolver.owner_of(t) for t in o.identifiers} - {None}
        for c in self.catalog(view, None):
            if c.resource_id == resource_id and c.status == "CONFIRMED":
                owners |= set(c.reason.split("owner=")[1:2])
        return owners

    def _compute(self):
        links, live = {}, {}
        for cid in sorted(self.requests, key=lambda c: (len(c), c)):
            q = self.requests[cid]
            intent = self.intents.get(cid)
            subject = self.resolver.resolve(q["email"])
            if intent is None or intent.label != "DELETION" or subject is None:
                links[cid] = AccountLink(
                    cid, "NOT_A_DELETION", reason="not a resolvable deletion request"
                )
                continue
            cands = self._candidates(q)
            link = AccountLink(cid, "TIED", candidates=tuple(cands))
            view = self.store.as_of(q["audit_at"])
            mine, other = [], []
            for c in cands:
                owners = self._owners(view, c.resource_id)
                if subject.user_id in owners:
                    mine.append(c)
                elif owners:
                    other.append(c)
                    link.filtered.append(
                        (
                            c.resource_id,
                            f"pre-audit evidence ties it to {', '.join(sorted(owners))}",
                        )
                    )
            keep = mine or [c for c in cands if c not in other]
            links[cid], live[cid] = link, {c.activity_id: c for c in keep}
        changed = True
        while changed:  # global one-to-one elimination
            changed = False
            singles = Counter(next(iter(cs)) for cs in live.values() if len(cs) == 1)
            for cid, cs in live.items():
                if len(cs) != 1 or links[cid].status == "LINKED":
                    continue
                aid = next(iter(cs))
                if singles[aid] > 1:
                    continue  # two requests claim the same delete: both stay unresolved
                links[cid].status, links[cid].activity_id, links[cid].resource_id = (
                    "LINKED",
                    aid,
                    cs[aid].resource_id,
                )
                for c2, cs2 in live.items():
                    if c2 != cid and aid in cs2:
                        del cs2[aid]
                        changed = True
        for cid, cs in live.items():
            l = links[cid]
            l.survivors = tuple(sorted(cs.values(), key=lambda c: (c.event_time, c.activity_id)))
            if l.status == "LINKED":
                continue
            if not l.candidates:
                l.status, l.reason = "NO_CANDIDATE", "no account delete in the window"
            elif not cs:
                l.status, l.reason = (
                    "NO_CANDIDATE",
                    "every candidate is tied to another person or claimed by another request",
                )
            elif len(cs) == 1:
                l.reason = "the only candidate is claimed by another request too"
            else:
                l.reason = (
                    f"{len(cs)} candidates survive every grounded filter (ADR 0004: no tie-break)"
                )
        self._accounts = links

    def account(self, case_id):
        if self._accounts is None:
            self._compute()
        return self._accounts.get(case_id) or AccountLink(
            case_id, "NOT_A_DELETION", reason="unknown request"
        )

    def distribution(self):
        """{number of surviving candidates: deletion requests}; 1 with status LINKED, >1 or 0 unresolved."""
        if self._accounts is None:
            self._compute()
        return dict(
            sorted(
                Counter(
                    len(l.survivors)
                    for l in self._accounts.values()
                    if l.status != "NOT_A_DELETION"
                ).items()
            )
        )

    def summary(self, case_ids):
        """One line for a run: surviving-candidate distribution and link outcomes over these requests."""
        if self._accounts is None:
            self._compute()
        ls = [
            self._accounts[c]
            for c in case_ids
            if c in self._accounts and self._accounts[c].status != "NOT_A_DELETION"
        ]
        dist = dict(sorted(Counter(len(l.survivors) for l in ls).items()))
        st = Counter(l.status for l in ls)
        return (
            f"linking: {len(ls)} deletion requests; surviving account candidates per request {dist}; "
            f"linked {st['LINKED']}, tied {st['TIED']} (UNRESOLVED_LINK), no candidate {st['NO_CANDIDATE']}"
        )

    # ---- catalog links -------------------------------------------------------------------
    def catalog(self, view, subject):
        """LINK_RESOURCE_IDENTITY claims visible at the cutoff (for `subject`, or all when None), each checked
        against the artifact naming the resource that was captured at or before the claim (ADR 0005)."""
        out = []
        for a in self._catalog:
            if a.event_time > view.cutoff:
                continue
            claimed = {
                self.resolver.owner_of(t)
                for t in EMAIL_IN_TEXT.findall(a.details) + _user_ids(a.details)
            } - {None}
            if subject is not None and subject.user_id not in claimed:
                continue
            arts = [
                o
                for o in view.observations(a.resource_id)
                if o.system_id == a.target_system
                and o.identifiers
                and self.store.captured_at(o.file_id) <= a.event_time
            ]
            if not arts:
                out.append(
                    CatalogLink(
                        a.activity_id,
                        a.target_system,
                        a.resource_id,
                        "UNCONFIRMED",
                        reason="no visible artifact names the resource with an identifier",
                    )
                )
                continue
            art = max(arts, key=lambda o: (self.store.captured_at(o.file_id), o.file_id, o.locator))
            shown = {t: self.resolver.owner_of(t) for t in art.identifiers}
            owner = next((u for u in shown.values() if u in claimed), None)
            if owner:
                out.append(
                    CatalogLink(
                        a.activity_id,
                        a.target_system,
                        a.resource_id,
                        "CONFIRMED",
                        art.file_id,
                        f"owner={owner}",
                    )
                )
            else:
                seen = ", ".join(f"{t} ({u or 'nobody'})" for t, u in sorted(shown.items()))
                out.append(
                    CatalogLink(
                        a.activity_id,
                        a.target_system,
                        a.resource_id,
                        "CONTRADICTED",
                        art.file_id,
                        f"{art.file_id} {art.locator} shows {seen}",
                    )
                )
        return out


def _user_ids(text):
    import re

    return re.findall(r"\buser_\d+\b", text)
