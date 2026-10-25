# ADR 0012 — Categories with no observable resource produce no steps

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes

## Question

CACHE_ENTRY and EMAIL_DELIVERY_LOG resources appear in **no evidence file**: there are 284 REFRESH_CACHE and 368 SEND_EMAIL activity rows only. PRODUCT_TELEMETRY has no resource at all. MARKETING_PROFILE appears only as `marketing_001` via a contradicted link (ADR 0005). Should steps be emitted?

## Context

- `docs/02` §7.1: 0 tagged units for CACHE_ENTRY, EMAIL_DELIVERY_LOG, PRODUCT_TELEMETRY and MARKETING_PROFILE, and no sample label for any of them.

## Recommendation and decision

**No steps.** There is no grounded link to a person, and no observable state. Each is logged as `NOT_OBSERVABLE(category)`.

## Consequences

- If gold expects cache or email-log steps, they are lost. That is accepted under "never attribute without a grounded link".

## Rejected alternatives

- **Inferring cache or email-log records from activity bursts:** these are claims about unobservable stores.
