# ADR 0006 — A required end state with no evidence: never COMPLETE; an attempted-but-unproven delete is reported as remaining

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** **no, in part**; see "Dissent"

## Question

A resource is grounded-linked to the subject, but no pre-audit evidence shows its end state. What is emitted?

## Context

- AGENTS.md §6.5: "A deletion is COMPLETE only when every relevant copy has the required treatment …". §6.6: "A finding must use the participant-visible `file_id`, `activity_id`, or `audit_id` that proves it."
- Measured on samples:
  - all 12 primary accounts that have a FAILED or PARTIAL delete claim before the audit are gold **VERIFY_RECORD_ABSENT** (never a finding);
  - at least 6 of them (account_002, 3960, 5037, 410, 7012, 8858) have **no pre-audit evidence at all**;
  - 0 gold steps cite an `activity_id` or `audit_id`.

## Recommendation

COMPLETE requires evidence for every required end state, so agree on that part. But when the only signal is a FAILED or PARTIAL activity claim, emit the resource as a **future verification step** (empty `evidence_id`, e.g. VERIFY_RECORD_ABSENT), not as REPORT_REMAINING_RECORD.

## Decision (owner)

- No evidence for a required end state → the case is **not COMPLETE**.
- If deletion was **attempted but is unproven** (a FAILED or PARTIAL claim, no evidence of absence) → report the resource as **remaining** (REPORT_REMAINING_RECORD citing the activity row, then DELETE_RECORD, then VERIFY_RECORD_ABSENT).
- If nothing grounded exists → emit nothing for that resource.

## Dissent

The measured gold pattern disagrees with reporting such resources as remaining:

- In all 12 sample cases with a FAILED or PARTIAL account-delete claim, gold lists the account only as VERIFY_RECORD_ABSENT.
- For about 6 of those, no evidence exists either way, so the ruling would add a finding and a remediation step that gold does not contain, costing about 2 extra steps per such case.
- Citing an activity row as proof of *presence* also treats a claim as a state, the mirror image of ADR 0003. A FAILED delete proves only that a delete was attempted.

I would emit the verification step only, and leave the status to the other grounded findings.

**I adopt the ruling as written**, and I will report its measured impact on samples in the evaluation report so the owner can revisit it.

## Consequences

- More INCOMPLETE findings that cite `activity_N` IDs.
- An expected precision cost on samples (to be measured by the evaluator).
- COMPLETE is never claimed without per-resource evidence.

## Rejected alternatives

- **Assume absent when a SUCCESS claim exists:** evidence over claims.
- **Verification-only for unproven resources:** recommended, but overruled.
