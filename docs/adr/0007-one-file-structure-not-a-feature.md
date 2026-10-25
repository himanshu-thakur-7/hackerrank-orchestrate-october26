# ADR 0007 — "One evidence file per case" is never an input feature

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes

## Question

In 31/32 samples, every cited step uses one evidence file (`docs/02` §2.6). May the system exploit that, for example "pick the file, then attribute everything in it"?

## Context

- It is a dataset regularity, not a rule.
- `evidence_92` alone is cited by 9 sample cases (case_21, case_23 to case_30; corrected 2026-10-25 from a miscount of 10); a file holds many users and decoys.

## Recommendation

Use it only as an evaluation sanity check, for example to flag a case citing four files for review.

## Decision

**Never an input feature. Evaluation self-check only.**

## Consequences

- Each citation is chosen per resource as "the latest file at or before `audit_at` that names the resource" (`docs/02` §4.3).

## Rejected alternatives

- **"Choose a case file first":** that is a case-family shortcut (AGENTS.md §6.7).
