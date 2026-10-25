# Blind silver audit A: case_431, case_247, case_499, case_460

Sources: dataset/ only (CSVs, evidence/**, PNGs viewed, PDFs via pdftotext). No output.csv, code/, docs/, runs/, sample_output.csv used.
Visibility rule: manifest captured_at <= audit_at (equality treated as visible).

---

## case_499 (daniel.m47291@outlook.com; reported COMPLETE 2026-01-20T08:00Z; audit_at 2026-02-13T08:00Z)

**Intent:** "I would like the account associated with this address to be erased." -> authorises deletion.

**Subject:** user_497 Daniel Morgan (user_identities.csv). Request email is HISTORICAL (user_audit_log.csv audit_71, 2025-10-15: daniel.m47291@outlook.com -> daniel.m472@outlook.com).
- emails: daniel.m47291@outlook.com (old), daniel.m472@outlook.com (current)
- sha256: 0c3d36a5053b01823de8a8808f0d6ab12834b676d9347d60e9ad58c5e096de73 (old, matches audit_72), 9783ee79c48521a5a5f133185c1af4d1e5f4f5ac616504c1487409a43f765ad7 (current)
- phone: +1 (415) 555-0197

**Visible files:** evidence_62 (01-29), evidence_49 (01-31), evidence_48 (02-03), evidence_47 (02-08), evidence_63 (02-13T07:43:27), evidence_46 PNG (02-13T08:00, object storage listing; no subject identifiers).

**Hits:** only evidence_63 databases/customer_data_inventory_20260213.sql:19
`INSERT INTO customer_profiles VALUES ('account_3626', NULL, NULL, 'daniel.m47291@outlook.com', NULL, NULL, 'DELETION_PENDING', '2026-02-13T07:43:27Z');`
No hit for current email, either hash, phone, user_497 or name in any visible file.

| system_id | resource_id | state at audit_at | proof | category | required |
|---|---|---|---|---|---|
| account_service | account_3626 | PRESENT (old email exposed, DELETION_PENDING) | evidence_63 customer_data_inventory_20260213.sql:19 | USER_PROFILE (no retained records for user_497 visible -> not tombstone) | DELETE |

Activity claims: activity_229 (2026-01-20T07:04:40Z) DELETE_RECORD account_3626 SUCCESS; activity_234 (08:44:32Z) SYNC_RECORD account_service->account_replication_cluster account_3626 "final checkpoint". The snapshot contradicts the SUCCESS claim.

**Expected status: INCOMPLETE**

| # | phase | operation | system_id | resource_id | evidence_id |
|---|---|---|---|---|---|
| 1 | FINDING | REPORT_REMAINING_RECORD | account_service | account_3626 | evidence_63 |
| 2 | REMEDIATION | DELETE_RECORD | account_service | account_3626 | "" |
| 3 | VERIFICATION | VERIFY_RECORD_ABSENT | account_service | account_3626 | "" |

**Linking:** reported_at 2026-01-20T08:00Z shared by case_497 (COMPLETE), case_498 (PARTIAL), case_499 (COMPLETE). Deletes in 06:30-07:30: account_5281 SUCCESS 06:55 (activity_228), account_3626 SUCCESS 07:04 (activity_229), account_282 PARTIAL 07:15 (activity_230 -> case_498). account_445 SUCCESS 05:45 fits case_512 (reported 07:00). Result-matching alone leaves 5281/3626 ambiguous between case_497/499, but evidence_63:19 binds account_3626 to daniel.m47291 directly -> account_3626 is the subject's (high).

**Misses:** downstream after delete: analytics_6565 ANONYMIZE SUCCESS (activity_231) - owner ambiguous (case_497 or 499); evidence_63:23 shows it with all identifiers NULL, so compliant either way (no step needed for INCOMPLETE). support_9075/search_6093 belong to valvarez255390 (evidence_63:29,35) -> case_498. Replication SYNC (activity_234) could be read as REPORT_ACTIVE_DATA_FLOW, but "final checkpoint" suggests it ended and there is no data_flow resource; not flagged.

**Confidence:** high on status, high on steps. Open question: whether the grader expects a replication-related finding (unlikely).

---

## case_460 (parker.grace@gmail.com; reported NOT_STARTED 2026-02-08T12:00Z; audit_at 2026-03-05T12:00Z)

**Intent:** "submit a request to delete this account and its personal data" -> authorises deletion.

**Subject:** user_458 Grace Parker (user_identities.csv), no audit-log changes.
- email parker.grace@gmail.com; sha256 2a281960e606f04db81aa827a2400f2c9eb6ed91248d7031b586a02928272b7c; phone +44 7700 900458.

**Visible files:** evidence_62, 49, 48, 47, 63, 46, 64 (02-18), 45 (02-23), 65 (02-28), 44 (03-02), 43 (03-05T12:00 = audit_at).

**Hits (evidence_43 databases/customer_data_reporting_replica_20260305.sql):**
- :20 / :53 audit_record_1369 security_audit_events subject_reference user_458 "account_deletion_reviewed"
- :31 / :64 legal_hold_5622 retained_order_records subject_reference user_458, retained_until 2033-12-31, reason payment_dispute_and_tax_record
- :39 / :72 support_4146 support_conversations subject_reference user_458, message_text "Please send the delivery update to parker.grace@gmail.com. The affected order includes: Ceramic coffee set."

| system_id | resource_id | state at audit_at | proof | category | required |
|---|---|---|---|---|---|
| account_service | account_5167 | PRESENT (delete FAILED; no later evidence of removal) | system_activity.csv activity_475 (2026-02-08T10:59:54Z, DELETE_RECORD ... FAILED) | USER_PROFILE (see tombstone note) | DELETE |
| support_platform | support_4146 | PRESENT, email exposed in message_text (primary + reporting replica) | evidence_43 :39, :72; activity_480 REDACT FAILED | SUPPORT_MESSAGE (order context) | REDACT |
| security_service | audit_record_1369 | PRESENT | evidence_43 :20, :53 | SECURITY_AUDIT_LOG | RETAIN (compliant) |
| legal_service | legal_hold_5622 | PRESENT, hold active to 2033 | evidence_43 :31, :64; activity_478 RETAIN SUCCESS | LEGAL_HOLD_RECORD | RETAIN (compliant) |

**Expected status: INCOMPLETE**

| # | phase | operation | system_id | resource_id | evidence_id |
|---|---|---|---|---|---|
| 1 | FINDING | REPORT_REMAINING_RECORD | account_service | account_5167 | activity_475 |
| 2 | FINDING | REPORT_EXPOSED_PII | support_platform | support_4146 | evidence_43 |
| 3 | REMEDIATION | REDACT_RECORD | support_platform | support_4146 | "" |
| 4 | REMEDIATION | DELETE_RECORD | account_service | account_5167 | "" |
| 5 | VERIFICATION | VERIFY_RECORD_REDACTED | support_platform | support_4146 | "" |
| 6 | VERIFICATION | VERIFY_RECORD_ABSENT | account_service | account_5167 | "" |

(Ordering of findings/remediation between account and downstream copy is a judgement call: downstream support copy before source account.)

**Linking:** reported_at 2026-02-08T12:00Z shared by case_458 (PARTIAL), case_459 (COMPLETE), case_460 (NOT_STARTED). Deletes 10:30-11:30: account_077 PARTIAL 10:50 (activity_474 -> case_458), account_5167 FAILED 10:59 (activity_475 -> case_460), account_5892 SUCCESS 11:10 (activity_476 -> case_459). Unique by result -> account_5167 (medium-high; account_5167 appears in no evidence file at all).

**Misses:** downstream burst: analytics_5221 ANONYMIZE SUCCESS (activity_477; owner ambiguous; evidence_43:16 shows identifiers NULL -> compliant), legal_hold_5622 RETAIN (user_458, retained), backup_1140 CHECK_RESTORE_ACCESS "can still be restored" (activity_479) - subject_reference d.romero12@gmail.com (evidence_43:29) = case_459's subject, NOT ours; support_4146 REDACT FAILED (ours, included).

**Confidence:** medium. Open questions: (a) account_5167 tombstone vs delete: user_458 has retained records (audit_record_1369, legal_hold_5622) referencing user_id, so rule_15 ACCOUNT_TOMBSTONE -> REDACT_RECORD / VERIFY_RECORD_REDACTED could be the intended treatment instead of DELETE; (b) whether VERIFY_RECORD_PRESENT for audit_record_1369 and legal_hold_5622 is expected in an INCOMPLETE row (contract says verification covers remediated records, so omitted); (c) finding evidence for the account is an activity_id because no visible file names account_5167.

---

## case_431 (lucas-almeida@proton.me; reported NOT_STARTED 2026-03-02T08:00Z; audit_at 2026-03-20T08:00Z)

**Intent:** "request for permanent account deletion" -> authorises deletion.

**Subject:** user_429 Lucas Almeida (user_identities.csv), no audit-log changes.
- email lucas-almeida@proton.me; sha256 99b86a480d2eb03db56490ff0d7320bb998d2525cd83141f97edb15eb32250bf; phone +55 31 95698-0675.

**Visible files:** all of case_460's plus evidence_42 PNG (03-10, user_17 retained reference - unrelated), evidence_66 (03-10), evidence_67 (03-10), evidence_41 (03-15), evidence_68 (03-20T07:23:49).

**Hits (evidence_68 records/service_resource_export_20260320_072349.json):**
- :199-209 search_7427 index query "lucas-almeida@proton.me", total 1, observed 2026-03-20T05:46:08Z
- :274-281 support_3615 requester_email "lucas-almeida@proton.me", message_excerpt "Customer contacted support about account access.", observed 07:23:27Z

| system_id | resource_id | state at audit_at | proof | category | required |
|---|---|---|---|---|---|
| account_service | account_6101 | PRESENT (delete FAILED) | activity_799 (2026-03-02T07:08:46Z DELETE_RECORD FAILED) | USER_PROFILE | DELETE |
| search_service | search_7427 | PRESENT with email | evidence_68:199-209; activity_808 DELETE FAILED | SEARCH_INDEX_ENTRY | DELETE |
| support_platform | support_3615 | PRESENT with requester_email | evidence_68:274-281; activity_806 DELETE_RECORD FAILED | SUPPORT (worker op = DELETE -> treated as SUPPORT_ATTACHMENT-like, see note) | DELETE |

**Expected status: INCOMPLETE**

| # | phase | operation | system_id | resource_id | evidence_id |
|---|---|---|---|---|---|
| 1 | FINDING | REPORT_REMAINING_RECORD | account_service | account_6101 | activity_799 |
| 2 | FINDING | REPORT_REMAINING_RECORD | search_service | search_7427 | evidence_68 |
| 3 | FINDING | REPORT_REMAINING_RECORD | support_platform | support_3615 | evidence_68 |
| 4 | REMEDIATION | DELETE_RECORD | search_service | search_7427 | "" |
| 5 | REMEDIATION | DELETE_RECORD | support_platform | support_3615 | "" |
| 6 | REMEDIATION | DELETE_RECORD | account_service | account_6101 | "" |
| 7 | VERIFICATION | VERIFY_RECORD_ABSENT | search_service | search_7427 | "" |
| 8 | VERIFICATION | VERIFY_RECORD_ABSENT | support_platform | support_3615 | "" |
| 9 | VERIFICATION | VERIFY_RECORD_ABSENT | account_service | account_6101 | "" |

**Linking:** reported_at 2026-03-02T08:00Z shared by case_431 (NOT_STARTED) and case_432 (PARTIAL). Deletes 06:30-07:30: account_6489 PARTIAL 06:57 (activity_798 -> case_432), account_6101 FAILED 07:08 (activity_799 -> case_431). account_3075/9120 SUCCESS and account_4921 FAILED (07:47-08:07) fit case_416/418/417 (reported 09:00). Unique -> account_6101 (medium-high; not named in any file).

**Misses:** burst after delete: support_3615 (ours), export_9343 & search_3844 (anair9899 = case_432, evidence_68:91,181), search_7427 (ours), then data_flow_1412 CHECK_DATA_FLOW "remains enabled" (activity_810, 09:38), search_8686/6600/5479 DELETE FAILED and support_9464 REDACT FAILED (activities 812-815). These later rows interleave with case_416-418's window and no visible (<= audit_at) file names their owner -> ambiguous, not attributed. If data_flow_1412 were lucas's, steps REPORT_ACTIVE_DATA_FLOW / DISABLE_DATA_FLOW (first in remediation) / VERIFY_DATA_FLOW_DISABLED would be needed.

**Confidence:** medium. Open questions: (a) support_3615 treatment: the support_records row has the same message_excerpt as support_9075 (which the worker REDACTs for case_498), so text gives no category; the worker's DELETE op suggests delete (REPORT_REMAINING_RECORD/DELETE/VERIFY_ABSENT); alternative is SUPPORT_MESSAGE -> REPORT_EXPOSED_PII/REDACT_RECORD/VERIFY_RECORD_REDACTED; (b) attribution of data_flow_1412 and 09:52-10:11 failures.

---

## case_247 (rina.y488481@outlook.com; reported COMPLETE 2026-06-06T12:00Z; audit_at 2026-06-18T12:00Z)

**Intent:** "I would like the account associated with this address to be erased." -> authorises deletion.

**Subject:** user_245 Rina Yamamoto. Request email is HISTORICAL (audit_187, 2026-02-18: rina.y488481@outlook.com -> rina.y4884@outlook.com; audit_188 hash change).
- emails: rina.y488481@outlook.com (old), rina.y4884@outlook.com (current)
- sha256: 003d21e360feed836331c853166c32211837d855c66eed79752ea1705b3a84a1 (old), d6b84ad059ecee85f145aab531352165555ee75b07d761951c9566ea3d2739b5 (current)
- phone +81 90 3677 8075

**Visible files:** evidence_23..49 with captured_at <= 06-18T12:00 (incl. evidence_27 PDF, PNGs 23/28/32/42/46 - none name the subject), evidence_62..78.
"yamamoto" hits are other people (syamamoto4983@fastmail.com evidence_44/65; yamamoto.keiko@icloud.com evidence_76:46) -> not subject.

**Hits (evidence_78 databases/customer_data_inventory_20260618.sql, snapshot 2026-06-18T11:44:03Z):**
- :19 `('account_2981', NULL, NULL, 'rina.y488481@outlook.com', NULL, NULL, 'DELETION_PENDING', '2026-06-18T11:44:03Z')`
- :32 `('search_9473', NULL, NULL, 'rina.y488481@outlook.com', NULL, NULL, 'customer_directory_v3', '2026-06-18T10:15:22Z')`

| system_id | resource_id | state at audit_at | proof | category | required |
|---|---|---|---|---|---|
| account_service | account_2981 | PRESENT with old email | evidence_78:19 (contradicts activity_2236 SUCCESS) | USER_PROFILE (no retained records for user_245 visible) | DELETE |
| search_service | search_9473 | PRESENT with old email | evidence_78:32 (contradicts activity_2245 SUCCESS) | SEARCH_INDEX_ENTRY | DELETE |

**Expected status: INCOMPLETE** (reported COMPLETE is false)

| # | phase | operation | system_id | resource_id | evidence_id |
|---|---|---|---|---|---|
| 1 | FINDING | REPORT_REMAINING_RECORD | account_service | account_2981 | evidence_78 |
| 2 | FINDING | REPORT_REMAINING_RECORD | search_service | search_9473 | evidence_78 |
| 3 | REMEDIATION | DELETE_RECORD | search_service | search_9473 | "" |
| 4 | REMEDIATION | DELETE_RECORD | account_service | account_2981 | "" |
| 5 | VERIFICATION | VERIFY_RECORD_ABSENT | search_service | search_9473 | "" |
| 6 | VERIFICATION | VERIFY_RECORD_ABSENT | account_service | account_2981 | "" |

**Linking:** reported_at 2026-06-06T12:00Z shared by case_245 (PARTIAL), case_246 (PARTIAL), case_247 (COMPLETE); case_262 at 11:00 (PARTIAL). Deletes 10:00-11:30: account_5072 PARTIAL 10:07, account_2981 SUCCESS 10:46 (activity_2236), account_2481 PARTIAL 10:57, account_1264 PARTIAL 11:08. Only SUCCESS -> account_2981, also directly bound by evidence_78:19 (high).

**Misses:** burst: search_2228 FAILED (activity_2240) = oliveira.camila user_260 (evidence_24 read_replica_20260613.sql:31) -> case_262; support_579 & search_2725 = azulu6965 (evidence_78:27,37) -> case_246; analytics_4010 = nana-appiah (evidence_78:21) -> case_245; search_9473 ours; activity_2242 replication "final checkpoint" for account_2981 (same pattern as case_499, not flagged). Nothing unattributed.

**Confidence:** high on status; high on steps (ordering of the two remediation steps is the only judgement call).

---

## Summary
- case_431: INCOMPLETE (account_6101 [activity_799], search_7427 + support_3615 [evidence_68]) - medium
- case_247: INCOMPLETE (account_2981 + search_9473 [evidence_78]) - high
- case_499: INCOMPLETE (account_3626 [evidence_63]) - high
- case_460: INCOMPLETE (account_5167 [activity_475], support_4146 exposed PII [evidence_43]; retained audit_record_1369, legal_hold_5622) - medium
