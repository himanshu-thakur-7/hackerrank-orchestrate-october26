"""Identity Resolver: request email -> the subject's full identifier set.

Exact matching only (after lowercasing emails and keeping only digits of phones); look-alike
emails never match (CONTEXT: look-alike decoy). History comes from user_audit_log.csv.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from ghostaudit.data import read_csv


def _digits(s):
    return re.sub(r"\D", "", s or "")


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class Identity:
    user_id: str
    emails: set = field(default_factory=set)
    email_hashes: set = field(default_factory=set)
    phones: set = field(default_factory=set)
    names: set = field(default_factory=set)

    def tokens(self):
        """Every exact identifier of the subject, as Evidence Store index keys (phones as
        'tel:<digits>')."""
        return sorted(
            {self.user_id} | self.emails | self.email_hashes | {"tel:" + p for p in self.phones}
        )

    def matches(self, token):
        """True if token is exactly one of the subject's identifiers (case-insensitive for text)."""
        t = (token or "").strip()
        if not t:
            return False
        low = t.lower()
        return (
            t == self.user_id
            or low in self.emails
            or low in self.email_hashes
            or (len(_digits(t)) >= 9 and _digits(t) in self.phones)
        )


class Resolver:
    def __init__(self, identities, audit_rows):
        self._by_user = {}
        for r in identities:
            i = Identity(
                r["user_id"],
                {r["email"].lower()},
                {r["email_hash"].lower()},
                {_digits(r["phone"])},
                {r["name"]},
            )
            self._by_user[r["user_id"]] = i
        for a in audit_rows:
            i = self._by_user.get(a["user_id"])
            if i is None:
                continue
            if a["field_name"] == "email":
                i.emails |= {a["old_value"].lower(), a["new_value"].lower()}
            elif a["field_name"] == "email_hash":
                i.email_hashes |= {a["old_value"].lower(), a["new_value"].lower()}
            elif a["field_name"] == "phone":
                i.phones |= {_digits(a["old_value"]), _digits(a["new_value"])}
        self._by_email = {}
        for i in self._by_user.values():
            i.email_hashes |= {_sha(e) for e in i.emails}
            i.phones.discard("")
            for e in i.emails:
                self._by_email.setdefault(e, set()).add(i.user_id)

    @classmethod
    def from_dataset(cls, data_dir):
        d = Path(data_dir)
        return cls(read_csv(d / "user_identities.csv"), read_csv(d / "user_audit_log.csv"))

    def resolve(self, email):
        """The unique subject for a request email, or None (no match or ambiguous)."""
        users = self._by_email.get((email or "").strip().lower(), set())
        return self._by_user[next(iter(users))] if len(users) == 1 else None

    def user(self, user_id):
        return self._by_user.get(user_id)

    def owner_of(self, token):
        """user_id whose identifier set contains `token` exactly (email any case, sha256, phone,
        user_id), else None."""
        if not hasattr(self, "_owner"):
            self._owner = {}
            for u in self._by_user.values():
                self._owner[u.user_id] = u.user_id
                for e in u.emails | u.email_hashes:
                    self._owner[e] = u.user_id
                for ph in u.phones:
                    self._owner["tel:" + ph] = u.user_id
        t = (token or "").strip()
        hit = self._owner.get(t) or self._owner.get(t.lower())
        if hit is None and len(_digits(t)) >= 9 and not re.search(r"[A-Za-z]", t):
            hit = self._owner.get("tel:" + _digits(t))
        return hit
