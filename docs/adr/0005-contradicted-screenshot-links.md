# ADR 0005 — Reject an identity link that the screenshot contradicts

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes

## Question

A `LINK_RESOURCE_IDENTITY` activity claims a resource belongs to a person, but the screenshot captured 7 minutes earlier shows a different identity. Which wins?

## Context

- All 12 link rows land exactly 7 minutes after a screenshot or PDF capture (`docs/02b` §3).
- 9 are consistent with the artifact. **activity_4008** claims `marketing_001 → kwame-mensah@proton.me / user_09`, but `evidence_60` shows "Soo-jin Park, sj.park@naver.com, +82 10-5837-9451", who is no known user (eval case_63).
- activity_4007 (case_61) is unverifiable: the screen shows a file name and no person.

## Recommendation

Evidence over claims: when what is visible contradicts the claim, reject the claim.

## Decision

**General rule:** if the artifact a link refers to shows a different person (a different name, email or phone that resolves to someone else or to no known user), the link is **rejected**. A link the artifact cannot confirm *or* refute (activity_4007) is a claim without corroboration, and is handled like any other unconfirmed link (ADR 0006).

## Consequences

- case_63 gets no `marketing_001` step for user_09.
- The vision extractor must output the visible identifiers, so the rule can be checked automatically.

## Rejected alternatives

- **Trusting the catalog link:** a claim overriding direct evidence.
- **Ignoring screenshots:** that loses 7 screenshot-only cases (data notes, correction to §5.4).
