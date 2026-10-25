# Silver-label audit (T16)

> **This is an evidence-based review, not gold.** Neither the auditors nor I have labels for evaluation cases; a disagreement is resolved against the raw evidence and our ADRs, and an agreement is only as good as the shared reading of that evidence.

These are blind hand checks of evaluation cases against the **raw evidence**, with no gold labels involved. The sample comes from `code/evaluation/silver.py`: 20 cases, stratified by loss-ledger reason, drawn with `random.Random(20261025)`. The first 6 were checked by hand on 2026-10-25.

## The 20 cases

| # | Case | Stratum (loss-ledger reason) | Engine status |
| --- | --- | --- | --- |
| 1 | case_374 | fully grounded:COMPLETE | COMPLETE |
| 2 | case_362 | fully grounded:COMPLETE | COMPLETE |
| 3 | case_86 | fully grounded:COMPLETE | COMPLETE |
| 4 | case_164 | fully grounded:COMPLETE | COMPLETE |
| 5 | case_91 | fully grounded:INCOMPLETE | INCOMPLETE |
| 6 | case_355 | fully grounded:INCOMPLETE | INCOMPLETE |
| 7 | case_431 | fully grounded:INCOMPLETE | INCOMPLETE |
| 8 | case_247 | unlabeled:DELETION_PENDING (ADR 0010) | INCOMPLETE |
| 9 | case_499 | unlabeled:DELETION_PENDING (ADR 0010) | INCOMPLETE |
| 10 | case_460 | unlabeled:legal hold (ADR 0011) | INCOMPLETE |
| 11 | case_505 | unlabeled:legal hold (ADR 0011) | INCOMPLETE |
| 12 | case_205 | unresolved:tied | INCOMPLETE |
| 13 | case_347 | unresolved:tied | INCOMPLETE |
| 14 | case_191 | unresolved:tied | COMPLETE |
| 15 | case_33 | unresolved:window | INCOMPLETE |
| 16 | case_55 | unresolved:window | INCOMPLETE |
| 17 | case_531 | unproven | INCOMPLETE |
| 18 | case_63 | unlabeled:INCOMPLETE [] (ADR 0015) + contradicted | INCOMPLETE |
| 19 | case_61 | unresolved:catalog | INCOMPLETE |
| 20 | case_540 | resolved:non-deletion | NOT_APPLICABLE |

## Checklist (per case, from raw files only)

1. **Intent.** Read `request_text`. Does it authorise deletion? Look for negations and scope limits (marketing only, export, correction).
2. **Subject.** Find the request email in `user_identities.csv`, current or historical via `user_audit_log.csv`. List every identifier: emails, sha256 of each email, phones, user_id.
3. **Visible files.** Use only files with manifest `captured_at <= audit_at`.
4. **Independent discovery.** Grep every identifier in every visible text file; for PNGs and PDFs, read the image or the text. Write down each resource id on a matching line or record unit. Compare with the engine's resources (`--explain`).
5. **State per resource.** Take the latest line at or before `audit_at` for that resource, in every file, replica tables included. Note any later line that contradicts an earlier one.
6. **Policy.** Determine category and required end state. Check redacted or anonymized records for null PII.
7. **Steps.** Every finding cites the file whose line shows the violation. Every COMPLETE verification cites the latest file naming the resource. Remediation and verification in INCOMPLETE rows are uncited.
8. **Linking.** For an activity-linked account, check the window (0.5–1.5 h before `reported_at`), result↔status agreement, and that no other request claims the same delete.
9. **Misses.** Look at the deletion_worker rows after the account delete. Is a downstream resource visibly the subject's, but not emitted? Is it attributable, or ambiguous (interleaved bursts)?
10. **Verdict.** Agree, or disagree with a reason.

## Results for the first 6

