# Architecture Decision Records

Each ADR states the question, my recommendation (with rule text and measured numbers), and the owner's ruling. One ADR records a dissent.

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-case-id-sort-order.md) | Sort output rows by numeric case_id (case_33 … case_550) | Accepted |
| [0002](0002-strict-audit-cutoff.md) | Strict inclusive cutoff: only files with captured_at <= audit_at, file-level | Accepted |
| [0003](0003-account-recovery-from-activity.md) | Recover account IDs from system_activity, unique grounded candidate only; activity is linkage, not state | Accepted |
| [0004](0004-ties-are-unresolved.md) | Tied candidates are omitted and logged as unresolved links; no case_id-order tie-break | Accepted |
| [0005](0005-contradicted-screenshot-links.md) | Reject identity links that the referenced screenshot contradicts (case_63) | Accepted |
| [0006](0006-no-evidence-no-complete.md) | No evidence for a required end state means not COMPLETE; attempted-but-unproven is reported as remaining | Accepted, **with dissent** |
| [0007](0007-one-file-structure-not-a-feature.md) | "One evidence file per case" is an evaluation self-check, never an input feature | Accepted |
| [0008](0008-llm-scope-and-cache.md) | Models only for intent and vision; pinned, cached as a .py module, rules-only fallback without keys | Accepted |
| [0009](0009-support-category-from-activity.md) | Untagged support (and analytics) category from the activity event type; state only from evidence | Accepted |
| [0010](0010-deletion-pending-is-present.md) | A DELETION_PENDING account is present under rule_01: remaining + delete + verify (unlabeled) | Accepted |
| [0011](0011-legal-hold-retain.md) | Pre-audit legal_hold_N records get VERIFY_RECORD_PRESENT, never delete (unlabeled) | Accepted |
| [0012](0012-unobservable-categories.md) | Cache, email-log, telemetry and unlinked marketing categories produce no steps; logged as not observable | Accepted |
| [0013](0013-typesafe-evaluation-only.md) | The TypeSafe System One (Jev) model is evaluation-only, plus an optional log-only intent shadow vote | Accepted |
