# ADR 0014 — Absence by omission (Coverage) is weak evidence; it never overrides a positive observation

- **Status:** Accepted by the owner for now (2026-10-25, relayed); evidence-backed
- **Amends:** docs/03_DESIGN.md §2 ("Coverage … ABSENT then means covered and not listed") and the design table "Coverage only for formats proven exhaustive"

## Question

When a snapshot covers a system or table but does not list a resource, does that prove the resource ABSENT at the snapshot time, even if an earlier source showed it PRESENT?

## Context: measured during T06 (`scratch/t06_bundle_coverage_probe.py`)

The test covered every sample gold resource the grader requires to still **exist** at `audit_at`: findings, plus VERIFY_RECORD_PRESENT / REDACTED / ANONYMIZED. 56 such resources had an observation at or before `audit_at`.

**Non-empty bundle collections** contradict gold in **5** cases. `evidence_51` (09-15T12:00) lists 2 `security_service` events for its own subjects. Treated as exhaustive, it would make audit_record_3737 (case_21), 451 (case_25), 5416 (case_26), 3830 (case_27) and 9265 (case_28) ABSENT, yet gold verifies them PRESENT.

**Empty bundle lists** contradict gold in **1** case. `evidence_51` lists `customer_profiles: []` at 09-15T12:00. Gold case_24 requires account_5334 REMAINING (cited `evidence_92`, PRESENT at 09:41). Yet gold case_31 uses the *same* empty list to verify account_4857 ABSENT.

**SQL inventory coverage** (snapshot_scope) contradicts gold in **1** case. `evidence_90` (09-05) scopes `account_service` and omits account_005. Gold case_05 (audit 09-08) requires account_005 REMAINING, because the failover replica `evidence_54` (09-02) still holds it.

**Every gold absence proven only by omission** has **no** positive observation anywhere before audit:

- account_001, 002 and 004 via `evidence_54`;
- account_4857 via `evidence_51`.

The other 6 gold absences are **explicit** negatives (404 / rows=0), and explicit negatives are never older than a positive (0 contradictions).

**Conclusion.** A snapshot lists the records relevant to *its* subjects or *its* copy (primary vs replica), not the whole store. Omission is therefore evidence of absence only when nothing visible says otherwise.

## Decision

1. **Explicit observations are strong** and follow latest-wins at or before the cutoff. Explicit observations are 404, NOT_FOUND, rows=0, total_hits=0, archive_present=false, and any listed row.
2. **Coverage (absence by omission) is weak.** It yields ABSENT for a resource **only if no visible observation shows it present** (any file, any copy, at or before the cutoff). It never overrides a PRESENT/ACTIVE/RESTORABLE/BLOCKED/DISABLED observation.
3. Loaders still emit Coverage for SQL table dumps, inventory snapshot_scope, and bundle collections (empty and non-empty). The weakness is enforced in one place, `CaseView.state`.
4. Register-style rows, such as `operational_record_history` in bundles and record-list registers, never emit Coverage. They are a history of checks, not a listing.

## Consequences

- Fixes the 7 contradictions above (gold-consistent on all 56 must-exist resources and all 10 cited absences).
- A deleted resource whose only post-deletion evidence is omission stays PRESENT if an older sighting exists. That favours "remaining" (INCOMPLETE) over false compliance, which matches "absence of proof is not proof of absence".
- Replica drift needs no special handling: a primary-only snapshot cannot erase a replica sighting.

## Rejected alternatives

- **Exhaustive coverage per (system, table):** 7 gold contradictions.
- **Subject-scoped coverage** (absence only for subjects the snapshot mentions): fails `evidence_54`, which proves accounts 001, 002 and 004 absent while mentioning none of their owners.
- **Dropping coverage entirely:** loses the 4 gold absences proven only by omission (case_01, 02, 04, 31).