| Case | Raw evidence (file:line) | Engine | Verdict |
| --- | --- | --- | --- |
| case_374 | evidence_70 (captured 04-14 05:40 ≤ audit 06:00): lines 12–13, trace `rb-033708-006`, lookup `obinna.okafor@gmail.com` → `account_8598 rows=0 http_status=404`; lines 40–41, `audit_record_5137 rows=1 subject_reference=user_372`. The only other file naming the subject is the 04-16 bundle, which is post-audit. | COMPLETE: VERIFY_ABSENT account_8598 + VERIFY_PRESENT audit_record_5137, both citing evidence_70; account also linked by activity_1112 (0.75 h) | **Agree.** Probable miss: an ANONYMIZE at +16 min for analytics_5779 *or* analytics_9394 (two rows in the same minute, both null-PII in evidence_70 lines 23/35). It is ambiguous, so omitted (ADR 0004). |
| case_362 | No visible file names account_507. evidence_33 (regional replicas, captured = audit 04-24 08:00) lines 27/63/101: `audit_record_8638 subject_reference user_360`. Its generic tables list account_service rows but not account_507. | COMPLETE: VERIFY_ABSENT account_507 citing evidence_33 (absence by omission, ADR 0014; nothing shows it present); account from activity_1438 (PARTIAL, 1.13 h) | **Agree, weakly grounded.** The absence rests on omission. Probable miss: `analytics_4273` (ANONYMIZE at +40 min, the only one before the next account delete; evidence_33 line 15 shows it with all PII null). This is the "unlinked anonymized analytics" loss class. |
| case_86 | evidence_08 (captured = audit 09-06 07:00) line 1: `account_8473 FOUND` (08-31). Line 8: `account_8473 NOT_FOUND` (09-06). Line 29: `audit_record_5580 FOUND subject user_84`. | COMPLETE: VERIFY_ABSENT account_8473 (latest line 8) + VERIFY_PRESENT audit_record_5580, citing evidence_08 | **Agree.** The in-file ordering FOUND → NOT_FOUND is handled. |
| case_164 | evidence_85 (07-28) lines 28–29: lookup `tomasz.stojanovic@outlook.com` → `account_9549 rows=0 404`; lines 40–41: `audit_record_6780 rows=1` for user_162. | COMPLETE: both verifications cite evidence_85; activity_2846 (0.99 h) agrees | **Agree.** analytics_6402 (ANONYMIZE +31 min) follows two interleaved account deletes (account_9549 and account_1837), so it is ambiguous and correctly omitted. |
| case_91 | evidence_08 lines 6 (`account_6075 FOUND`), 14 (`analytics_8539 IDENTIFIABLE`), 23 (`search_9156 FOUND`), 32 (`audit_record_8304 FOUND user_89`), 34 (`support_266 IDENTIFIABLE`), all for `mei.k952079@outlook.com`, captured at audit. | INCOMPLETE: 4 findings (account remaining, search remaining, analytics and support exposed), 4 remediations, 5 verifications | **Agree.** reported_status COMPLETE and SUCCESS claims are contradicted by the audit-time lines. The categories come from `record_type` tags. |
| case_355 | evidence_33 line 87: `customer_data_replica_eu_west` has `account_6539` with user_353, full name, `andres.r136@…`. It is absent from the primary (drift, docs/02 §5.2). Lines 19/55/93: `audit_record_1151 user_353`. | INCOMPLETE: REPORT_REMAINING account_6539 citing evidence_33; VERIFY_PRESENT audit_record_1151 (uncited) | **Agree.** This is the replica-only trap. |

**Disagreements with the engine: 0 of 6.** The independent raw grep found exactly the engine's identifier-linked resources in all 6 cases.

**Probable misses: 2 cases** (case_374, case_362), each one `VERIFY_RECORD_ANONYMIZED` on an analytics record linkable only through activity bursts. That is the loss class the ledger's step ceiling already accounts for (~0.22 per case). Cases 7–20 were audited blind; see below.

## Cases 7–20: blind audit by four independent sub-agents

Each auditor got **only** this checklist, its case ids and `dataset/` (plus the contract in AGENTS.md §6). They were not given output.csv, the engine code, `--explain`, the loss ledger, docs or gold. Each wrote its own expected resources, status and steps with file:line proof:

- [auditor_A.md](silver_audit/auditor_A.md): case_431, 247, 499, 460
- [auditor_B.md](silver_audit/auditor_B.md): case_505, 205, 347, 191
- [auditor_C.md](silver_audit/auditor_C.md): case_33, 55, 531
- [auditor_D.md](silver_audit/auditor_D.md): case_63, 61, 540

I then compared each result with the engine row.

