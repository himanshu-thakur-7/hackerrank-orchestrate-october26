"""L1 scorer: score(pred, gold, case_ids) -> metrics. Expected values below were worked out by hand."""
import unittest
from evaluation import scorer
from evaluation.tests.helpers import GOLD


def st(n, phase, sys_, res, op, state, ev=""):
    return {"step_no": n, "phase": phase, "system_id": sys_, "resource_id": res, "operation": op, "state": state, "evidence_id": ev}


GOLD_TOY = {
    "A": ("INCOMPLETE", [st(1, "FINDING", "s1", "r1", "REPORT_REMAINING_RECORD", "PRESENT", "ev1"),
                         st(2, "REMEDIATION", "s1", "r1", "DELETE_RECORD", "ABSENT"),
                         st(3, "VERIFICATION", "s1", "r1", "VERIFY_RECORD_ABSENT", "ABSENT"),
                         st(4, "VERIFICATION", "acct", "a1", "VERIFY_RECORD_ABSENT", "ABSENT")]),
    "B": ("COMPLETE", [st(1, "VERIFICATION", "acct", "b1", "VERIFY_RECORD_ABSENT", "ABSENT", "ev3")]),
}
PRED_TOY = {
    "A": ("INCOMPLETE", [st(1, "FINDING", "s1", "r1", "REPORT_REMAINING_RECORD", "PRESENT", "ev2"),
                         st(2, "REMEDIATION", "s1", "r1", "DELETE_RECORD", "ABSENT"),
                         st(3, "VERIFICATION", "s1", "r1", "VERIFY_RECORD_ABSENT", "ABSENT")]),
    "B": ("INCOMPLETE", [st(1, "FINDING", "acct", "b1", "REPORT_REMAINING_RECORD", "PRESENT", "ev3"),
                         st(2, "REMEDIATION", "acct", "b1", "DELETE_RECORD", "ABSENT"),
                         st(3, "VERIFICATION", "acct", "b1", "VERIFY_RECORD_ABSENT", "ABSENT")]),
}


class Scorer(unittest.TestCase):
    def test_gold_against_itself_is_perfect(self):
        g = scorer.load(GOLD)
        m = scorer.score(g, g, sorted(g))
        for k, v in m.items():
            if isinstance(v, float):
                self.assertEqual(v, 1.0, k)

    def test_hand_worked_example(self):
        m = scorer.score(PRED_TOY, GOLD_TOY, ["A", "B"])
        expect = {
            "status_accuracy": 0.5,
            "identity_recall": 2 / 3,
            "finding_precision": 0.5, "finding_recall": 1.0, "finding_f1": 2 / 3,
            "policy_accuracy": 1 / 3,
            "evidence_accuracy": 0.0,
            "strict_step_f1": 4 / 11,
            "step_f1_unordered": 4 / 11,
            "field_acc_operation": 1.0, "field_acc_state": 1.0, "field_acc_evidence_id": 0.5, "field_acc_step_no": 0.75,
            "field_acc_mean": 0.8125,
            "sequence_exact": 0.0,
            "sequence_lcs_mean": (0.75 + 1 / 3) / 2,
            "row_exact": 0.0,
            "proxy": 0.431608,
        }
        for k, v in expect.items():
            self.assertAlmostEqual(m[k], v, places=6, msg=k)

    def test_subset_scoring_counts_only_given_cases(self):
        m = scorer.score(PRED_TOY, GOLD_TOY, ["A"])
        self.assertEqual(m["status_accuracy"], 1.0)
        self.assertEqual(m["cases"], 1)

    def test_missing_prediction_counts_as_empty(self):
        m = scorer.score({}, GOLD_TOY, ["B"])
        self.assertEqual(m["status_accuracy"], 0.0)
        self.assertEqual(m["identity_recall"], 0.0)
