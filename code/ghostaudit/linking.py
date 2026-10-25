"""Linking beyond the subject's own identifiers (docs/03_DESIGN.md §3 Stage 4; ADR 0003-0005).

  Linker(store, resolver, requests, intents)
    .account(case_id)        -> AccountLink   primary account from activity, unique survivor only
    .distribution()          -> {candidate count: deletion requests}, after all filters
    .catalog(view, subject)  -> [CatalogLink] LINK_RESOURCE_IDENTITY claims checked against their
                                artifact

Account candidates are DELETE_RECORD -> account_service activity rows (claims used only as a
linkage key, never as state) that pass, in order:
  1. the window: event_time in [reported_at - 1.5 h, reported_at - 0.5 h]
     (ACCOUNT_DELETE_WINDOW_HOURS), and at or before audit_at;
  2. reported_result agrees with reported_status (RESULT_OF);
  3. the pre-audit identity filter: drop a candidate that visible evidence ties to another
     person; if visible evidence ties one to this subject, keep only those;
  4. global one-to-one elimination over every deletion request (samples + evaluation): a request
     left with one candidate claims it, and it is removed from every other request, until
     nothing changes.
Only a unique survivor is linked. Anything else is logged with its reason and candidate set;
there is no tie-break (ADR 0004), in particular never by case_id order. The distance to
reported_at is reported for each candidate, but it is not used to choose.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

from ghostaudit.loaders.common import EMAIL_IN_TEXT

if TYPE_CHECKING:
    from ghostaudit.data import Request
    from ghostaudit.identity import Identity, Resolver
    from ghostaudit.intent import Intent
    from ghostaudit.store import ActivityEvent, CaseView, EvidenceStore, Observation
# The primary-account delete lands between 0.5 h and 1.5 h before reported_at (docs/03 §1: the gold
# account's delete was measured 0.75-1.23 h before reported_at in all 23 generated sample cases).
ACCOUNT_DELETE_WINDOW_HOURS = (0.5, 1.5)
RESULT_OF = {"COMPLETE": "SUCCESS", "PARTIALLY_COMPLETE": "PARTIAL", "NOT_STARTED": "FAILED"}


def _T(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def _case_order(case_id: str) -> tuple[int, str]:
    """Natural case order (a shorter id sorts first, so 9 comes before 10); it only makes the
    iteration deterministic."""
    return (len(case_id), case_id)


def _eliminate_one_to_one(
    links: dict[str, AccountLink], live: dict[str, dict[str, Candidate]]
) -> None:
    """Global one-to-one elimination: a request left with exactly one candidate claims it, and the
    claimed delete is removed from every other request, until nothing changes. A delete that two
    requests both claim as their only candidate links neither (ADR 0004)."""
    changed = True
    while changed:
        changed = False
        singles = Counter(next(iter(cs)) for cs in live.values() if len(cs) == 1)
        for cid, cs in live.items():
            if len(cs) != 1 or links[cid].status == "LINKED":
                continue
            aid = next(iter(cs))
            if singles[aid] > 1:
                continue
            link = links[cid]
            link.status, link.activity_id, link.resource_id = "LINKED", aid, cs[aid].resource_id
            changed |= _remove_claimed(live, cid, aid)


def _remove_claimed(live: dict[str, dict[str, Candidate]], owner_cid: str, aid: str) -> bool:
    """Remove activity `aid` from every request but its owner; True if anything was removed."""
    removed = False
    for cid, cs in live.items():
        if cid != owner_cid and aid in cs:
            del cs[aid]
            removed = True
    return removed


def _settle(link: AccountLink, survivors: dict[str, Candidate]) -> None:
    """Record the survivors and, for an unlinked request, why it stayed unresolved."""
    link.survivors = tuple(sorted(survivors.values(), key=lambda c: (c.event_time, c.activity_id)))
    if link.status == "LINKED":
        return
    if not link.candidates:
        link.status, link.reason = "NO_CANDIDATE", "no account delete in the window"
    elif not survivors:
        link.status = "NO_CANDIDATE"
        link.reason = "every candidate is tied to another person or claimed by another request"
    elif len(survivors) == 1:
        link.reason = "the only candidate is claimed by another request too"
    else:
        link.reason = (
            f"{len(survivors)} candidates survive every grounded filter (ADR 0004: no tie-break)"
        )


@dataclass(frozen=True)
class Candidate:
    """One DELETE_RECORD activity row that may be the subject's primary account."""

    activity_id: str
    resource_id: str
    event_time: str
    hours_before_report: float
    result: str


