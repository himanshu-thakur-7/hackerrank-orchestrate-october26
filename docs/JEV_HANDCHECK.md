# Jev ranker: hand check of the 15 lowest-scored eval steps

- **Source:** `docs/JEV_REVIEW_QUEUE.md`, from the live `jev-rank` run (11,450 calls, `jev-1.14.0`).
- **Method:** each step was checked by hand against the raw evidence file and line it cites. This is advisory and covers **state and time only**, not ownership.
- **Result: 0 real engine mistakes out of 15.** 15 are fine: 4 are false alarms from Jev on redaction wording, and 11 are absences proven by omission, which Jev cannot judge. No code fix was needed, so no regression test was added.

## 4 × VERIFY_RECORD_REDACTED on support records (fine; false alarms by Jev)

| case | resource | score | cited evidence (file, line) |
| --- | --- | --- | --- |
| case_464 | support_5586 | −0.328 | evidence_65 `records/service_resource_export_20260228_103637.json` line 291 |
| case_532 | support_7724 | −0.315 | evidence_62 `records/service_resource_export_20260129_114459.json` line 318 |
| case_231 | support_3964 | −0.256 | evidence_80 `records/service_resource_export_20260628_062556.json` line 262 |
| case_277 | support_2036 | −0.241 | evidence_77 `records/service_resource_export_20260603_083457.json` line 249 |

- **What each record shows:**
  - `customer_reference` is the stable `user_N`;
  - `requester_name`, `requester_email` and `requester_phone` are all `null`;
  - `message_excerpt` is a template such as "Customer supplied contact details for a delivery query."
- **This is the redacted state that policy requires** (the stable reference is kept and direct identifiers are removed).
- **Gold agrees.** The public samples case_26, case_27 and case_28 (support_4715, support_4707 and support_2351 in `service_resource_export_20260915_114455.json`) have the identical pattern, and `sample_output.csv` marks them `VERIFY_RECORD_REDACTED`.
- **Why Jev scored them low:** it reads the words "contact details" in the excerpt as exposed PII. The excerpt names no identifier.

## 11 × VERIFY_RECORD_ABSENT on accounts, by omission (fine; nothing for Jev to read)

| case | resource | score | cited covering snapshot |
| --- | --- | --- | --- |
| case_458 | account_077 | −0.080 | evidence_43 `databases/customer_data_reporting_replica_20260305.sql` |
| case_260 | account_7811 | −0.068 | evidence_24 `databases/customer_data_read_replica_20260613.sql` |
| case_253 | account_6073 | −0.067 | evidence_24 `databases/customer_data_read_replica_20260613.sql` |
| case_354 | account_3918 | −0.067 | evidence_33 `databases/customer_data_regional_replicas_20260424.sql` |
| case_57 | account_1298 | −0.067 | evidence_05 `databases/customer_data_read_replica_20260921.sql` |
| case_502 | account_2554 | −0.066 | evidence_63 `databases/customer_data_inventory_20260213.sql` |
| case_335 | account_8892 | −0.065 | evidence_72 `databases/customer_data_inventory_20260504.sql` |
| case_178 | account_1090 | −0.065 | evidence_84 `databases/customer_data_inventory_20260723.sql` |
| case_221 | account_4512 | −0.062 | evidence_81 `databases/customer_data_inventory_20260703.sql` |
| case_493 | account_7766 | −0.058 | evidence_63 `databases/customer_data_inventory_20260213.sql` |
| case_162 | account_5983 | −0.056 | evidence_15 `databases/customer_data_read_replica_20260802.sql` |

- **Checked with grep:**
  - the resource id has 0 occurrences in each cited file;
  - each file is a covering snapshot of the account table, captured at or before `audit_at`;
  - no file visible at audit names the resource with another state (case_335 and case_221 are named only in files captured after their audit).
- **This is absence by omission** (ADR 0014; the citation rule cites the covering file).
- **Why the scores are low:** the step has no evidence lines, so Jev sees `resource_mentioned_in_evidence: false` and scores near 0. These are blind spots of the ranker, not engine errors.

## Implication for the queue

- **Two step shapes fill the bottom of the queue** without being errors:
  - redacted support records whose excerpt mentions "contact details";
  - absences by omission.
- A reviewer should skip past these shapes first.
- The queue says nothing about **ownership** (decoy owner) or **operation type**, because Jev was never asked about them.
