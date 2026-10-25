# ADR 0011 — Pre-audit legal_hold_N records are retained (rule_13); unlabeled

- **Status:** Accepted (owner ruling); **unlabeled**
- **Recommendation matched the ruling:** yes, with a caveat

## Question

6 eval cases have a `legal_hold_N` record linked to the subject at or before `audit_at`: case_261, 390, 460, 473, 505, 511. What is emitted?

## Context

- rule_13: `LEGAL_HOLD_RECORD, A supplied legal hold is active, RETAIN`.
- Example: `evidence_47` line 30, `legal_hold_2227 … "retention_reason":"payment_dispute_and_tax_record","retained_until":"2033-12-31T23:59:59Z"`.
- No sample covers a `legal_hold_N` resource; there are 0 gold steps on `legal_service`.
- **Caveat:** 6 sample subjects appear in the legal *register* PDF (`evidence_27`, which lists orders but no resource IDs), and their gold has no legal step.
- 3 further cases have holds only after the audit (case_46, case_220, case_432).

## Recommendation and decision

For the 6 pre-audit cases, emit **VERIFY_RECORD_PRESENT `legal_service legal_hold_N`**, citing the file where the case is COMPLETE. Never delete. Register entries without a resource ID produce no step. The 3 post-audit-only cases get nothing (ADR 0002).

## Consequences

- Up to 6 unlabeled steps, a small risk if gold omits them.

## Rejected alternatives

- **Deleting held records:** violates rule_13.
- **Steps for register rows:** they have no resource ID, and the samples show none.