@dataclass
class AccountLink:
    """The primary-account decision for one request.

    status is LINKED (resource_id and activity_id set), TIED, NO_CANDIDATE or NOT_A_DELETION;
    candidates and survivors record what each filter kept, for the log."""

    case_id: str
    status: str  # LINKED | TIED | NO_CANDIDATE | NOT_A_DELETION
    resource_id: str | None = None
    activity_id: str | None = None
    candidates: tuple[Candidate, ...] = ()  # after window + result
    survivors: tuple[Candidate, ...] = ()  # after identity filter + global elimination
    reason: str = ""
    filtered: list[tuple[str, str]] = field(default_factory=list)  # (resource_id, why dropped)

    def describe(self) -> str:
        """One log line: the linked account and its distance, or why none was linked."""
        if self.status == "LINKED":
            c = next(c for c in self.survivors if c.resource_id == self.resource_id)
            return (
                f"LINKED_ACCOUNT({self.resource_id} via {self.activity_id}, "
                f"{c.hours_before_report:.2f} h before reported_at)"
            )
        cands = ", ".join(f"{c.resource_id}/{c.activity_id}" for c in self.survivors) or "none"
        return f"UNRESOLVED_LINK(primary account: {self.reason}; candidates [{cands}])"


@dataclass(frozen=True)
class CatalogLink:
    """A LINK_RESOURCE_IDENTITY claim and what its artifact shows (ADR 0005)."""

    activity_id: str
    system_id: str
    resource_id: str
    status: str  # CONFIRMED | CONTRADICTED | UNCONFIRMED
    artifact: str = ""  # file_id checked
    reason: str = ""


