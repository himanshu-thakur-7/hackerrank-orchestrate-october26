# ADR 0013 — The TypeSafe "System One" (Jev) decision model is for evaluation only

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes

## Question

Where may the Jev decision model (TypeSafe System One) be used?

## Context

- Principles: deterministic output, and models only for language and vision (ADR 0008).
- I have no first-hand knowledge of this product. It is recorded as specified by the owner; the key is `TYPESAFE_API_KEY`, from the environment only.

## Recommendation and decision

- Use it **in evaluation only**, as a judge or reviewer of outputs.
- Optionally run it as a **log-only shadow vote on request intent**, recorded beside the primary intent decision.
- **It never changes a row** of `output.csv`.

## Consequences

- Disagreements between the shadow vote and the primary intent are listed in the evaluation report for review.

## Rejected alternatives

- **Using it as a primary decider:** non-deterministic, and outside the "language and vision only" scope.
