"""L0 contract gate: behaviour through gate.check(output, requests, manifest) -> list of violation strings."""
import unittest
from evaluation import gate
from evaluation.tests.helpers import GOLD, SAMPLE_REQ, MANIFEST, gold_rows, tmp_copy, mutate_step


def check(path):
    return gate.check(path, SAMPLE_REQ, MANIFEST)


class FormatRules(unittest.TestCase):
    def test_gold_sample_passes(self):
        self.assertEqual(check(GOLD), [])

    def test_bad_quoting_fails_with_line_number(self):
        raw = GOLD.read_bytes().decode()
        lines = raw.split("\n")
        lines[3] = lines[3].replace('""', '"')          # un-escape inner quotes on data line 3
        v = check(tmp_copy(raw="\n".join(lines).encode()))
        self.assertTrue(v)
        self.assertIn("L0.csv", v[0])
        self.assertIn("line 4", v[0])

    def test_bom_and_crlf_and_header(self):
        raw = GOLD.read_bytes()
        self.assertIn("L0.encoding", check(tmp_copy(raw=b"\xef\xbb\xbf" + raw))[0])
        self.assertIn("L0.line_endings", check(tmp_copy(raw=raw.replace(b"\n", b"\r\n")))[0])
        bad_header = raw.replace(b"case_id,deletion_status,steps_json", b"case_id,status,steps_json", 1)
        self.assertIn("L0.header", check(tmp_copy(raw=bad_header))[0])


if __name__ == "__main__":
    unittest.main()


class CaseSetAndOrder(unittest.TestCase):
    def test_wrong_row_order_names_the_offending_case(self):
        rows = gold_rows()
        rows[3], rows[4] = rows[4], rows[3]               # case_03 <-> case_04
        v = check(tmp_copy(rows=rows))
        self.assertTrue(any(x.startswith("L0.order") and "case_03" in x for x in v), v)

    def test_missing_duplicate_and_unknown_cases(self):
        rows = gold_rows()
        self.assertTrue(any("L0.cases" in x and "missing" in x and "case_32" in x for x in check(tmp_copy(rows=rows[:-1]))))
        dup = rows + [rows[-1]]
        self.assertTrue(any("L0.cases" in x and "duplicate" in x for x in check(tmp_copy(rows=dup))))
        unk = [list(r) for r in rows]; unk[1][0] = "case_99"
        self.assertTrue(any("L0.cases" in x and "unknown" in x and "case_99" in x for x in check(tmp_copy(rows=unk))))

    def test_natural_numeric_order_is_required_not_lexical(self):
        self.assertEqual(gate.natural_key("case_100") > gate.natural_key("case_33"), True)


def first(v, code):
    return next((x for x in v if x.startswith(code)), None)


class StepRules(unittest.TestCase):
    def test_null_evidence_on_remediation_is_rejected_precisely(self):
        rows = mutate_step(gold_rows(), "case_05", 2, evidence_id=None)
        msg = first(check(tmp_copy(rows=rows)), "L0.evidence")
        self.assertIsNotNone(msg)
        self.assertIn("case_05 step 2", msg)
        self.assertIn("null", msg)

    def test_unknown_triple_and_extra_key(self):
        rows = mutate_step(gold_rows(), "case_05", 1, state="ABSENT")
        self.assertIn("case_05 step 1", first(check(tmp_copy(rows=rows)), "L0.triple"))
        rows = mutate_step(gold_rows(), "case_05", 1, note="x")
        self.assertIn("case_05 step 1", first(check(tmp_copy(rows=rows)), "L0.keys"))

    def test_step_numbering_and_sort_key(self):
        rows = mutate_step(gold_rows(), "case_05", 3, step_no=4)
        self.assertIn("case_05", first(check(tmp_copy(rows=rows)), "L0.step_no"))
        rows = mutate_step(gold_rows(), "case_05", 3, step_no="3")
        self.assertIn("case_05", first(check(tmp_copy(rows=rows)), "L0.step_no"))
        # case_11 steps 2,3 are REPORT_EXPOSED_PII on analytics then support: swap their system/resource
        rows = mutate_step(gold_rows(), "case_11", 2, system_id="support_platform", resource_id="support_864")
        rows = mutate_step(rows, "case_11", 3, system_id="analytics_platform", resource_id="analytics_2034")
        self.assertIn("case_11", first(check(tmp_copy(rows=rows)), "L0.sort"))

    def test_status_shape_rules(self):
        rows = [list(r) for r in gold_rows()]
        rows[1][1] = "NOT_APPLICABLE"                      # case_01 keeps its steps
        self.assertIn("case_01", first(check(tmp_copy(rows=rows)), "L0.status"))
        rows = [list(r) for r in gold_rows()]
        rows[5][1] = "COMPLETE"                            # case_05 is INCOMPLETE with findings
        self.assertIn("case_05", first(check(tmp_copy(rows=rows)), "L0.status"))
        rows = [list(r) for r in gold_rows()]
        rows[1][2] = "not json"
        self.assertIn("case_01", first(check(tmp_copy(rows=rows)), "L0.json"))

    def test_evidence_must_exist_and_be_captured_by_audit_at(self):
        rows = mutate_step(gold_rows(), "case_05", 1, evidence_id="evidence_999")
        self.assertIn("does not exist", first(check(tmp_copy(rows=rows)), "L0.evidence"))
        rows = mutate_step(gold_rows(), "case_05", 1, evidence_id="evidence_93")   # captured 2026-09-16 > audit 09-08
        self.assertIn("after audit_at", first(check(tmp_copy(rows=rows)), "L0.evidence"))
        rows = mutate_step(gold_rows(), "case_05", 1, evidence_id="")
        self.assertIn("finding", first(check(tmp_copy(rows=rows)), "L0.evidence"))
        rows = mutate_step(gold_rows(), "case_05", 2, evidence_id="evidence_54")
        self.assertIn('must be ""', first(check(tmp_copy(rows=rows)), "L0.evidence"))

    def test_remediation_needs_finding_and_verification(self):
        rows = mutate_step(gold_rows(), "case_05", 3, resource_id="account_999")
        self.assertIn("account_005", first(check(tmp_copy(rows=rows)), "L0.pairing"))
