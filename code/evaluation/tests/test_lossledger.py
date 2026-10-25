"""T16 loss ledger: each engine log line maps to exactly one ledger reason; real eval has no
'unknown'."""

import unittest
from types import SimpleNamespace

from evaluation import lossledger


def assessment(log, resources=(), status="INCOMPLETE"):
    return SimpleNamespace(log=list(log), resources=list(resources), status=status)


class Reasons(unittest.TestCase):
    def test_log_lines_map_to_reasons(self):
        a = assessment(
            [
                "UNRESOLVED_LINK(primary account: 2 candidates survive every grounded filter (ADR "
                "0004: no tie-break); candidates [a, b])",
                "UNRESOLVED_LINK(activity_1 object_19: catalog claim not confirmed, no visible "
                "artifact)",
                "REJECTED_LINK(activity_2 marketing_001: shows x; ADR 0005)",
                "UNPROVEN(backup_service/backup_1)",
                "NO_GROUNDED_STEP",
                "STALE_LINK(account_service/account_1: every link predates requested_at and shows "
                "it absent; ADR 0016)",
            ]
        )
        self.assertEqual(
            lossledger.reasons(a, "TIED"),
            sorted(
                [
                    "unresolved:tied",
                    "unresolved:catalog",
                    "contradicted",
                    "unproven",
                    "unlabeled:INCOMPLETE [] (ADR 0015)",
                    "unlabeled:stale link (ADR 0016)",
                ]
            ),
        )
        w = assessment(
            ["UNRESOLVED_LINK(primary account: no account delete in the window; candidates [none])"]
        )
        self.assertEqual(lossledger.reasons(w, "NO_CANDIDATE"), ["unresolved:window"])

    def test_real_eval_ledger_has_no_unknown(self):
        code, ledger = lossledger.run()
        self.assertEqual(code, 0)
        self.assertEqual(len(ledger), 518)
        self.assertNotIn("unknown", {r for rs in ledger.values() for r in rs})


if __name__ == "__main__":
    unittest.main()
