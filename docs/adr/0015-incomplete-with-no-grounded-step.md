# ADR 0015 — A deletion with nothing grounded to report is INCOMPLETE with `[]`

- **Status:** Proposed (needs owner ratification). Adopted provisionally in T09.
- **Amends:** the T01 L0 gate rule "only NOT_APPLICABLE may be []", which was my reading, not a quoted rule.

## Question

The request authorises deletion, but no grounded resource is visible at `audit_at`. Either the subject's identifiers appear only in files captured later, or only in images/PDFs not yet loaded, or the resource needs a link that is not resolved. What row is written?

## Context

- PS:91 requires `[]` for NOT_APPLICABLE. It does not say an INCOMPLETE row must carry steps: "For `INCOMPLETE`, include findings, the complete remediation plan, and the checks that must pass afterward" describes what to include when there is something to include.
- `docs/03_DESIGN.md` Stage 2 already writes UNRESOLVED_SUBJECT as "INCOMPLETE with no steps". ADR 0006 §4 says "Nothing grounded means nothing emitted". The T01 gate contradicted both.
- T09 measurement: **10 eval cases** (case_33, 35, 39, 45, 50, 52, 53, 55, 61, 63) and 4 samples (case_01, 02, 04, 07) end with no grounded step today. Most of them overlap the "subject's identifiers only in post-audit files" set (`docs/02` §5.4) or need T10/T12.
- COMPLETE is impossible: every COMPLETE step must cite proving evidence.
- NOT_APPLICABLE is wrong: the request does authorise deletion.
- Inventing a step (a guessed account id, or an activity-cited finding) breaks ADR 0004 and 0006.

## Decision

Write `INCOMPLETE` with `[]`, and log `NO_GROUNDED_STEP` in the case trace. The L0 gate accepts the row and reports a counted warning `L0.empty_incomplete` naming the cases. `COMPLETE` with `[]` stays a violation.

## Consequences

- The output stays honest: no evidence, so no compliance claim, and no fabricated step.
- The warning count is a progress metric for T10/T12. It should fall as linking and image/PDF loaders land.
- **Risk:** if the grader rejects INCOMPLETE `[]`, these rows score zero (as they would anyway) or invalidate the file. Reverting is a one-line change in `gate.py`. A safe fallback would then be needed (an open question for the owner).

## Rejected alternatives

- **COMPLETE `[]`:** a compliance claim without evidence.
- **Defaulting to `reported_status`:** that trusts a claim (AGENTS.md §6.5).
- **A placeholder step:** no resource id is grounded, so any step would be fabricated.
