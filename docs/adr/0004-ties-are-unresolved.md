# ADR 0004 — Tied candidates are omitted and logged, with no case_id-order tie-break

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes now. Earlier, `docs/03` proposed the tie-break "as a flagged last resort"; that is superseded.

## Question

When two or more candidate links remain equally plausible after the grounded steps, what is emitted?

## Context

- A tie-break on case_id order reached 23/32 on samples, but with 1 wrong pick (case_23). It relies on a generator artifact, the case numbering, not on any evidence.
- Grounded steps alone give 19/32 with 0 wrong.
- On eval: **136 of 508 deletion cases** stay tied, in 65 groups (55 pairs, 8 triples, 2 partial).

## Recommendation

Omit the step and record an *unresolved link*. Expected cost: about 136–160 gold-style steps (about 5% of about 3,050) plus about 110 VERIFY_RECORD_ANONYMIZED steps for already-anonymized analytics (`docs/03` §6).

## Decision

**Never attribute data to a person without a grounded link.** Ties produce no step, and each is written to the run log as `UNRESOLVED_LINK(case, candidates)`.

## Consequences

- Step recall drops by about 5%, while precision stays clean.
- Case status is not driven by the unresolved step alone (see ADR 0006 and the A24 note in `docs/03` §6).

## Rejected alternatives

- **case_id-order tie-break:** an artifact, and close to the forbidden case-family shortcut (AGENTS.md §6.7).
- **Emitting all tied candidates:** that attributes other people's records to this subject.
