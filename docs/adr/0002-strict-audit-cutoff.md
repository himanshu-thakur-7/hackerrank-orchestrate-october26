# ADR 0002 — Strict cutoff: only files captured at or before audit_at

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes (this was the default proposed in data notes §5.3, A23)

## Question

May evidence captured after `audit_at` be used for anything? That includes identity links, retained-record IDs, and pre-audit sub-snapshots inside a file whose manifest capture time is later.

## Context

- AGENTS.md §6.2: "Use only information available at or before `audit_at` … Evidence created later must not change the answer." §6.6: "Never cite … an evidence item captured after the case's `audit_at`."
- The samples never cite a post-audit file. Every cited file is captured at or before `audit_at`, and equal in 7 cases, so the boundary is **inclusive** (§2.6).
- `evidence_02` (manifest 09-17) contains sub-snapshots dated 09-09 and 09-15. Using them for linking would have resolved sample case_25/case_26, moving account recovery from 19/32 to 21/32 (`docs/03` §2).
- `evidence_02` also shows a post-audit resurrection of `account_3866`, which sample case_27 (COMPLETE) correctly ignores.

## Recommendation

File-level exclusion by manifest `captured_at`, inclusive (`<=`), for both citation and linkage. The cost is 2 sample hits; the gain is a single, auditable rule with no "partly usable file" exceptions.

## Decision

A file is usable for a case **only if `captured_at <= audit_at`**. A file captured later is invisible to that case, for every purpose, including its earlier sub-snapshots. Activity rows are likewise used only if `event_time <= audit_at`.

## Consequences

- Account recovery on samples stays at 19/32 grounded (A23 closed).
- 3 legal-hold cases and several screenshot-only links are dropped (ADR 0011, data notes §7.6).
- The rule is simple to test: every cited `evidence_id` must have `captured_at <= audit_at`.

## Rejected alternatives

- **Using sub-snapshots for linking but not citing:** +2 sample hits, but it lets later files influence the answer.
- **Per-record timestamps inside files:** fragile across the roughly 15 file schemas.