class Linker:
    """Links resources that do not carry the subject's identifiers (module docstring).

    Account links are computed once for every request together, on first use, because the
    one-to-one elimination is global."""

    def __init__(
        self,
        store: EvidenceStore,
        resolver: Resolver,
        requests: Iterable[Request],
        intents: Mapping[str, Intent],
    ) -> None:
        self.store, self.resolver = store, resolver
        self.requests = {q["case_id"]: q for q in requests}
        self.intents = intents
        self._accounts: dict[str, AccountLink] | None = None  # computed once, on first use
        self._deletes = [
            a
            for a in store.activity_events
            if a.event_type == "DELETE_RECORD" and a.target_system == "account_service"
        ]
        self._catalog = [
            a for a in store.activity_events if a.event_type == "LINK_RESOURCE_IDENTITY"
        ]

    # ---- primary account -------------------------------------------------------------------
    def _candidates(self, q: Request) -> list[Candidate]:
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

    def _owners(self, view: CaseView, resource_id: str) -> set[str]:
        owners: set[str] = set()
        for o in view.observations(resource_id):
            if o.system_id == "account_service":
                owners |= {u for t in o.identifiers if (u := self.resolver.owner_of(t)) is not None}
        for c in self.catalog(view, None):
            if c.resource_id == resource_id and c.status == "CONFIRMED":
                owners |= set(c.reason.split("owner=")[1:2])
        return owners

    def _identity_filter(
        self, link: AccountLink, cands: list[Candidate], view: CaseView, subject: Identity
    ) -> list[Candidate]:
        """Drop candidates that visible pre-audit evidence ties to someone else; if any is tied to
        this subject, keep only those. Dropped candidates are recorded on the link."""
        mine, other = [], []
        for c in cands:
            owners = self._owners(view, c.resource_id)
            if subject.user_id in owners:
                mine.append(c)
            elif owners:
                other.append(c)
                link.filtered.append(
                    (c.resource_id, f"pre-audit evidence ties it to {', '.join(sorted(owners))}")
                )
        return mine or [c for c in cands if c not in other]

    def _screen(self, cid: str) -> tuple[AccountLink, list[Candidate] | None]:
        """(AccountLink, kept candidates) for one request; kept is None when it is not a
        resolvable deletion request (no candidates are generated for it)."""
        q = self.requests[cid]
        intent = self.intents.get(cid)
        subject = self.resolver.resolve(q["email"])
        if intent is None or intent.label != "DELETION" or subject is None:
            return AccountLink(
                cid, "NOT_A_DELETION", reason="not a resolvable deletion request"
            ), None
        cands = self._candidates(q)
        link = AccountLink(cid, "TIED", candidates=tuple(cands))
        return link, self._identity_filter(link, cands, self.store.as_of(q["audit_at"]), subject)

    def _compute(self) -> dict[str, AccountLink]:
        links, live = {}, {}
        for cid in sorted(self.requests, key=_case_order):
            links[cid], keep = self._screen(cid)
            if keep is not None:
                live[cid] = {c.activity_id: c for c in keep}
        _eliminate_one_to_one(links, live)
        for cid, survivors in live.items():
            _settle(links[cid], survivors)
        return links

    def _all(self) -> dict[str, AccountLink]:
        """Every request's account link, computed on first use (the elimination is global)."""
        if self._accounts is None:
            self._accounts = self._compute()
        return self._accounts

    def account(self, case_id: str) -> AccountLink:
        """The account link of `case_id` (NOT_A_DELETION for an unknown request)."""
        return self._all().get(case_id) or AccountLink(
            case_id, "NOT_A_DELETION", reason="unknown request"
        )

    def distribution(self) -> dict[int, int]:
        """{number of surviving candidates: deletion requests}; 1 with status LINKED, >1 or 0
        unresolved."""
        return dict(
            sorted(
                Counter(
                    len(acct.survivors)
                    for acct in self._all().values()
                    if acct.status != "NOT_A_DELETION"
                ).items()
            )
        )

    def summary(self, case_ids: Iterable[str]) -> str:
        """One line for a run: surviving-candidate distribution and link outcomes over these
        requests."""
        accounts = self._all()
        ls = [
            accounts[c]
            for c in case_ids
            if c in accounts and accounts[c].status != "NOT_A_DELETION"
        ]
        dist = dict(sorted(Counter(len(acct.survivors) for acct in ls).items()))
        st = Counter(acct.status for acct in ls)
        return (
            f"linking: {len(ls)} deletion requests; surviving account candidates per request "
            f"{dist}; "
            f"linked {st['LINKED']}, tied {st['TIED']} (UNRESOLVED_LINK), no candidate "
            f"{st['NO_CANDIDATE']}"
        )

    # ---- catalog links -------------------------------------------------------------------
    def catalog(self, view: CaseView, subject: Identity | None) -> list[CatalogLink]:
        """LINK_RESOURCE_IDENTITY claims visible at the cutoff (for `subject`, or all when None),
        each checked against the artifact naming the resource that was captured at or before the
        claim (ADR 0005)."""
        out = []
        for a in self._catalog:
            if a.event_time > view.cutoff:
                continue
            claimed = self._claimed_owners(a)
            if subject is not None and subject.user_id not in claimed:
                continue
            out.append(self._check_claim(a, claimed, self._artifacts(view, a)))
        return out

    def _claimed_owners(self, a: ActivityEvent) -> set[str]:
        """The known people a link row names (by email or user id)."""
        tokens = EMAIL_IN_TEXT.findall(a.details) + _user_ids(a.details)
        return {u for t in tokens if (u := self.resolver.owner_of(t)) is not None}

    def _artifacts(self, view: CaseView, a: ActivityEvent) -> list[Observation]:
        """Visible observations of the linked resource that carry identifiers and were captured at
        or before the claim."""
        return [
            o
            for o in view.observations(a.resource_id)
            if o.system_id == a.target_system
            and o.identifiers
            and cast("str", self.store.captured_at(o.file_id)) <= a.event_time
        ]

    def _check_claim(
        self, a: ActivityEvent, claimed: set[str], arts: list[Observation]
    ) -> CatalogLink:
        """CONFIRMED when the latest artifact shows a claimed person, CONTRADICTED when it shows
        someone else, UNCONFIRMED when no artifact names the resource."""
        if not arts:
            return CatalogLink(
                a.activity_id,
                a.target_system,
                a.resource_id,
                "UNCONFIRMED",
                reason="no visible artifact names the resource with an identifier",
            )
        art = max(arts, key=lambda o: (self.store.captured_at(o.file_id), o.file_id, o.locator))
        shown = {t: self.resolver.owner_of(t) for t in art.identifiers}
        owner = next((u for u in shown.values() if u in claimed), None)
        if owner:
            return CatalogLink(
                a.activity_id,
                a.target_system,
                a.resource_id,
                "CONFIRMED",
                art.file_id,
                f"owner={owner}",
            )
        seen = ", ".join(f"{t} ({u or 'nobody'})" for t, u in sorted(shown.items()))
        return CatalogLink(
            a.activity_id,
            a.target_system,
            a.resource_id,
            "CONTRADICTED",
            art.file_id,
            f"{art.file_id} {art.locator} shows {seen}",
        )


def _user_ids(text: str) -> list[str]:
    import re

    return re.findall(r"\buser_\d+\b", text)
