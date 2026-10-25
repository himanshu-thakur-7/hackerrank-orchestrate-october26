"""A small synthetic world for engine tests: one subject with a historical email, files, observations.
Each scenario mirrors a real dataset situation named in the test that uses it."""
import hashlib
from _path import DATA
from ghostaudit import identity, policy
from ghostaudit.engine import Engine
from ghostaudit.intent import Intent
from ghostaudit.store import ActivityEvent, Coverage, EvidenceFile, EvidenceStore, Observation

OLD = "leila.old@example.com"
NEW = "leila.haddad@example.com"
OLD_HASH = hashlib.sha256(OLD.encode()).hexdigest()
DELETE = Intent("DELETION", "test", "rules")


def resolver():
    ids = [{"user_id": "user_1", "name": "Leila Haddad", "email": NEW, "phone": "+212 6 48 27 15 93",
            "email_hash": hashlib.sha256(NEW.encode()).hexdigest()},
           {"user_id": "user_2", "name": "Other Person", "email": "other@example.com", "phone": "+1 555 000 1111",
            "email_hash": hashlib.sha256(b"other@example.com").hexdigest()}]
    audit = [{"audit_id": "audit_1", "user_id": "user_1", "field_name": "email", "old_value": OLD, "new_value": NEW,
              "event_time": "2026-05-01T00:00:00Z"}]
    return identity.Resolver(ids, audit)


def ob(fid, at, sys_, res, state="PRESENT", ids=(), pii=(), cat=None, table="t", attrs=(), loc="line 1"):
    return Observation(fid, at, sys_, res, table, state, category=cat, pii_fields=tuple(pii), identifiers=tuple(ids),
                       locator=loc, attrs=tuple(attrs))


def engine(files, observations=(), coverage=(), activity=()):
    store = EvidenceStore(files=[EvidenceFile(f, f"evidence/x/{f}", "test", cap) for f, cap in files],
                          observations=observations, coverage=coverage, activity=activity)
    return Engine(store, resolver(), policy.Rules.from_csv(DATA / "deletion_rules.csv"))


def request(audit_at="2026-09-15T12:00:00Z", email=NEW, case_id="case_900"):
    return {"case_id": case_id, "email": email, "requested_at": "2026-09-01T00:00:00Z", "reported_status": "COMPLETE",
            "reported_at": "2026-09-02T00:00:00Z", "audit_at": audit_at, "request_text": "Please delete my account."}


def act(aid, at, type_, sys_, res, result="SUCCESS"):
    return ActivityEvent(aid, at, type_, "deletion_worker", sys_, res, result)


__all__ = ["OLD", "NEW", "OLD_HASH", "DELETE", "ob", "engine", "request", "act", "Coverage"]
