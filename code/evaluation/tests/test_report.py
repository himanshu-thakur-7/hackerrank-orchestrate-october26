"""T13 report generator: render(data) is pure; every required section appears and numbers come
from `data`."""

import unittest

from evaluation import report

METRICS = {
    k: 0.5
    for k in (
        "status_accuracy",
        "identity_recall",
        "finding_precision",
        "finding_recall",
        "finding_f1",
        "policy_accuracy",
        "evidence_accuracy",
        "strict_step_f1",
        "step_f1_unordered",
        "field_acc_operation",
        "field_acc_state",
        "field_acc_evidence_id",
        "field_acc_step_no",
        "field_acc_mean",
        "sequence_exact",
        "sequence_lcs_mean",
        "row_exact",
        "proxy",
    )
}
DATA = {
    "commit": "abc1234",
    "generated_at": "2026-10-25T00:00:00Z",
    "scores": {
        "dev": dict(METRICS, cases=22),
        "holdout": dict(METRICS, cases=10, proxy=0.805),
        "all": dict(METRICS, cases=32),
    },
    "dev_failures": ["case_01: status pred=INCOMPLETE gold=COMPLETE"],
    "history": [
        {"run": "20261025T010000Z", "commit": "aaa", "dev_proxy": 0.0, "holdout_proxy": 0.0}
    ],
    "metamorphic": [{"rid": "M1", "name": "shuffle", "expect": "identical", "holds": True}],
    "invariants": [
        {"id": "I1.evidence_exists_pre_audit", "desc": "cited evidence exists", "violations": 0}
    ],
    "rows": 518,
    "ledger": {
        "fully grounded": 344,
        "unresolved:tied": 136,
        "unlabeled:DELETION_PENDING (ADR 0010)": 8,
        "unlabeled:legal hold (ADR 0011)": 6,
        "unlabeled:INCOMPLETE [] (ADR 0015)": 3,
        "unknown": 0,
    },
    "ceiling": {"emitted": 2884, "missing": 350, "recall": 0.89},
    "custom": [
        {"case_id": "case_9001", "title": "replica-only account", "ok": True, "why": "replica"}
    ],
    "intent": {
        "texts": 398,
        "requests": 550,
        "confusion": {"DELETION/DELETION": 388, "NOT_DELETION/NOT_DELETION": 10},
        "disagreements": 0,
        "not_deletion_cases": 10,
    },
    "linking": {
        "samples_exact": 19,
        "samples_wrong": 0,
        "eval_linked": 360,
        "eval_tied": 136,
        "eval_none": 12,
    },
    "status_counts": {"COMPLETE": 150, "INCOMPLETE": 358, "NOT_APPLICABLE": 10},
}


class Render(unittest.TestCase):
    def setUp(self):
        self.md = report.render(DATA)

    def test_every_required_section_is_present(self):
        for heading in (
            "## 1. Approach",
            "## 2. Evaluation pipeline",
            "## 3. Results on the labeled samples",
            "## 4. Custom evaluation cases",
            "## 5. Metamorphic relations",
            "## 6. Invariants",
            "## 7. Loss ledger",
            "## 8. Silver-label audit",
            "## 9. Assumptions decided by unlabeled rules",
            "## 10. Failures found and improvements made",
            "## 11. Known limitations",
            "## 12. Reproduce",
        ):
            self.assertIn(heading, self.md)

    def test_numbers_come_from_the_data(self):
        self.assertIn("| proxy | 0.500 | 0.805 | 0.500 |", self.md)
        self.assertIn("DELETION_PENDING (ADR 0010) | 8", self.md)
        self.assertIn("~0.89", self.md)
        self.assertIn("abc1234", self.md)

    def test_holdout_is_aggregate_only_and_samples_do_not_predict_the_hidden_score(self):
        self.assertNotIn("holdout failures", self.md.lower())
        self.assertIn("do not predict the hidden score", self.md)


if __name__ == "__main__":
    unittest.main()
