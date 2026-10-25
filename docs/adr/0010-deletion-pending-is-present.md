# ADR 0010 — A DELETION_PENDING account is still present (rule_01); unlabeled assumption

- **Status:** Accepted (owner ruling); **unlabeled**, no sample covers it
- **Recommendation matched the ruling:** yes

## Question

8 eval cases show the subject's account row with `account_status 'DELETION_PENDING'` and an email still on it, captured on the audit day: case_67, 129, 177, 247, 249, 333, 499, 501 (`docs/02` §7.6). Is that remaining data?

## Context

- rule_01: `USER_PROFILE, Always, DELETE`.
- The row exists and holds a direct identifier, e.g. `evidence_63` line 19 `account_3626 … 'daniel.m47291@outlook.com' … 'DELETION_PENDING'`.
- In 5 of the 8, the earlier delete claim is SUCCESS and `reported_status` is COMPLETE.

## Recommendation and decision

Treat the account as **present**:

- REPORT_REMAINING_RECORD (citing the snapshot);
- DELETE_RECORD;
- VERIFY_RECORD_ABSENT;
- the case is **INCOMPLETE**.

## Consequences

- Listed as a stated, unlabeled assumption in the README and the evaluation report.

## Rejected alternatives

- **"Pending means in progress, so COMPLETE":** the record and its identifier still exist at `audit_at`.
