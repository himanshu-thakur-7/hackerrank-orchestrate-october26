# Silver-label audit (T16)

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

**Probable misses: 2 cases** (case_374, case_362), each one `VERIFY_RECORD_ANONYMIZED` on an analytics record linkable only through activity bursts. That is the loss class the ledger's step ceiling already accounts for (~0.22 per case). Cases 7–20 are left for the next session, using the same checklist.