| # | Case | Auditor expectation | Engine (before → after this audit) | Verdict |
| --- | --- | --- | --- | --- |
| 7 | case_431 | INCOMPLETE; search_7427 remaining; support_3615 still holds the email, **DELETE** (the worker ran DELETE_RECORD on it); account_6101 via the FAILED delete | INCOMPLETE; support_3615 was **REDACT** (category from a `message_excerpt` field) → now **DELETE** | **Engine bug, fixed.** My T08 "content" rule let a templated `message_excerpt` outrank the deletion_worker claim. ADR 0009 ranks only an *uploaded file* above the claim, and the activity type agrees with tags 31/31. Message text now ranks below the claim (regression test `test_message_text_does_not_override_a_delete_claim`). That changes 12 eval rows: case_71, 95, 131, 143, 179, 227, 251, 275, 347, 431, 443, 527. Samples are unchanged (0 diffs). |
| 8 | case_247 | INCOMPLETE; account_2981 and search_9473 remain (evidence_78 lines 19, 32), under the historical email | same | Agree |
| 9 | case_499 | INCOMPLETE; account_3626 DELETION_PENDING with the email (evidence_63 line 19) | same | Agree (ADR 0010) |
| 10 | case_460 | INCOMPLETE; support_4146 exposes the email (evidence_43 lines 39, 72) → REDACT; audit_record_1369 and legal_hold_5622 retained; account_5167 via the FAILED delete | same | Agree. The auditor asks whether account_5167 should become a tombstone (rule_15) because held records reference it. **Documented assumption:** a tombstone step needs a visible `identity_service` record; none is visible, so no tombstone step is emitted. |
| 11 | case_505 | INCOMPLETE; data_flow_5281 enabled, search_2591 present (evidence_47); legal_hold_2227 and audit_record_3441 retained; account tied (account_8136 / account_7244, shared with case_504) | same; account logged UNRESOLVED_LINK | Agree, tie included (ADR 0004). The auditor was unsure about uncited VERIFY_RECORD_PRESENT for retained records in INCOMPLETE rows. **Documented assumption**, backed by the samples: gold emits them (e.g. sample case_09, case_11). |
| 12 | case_205 | INCOMPLETE; data_flow_3530 enabled, search_540 present (evidence_20); audit_record_5023 retained; account tied (account_2399 / account_6726, shared with case_203) | same; tie logged | Agree |
| 13 | case_347 | INCOMPLETE; search_8185 present; support_9474 present, "very likely an attachment → DELETE" | support_9474 was REDACT → now **DELETE** | Same engine bug as #7, fixed by the same change |
| 14 | case_191 | COMPLETE; support_5049 redacted, data_flow_1611 disabled, backup_3010 blocked, audit_record_7493 present (evidence_83); analytics_5614 anonymized, linked **by worker timing only**; account tied (account_6608 / account_9317, shared with case_192) | COMPLETE with the 4 evidence-linked verifications; no analytics_5614; tie logged | Agree on status and the 4 resources. analytics_5614 is the known "anonymized analytics via bursts" loss. **Documented assumption** (ADR 0004): timing alone is not a grounded link. |
| 15 | case_33 | INCOMPLETE; export_1260 present (evidence_23 screen, "Ready"); **also export_1842** via the PDF statement NST-2026-0718-1842 (evidence_18) + catalog claim activity_4009; no account delete in the window | INCOMPLETE; export_1260 only; activity_4009 logged UNRESOLVED_LINK (unconfirmed) | **Documented assumption** (ADR 0005). The PDF is a customer statement and never prints `export_1842`; only the catalog claim maps it, by the shared "1842". The auditor also asks whether export_1260 belongs to the earlier request case_52 (same email). It is visible and still present at case_33's audit, so it stays in scope. |
| 16 | case_55 | INCOMPLETE; backup_9287 on the screen with the subject's email, "nothing shows restore access is blocked" → REPORT_RESTORE_RISK | INCOMPLETE `[]` (backup unproven: no restore flag shown) | **Documented assumption, flagged as a risk.** The engine requires positive evidence of restore access (restore_allowed / eligible / ACTIVE, as in every sample citation) before reporting a restore risk (ADR 0006: absence of proof is not proof). The auditor reads "no block shown" as a risk. If the owner prefers that reading, it is one line in `policy.treat` for BACKUP_ARCHIVE with state PRESENT. |
| 17 | case_531 | INCOMPLETE; backup_3382 restore_allowed=true (evidence_62 lines 104–108); account_3146 is the only FAILED delete in the window (activity_89), state unproven | same; account_3146 as an uncited future VERIFY_RECORD_ABSENT | Agree (ADR 0006: unproven → future verification only) |
| 18 | case_63 | **COMPLETE `[]`**; the catalog claim activity_4008 is rejected because evidence_60 shows Soo-jin Park; nothing else names the subject | INCOMPLETE `[]` (ADR 0015); REJECTED_LINK logged | Agree on the evidence (claim rejected, no step). The status differs: COMPLETE with no steps would claim compliance without evidence, which the contract and ADR 0015 rule out. **Documented assumption.** |
| 19 | case_61 | INCOMPLETE; object_19 (`delivery_confirmation_19.pdf`, evidence_46) remaining → DELETE, ownership from the catalog claim activity_4007 alone | INCOMPLETE `[]`; activity_4007 logged UNRESOLVED_LINK (unconfirmed) | **Documented assumption** (ADR 0005/0006): the screen shows a file name, no person and no object id. The auditor marked its own confidence medium. |
| 20 | case_540 | NOT_APPLICABLE (copy of invoices; "leave my profile and purchase history in place") | NOT_APPLICABLE | Agree |

**Summary for cases 7–20:**
- 9 agree on status and grounded resources.
- **1 engine bug**, found in two cases (#7, #13). It was fixed with a regression test and changed 12 eval rows.
- 5 documented assumptions where the auditor read the evidence more permissively, or asked an open question: #15 and #19 (unconfirmed catalog claims), #16 (backup with no restore flag), #18 (COMPLETE vs INCOMPLETE with `[]`), #14 (timing-only analytics).
- All 4 auditors confirmed every account tie the engine logs as unresolved (#11, #12, #13, #14). None found an account the engine missed.
