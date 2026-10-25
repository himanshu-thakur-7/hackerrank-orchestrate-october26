# ADR 0016 — A resource seen only absent before the request belongs to an earlier lifecycle

- **Status:** Proposed (T10); adopted provisionally.
- **Related:** ADR 0003 (activity is a linkage key), ADR 0004 (no guessing), ADR 0006 (unproven end states).

## Question

The subject's own identifier links a resource only through observations that **predate `requested_at`** and show it **ABSENT**. Is that resource part of this deletion?

## Context (T10 investigation of the one extra resource on dev)

- case_17 (leonie.g9352@outlook.com, requested 2026-08-19, audit 2026-09-15). `evidence_67` (`resource_lookup_trace_20260310_061801.log`, captured 2026-03-10) line 3: `profile_lookup_completed resource_id=account_6523 rows=0 http_status=404`, joined by trace to `lookup_key=leonie.g9352@outlook.com`.
- That trace is the readback for the **same subject's earlier request**, eval case_46 (requested 2026-03-08, audit 2026-03-11). It is a different lifecycle.
- `activity_3850` (2026-09-15T09:56) is a SUCCESS delete of `account_6523`, "submitted primary profile". It sits inside **case_03's** account window, not case_17's. So in September the id belongs to another lifecycle: the March 404 says nothing about it now.
- Gold for case_17 has `account_4092` (the activity-linked account) and **not** account_6523.
- Measured: on the 32 samples this pattern occurs once (this extra); every gold resource has a link at or after `requested_at`. On the 518 eval requests it occurs **0 times**, so the rule changes no eval row today.

## Decision

Drop a resource whose **every** grounded link is observed before `requested_at` **and** shows it ABSENT. Log it as `STALE_LINK(..., ADR 0016)` with the latest link.

A pre-request **PRESENT** sighting still links: that data existed and may remain.

## Consequences

- No stale ids (possibly reused later) receive verification steps.
- The rule is narrow. A later observation of the same resource for the subject brings it back into scope.

## Rejected alternatives

- **Keep it** (VERIFY_RECORD_ABSENT): this verifies an id from another lifecycle that is reused later. It is not this request's data.
- **Drop every pre-request link:** this would also drop data seen present before the request, which a deletion must cover.
