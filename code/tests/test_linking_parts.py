"""The account-link pieces in isolation: one-to-one elimination and the final status (ADR 0003, 0004)."""

import unittest

import _path  # noqa: F401  (puts code/ on sys.path)

from ghostaudit.linking import AccountLink, Candidate, _eliminate_one_to_one, _settle


def cand(aid, rid, t="2026-09-15T09:00:00Z"):
    return Candidate(aid, rid, t, 1.0, "SUCCESS")


class Elimination(unittest.TestCase):
    def test_a_single_candidate_is_claimed_and_removed_from_the_others(self):
        links = {"a": AccountLink("a", "TIED"), "b": AccountLink("b", "TIED")}
        live = {
            "a": {"x": cand("x", "account_1")},
            "b": {"x": cand("x", "account_1"), "y": cand("y", "account_2")},
        }
        _eliminate_one_to_one(links, live)
        self.assertEqual((links["a"].status, links["a"].resource_id), ("LINKED", "account_1"))
        self.assertEqual((links["b"].status, links["b"].resource_id), ("LINKED", "account_2"))

    def test_two_requests_sharing_their_only_candidate_link_neither(self):
        links = {"a": AccountLink("a", "TIED"), "b": AccountLink("b", "TIED")}
        live = {"a": {"x": cand("x", "account_1")}, "b": {"x": cand("x", "account_1")}}
        _eliminate_one_to_one(links, live)
        self.assertEqual((links["a"].status, links["b"].status), ("TIED", "TIED"))

    def test_two_survivors_stay_tied(self):
        links = {"a": AccountLink("a", "TIED")}
        live = {"a": {"x": cand("x", "account_1"), "y": cand("y", "account_2")}}
        _eliminate_one_to_one(links, live)
        self.assertEqual(links["a"].status, "TIED")


class Settle(unittest.TestCase):
    def test_reasons_for_unresolved_links(self):
        none = AccountLink("a", "TIED", candidates=())
        _settle(none, {})
        self.assertEqual(
            (none.status, none.reason), ("NO_CANDIDATE", "no account delete in the window")
        )
        gone = AccountLink("a", "TIED", candidates=(cand("x", "account_1"),))
        _settle(gone, {})
        self.assertEqual(gone.status, "NO_CANDIDATE")
        two = AccountLink("a", "TIED", candidates=(cand("x", "a1"), cand("y", "a2")))
        _settle(two, {"x": cand("x", "a1"), "y": cand("y", "a2")})
        self.assertEqual(two.status, "TIED")
        self.assertIn("no tie-break", two.reason)
        self.assertEqual([c.activity_id for c in two.survivors], ["x", "y"])

    def test_a_linked_request_keeps_its_status(self):
        link = AccountLink(
            "a", "LINKED", resource_id="account_1", candidates=(cand("x", "account_1"),)
        )
        _settle(link, {"x": cand("x", "account_1")})
        self.assertEqual((link.status, link.reason), ("LINKED", ""))


if __name__ == "__main__":
    unittest.main()
