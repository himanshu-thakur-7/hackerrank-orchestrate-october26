# ADR 0003 — Recover account IDs from system_activity, unique candidate only

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes

## Question

Gold answers name primary `account_N` IDs that no pre-audit evidence ties to the email. May `system_activity` be used to recover them?

## Context

Measured in `docs/03` §1–2:

- **Timing.** In the generated regime (506/518 eval rows; `reported_at − requested_at` is exactly 24, 48 or 72 h), the gold account's `DELETE_RECORD → account_service` lands **0.75–1.23 h before `reported_at`**.
- **Result vs status.** Its `reported_result` matches `reported_status` in **23/23** (COMPLETE↔SUCCESS, NOT_STARTED↔FAILED, PARTIALLY_COMPLETE↔PARTIAL).
- **Hit rate.** Window + result + a pre-audit identity filter + global one-to-one assignment over all 550 requests gives **19/32 exact, 0 wrong**.
- No activity column names the user.

## Recommendation

Use it as a **linkage key** only. A candidate becomes the account only when it is the unique survivor of these steps:

1. window `[reported_at − 1.5 h, reported_at − 0.5 h]`;
2. `reported_result` matches `reported_status`;
3. no pre-audit evidence ties the account to another person;
4. global one-to-one elimination.

## Decision

As recommended. **Activity is a correlation key for linkage, never proof of state.** The account's state (present, absent, redacted) must still come from evidence (ADR 0006).

## Consequences

- About 360 eval cases get a unique account after the grounded steps; about 136 remain tied (ADR 0004).
- The 12 cases in the 42 h family (`docs/03` §1) get no account from this path.

## Rejected alternatives

- **Ignoring activity entirely:** most COMPLETE verifications would lose their account step.
- **Treating a SUCCESS delete as proof of absence:** violates "evidence over claims".
