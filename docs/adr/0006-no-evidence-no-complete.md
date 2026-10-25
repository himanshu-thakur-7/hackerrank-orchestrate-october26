# ADR 0006 — Unproven end states: a future VERIFY step only, never a finding citing an activity row

- **Status:** Accepted (owner ruling superseded by evidence), amended 2026-10-25
- **Supersedes:** the first version of this ADR, which reported an attempted-but-unproven resource as REPORT_REMAINING_RECORD citing the activity row

## Question

A resource is grounded-linked to the subject (ADR 0003, 0004), but no pre-audit evidence shows its end state (ADR 0002). What is emitted, and what does it do to the case status?

## Context

- AGENTS.md §6.5: "A deletion is `COMPLETE` only when every relevant copy has the required treatment …".
- AGENTS.md §6.6: "A finding must use the participant-visible `file_id`, `activity_id`, or `audit_id` that proves it." and "Treat activity logs, workflow statuses, and system messages as claims unless the available evidence establishes the resulting state."
- Measured on the 32 samples (session log, 2026-10-25):
  - **12/12** primary accounts with a FAILED or PARTIAL delete claim before `audit_at` are gold **VERIFY_RECORD_ABSENT only**, never a finding: case_02, 09, 13, 17, 19, 20, 23, 25, 26, 28, 29, 32.
  - About **6** of them (account_002, 3960, 5037, 410, 7012, 8858) have **no pre-audit evidence** either way.
  - **0** gold steps cite an `activity_id` or `audit_id`. Every cited ID is a `file_id`.
- A FAILED delete proves only that a delete was **attempted**. Citing it as proof of *presence* would treat a claim as a state, the mirror image of what ADR 0003 forbids.

## History

- **v1 (owner ruling):** report attempted-but-unproven as remaining (REPORT_REMAINING_RECORD citing the activity row + DELETE_RECORD + VERIFY_RECORD_ABSENT).
- I recommended against it with the numbers above, and the owner overturned v1.
- **Lesson:** a rule that contradicts gold-labelled evidence gets **amended, not defended**.

## Decision

1. **Unproven end state, attempted claim only.** A grounded-linked resource whose end state no evidence shows, and whose only signal is a FAILED or PARTIAL action claim, gets a **future VERIFY step only**. Example: `VERIFY_RECORD_ABSENT`, with `evidence_id = ""` and state per its rule. It is **never** reported as `REPORT_REMAINING_RECORD` (or any finding) citing an activity row.
2. **Case status comes from the other grounded findings.** The unproven resource neither creates a finding nor, on its own, forces INCOMPLETE.
3. **Never COMPLETE without per-resource evidence.** Every step in a COMPLETE case must cite evidence that shows the compliant state (AGENTS.md §6.3). Where a resource's state *could be observed*, i.e. a usable file covers it, that evidence decides.
4. **Nothing grounded means nothing emitted.** No link, or a tied link (ADR 0004), produces no step. It is logged as `UNRESOLVED_LINK` / `NOT_OBSERVABLE` (ADR 0012).

**Edge case (unlabeled; no sample has it).** If the case has no grounded finding, but some grounded-linked resource is unproven:

- The case **cannot** carry an uncited VERIFY step, because COMPLETE requires a citation on every step.
- The resource is therefore **omitted** and logged as `UNPROVEN(resource)`.
- The status is COMPLETE when every *emitted* verification is evidence-backed.

This follows "absence of proof is not proof of absence" in both directions, and is listed as an accepted risk in `docs/03_DESIGN.md`.

## Consequences

- No step anywhere cites an `activity_id` or `audit_id` as proof of state. Findings cite files only, which matches gold (0/all).
- In INCOMPLETE cases, unproven accounts appear as VERIFY_RECORD_ABSENT with empty evidence, matching the 12/12 sample pattern.
- Fewer false findings, and the status is driven by observed violations.

## Rejected alternatives

- **v1: report as remaining, citing the activity row.** Contradicts 12/12 gold and treats a claim as state.
- **Assume absent from a SUCCESS claim:** evidence over claims.
- **INCOMPLETE whenever anything is unproven:** turns absence of proof into proof of a violation.
