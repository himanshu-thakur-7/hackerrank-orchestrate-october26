# Blind silver audit B: case_505, case_205, case_347, case_191

Sources used: dataset/ only (CSVs, evidence files, PNGs viewed, PDFs via pdftotext). No output.csv, code/, docs/, runs/, sample_output.csv.
Search method: case-insensitive grep across all of dataset/evidence (plus pdftotext output of the 4 PDFs) for each email, the sha256 of each email, phone digits with optional separators, user_id with word boundaries, and name. Every hit was then filtered by manifest captured_at <= audit_at. All visible PNGs were viewed: object_storage_browser_20260213, deleted_account_reference_20260310 (user_17), backup_restore_console_20260429 (backup_9286-9291, other accounts), support_ticket_console_20260524 (Kofi Ageyman), customer_export_console_20260618 (export_1258-1261), analytics_profile_view_20260713 (Omar Darwish, user_20). None of them concerns any of the four subjects. The visible PDFs (legal_retention_register_20260529, account_history_report_20260718) also do not concern them (user_08..user_29 and user_18 only).

Policy (deletion_rules.csv): SEARCH_INDEX_ENTRY rule_03 DELETE; SUPPORT_MESSAGE rule_05 REDACT; SUPPORT_ATTACHMENT rule_06 DELETE; ANALYTICS_PROFILE rule_07 ANONYMIZE; SECURITY_AUDIT_LOG rule_12 RETAIN; LEGAL_HOLD_RECORD rule_13 RETAIN; BACKUP_ARCHIVE rule_14 RETAIN with restore blocked; ACCOUNT_TOMBSTONE rule_15 REDACT. A connector configuration (data_flow) that is enabled and selects the subject is an active recreation path, so it must be DISABLED.

---

## case_505: nana.a7986@zoho.com

- Request (deletion_requests.csv): requested 2026-01-26T07:00Z, reported PARTIALLY_COMPLETE at 2026-01-29T07:00Z, **audit_at 2026-02-08T07:00:00Z**.
- **Intent:** "Please begin the deletion process for the account using this email address..." This authorises deletion, with no negation or scope limit.
- **Subject:** user_503, Nana Addo (user_identities.csv:504). Email nana.a7986@zoho.com, sha256 54fd54401770470e66bcd78d1114413ad27f4f36f639a44a4ede4024122ee202 (computed, matches the email_hash column), phone +233 24 077 1311. user_audit_log.csv has no rows for user_503, so there are no historical identifiers.
- **Visible files:** evidence_62 (01-29), evidence_49 (01-31), evidence_48 (02-03), and evidence_47 `evidence/databases/customer_data_reporting_replica_20260208.sql` (captured 2026-02-08T07:00:00Z, exactly at audit_at, so it is visible). No visible PNG or PDF. Subject hits occur **only in evidence_47**.

### Resources

| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| integration_service | data_flow_5281 | ACTIVE: enabled, continuous_sync, subject_selector = subject email | evidence_47 reporting_replica_20260208.sql:28 (primary) and :60 (replica): `"subject_selector":"nana.a7986@zoho.com","enabled":true,"mode":"continuous_sync"`; activity_338 (01-29T07:40) "Active connector repopulated downstream resource search_2591" | data flow | DISABLED |
| search_service | search_2591 | PRESENT with name, email and customer_reference | evidence_47 :32 and :64 `"display_name":"Nana Addo","email":"nana.a7986@zoho.com","customer_reference":"user_503"`; activity_341 DELETE_RECORD FAILED | SEARCH_INDEX_ENTRY | ABSENT |
| legal_service | legal_hold_2227 | PRESENT, retained_until 2033-12-31 | evidence_47 :30 and :62 `"subject_reference":"user_503","order_reference":"ORD-20262227","retention_reason":"payment_dispute_and_tax_record"`; activity_336 RETAIN_RECORD SUCCESS | LEGAL_HOLD_RECORD | PRESENT (retain) |
| security_service | audit_record_3441 | PRESENT | evidence_47 :19 and :51 `"subject_reference":"user_503","event_name":"account_deletion_reviewed"` | SECURITY_AUDIT_LOG | PRESENT (retain) |
| account_service | (unknown: account_8136 or account_7244) | no visible evidence | see Linking | ACCOUNT_TOMBSTONE / profile | not determinable |

### Expected status: **INCOMPLETE**
The connector is active and repopulating search_2591, and the search entry is still present.

### Expected steps
1. FINDING REPORT_ACTIVE_DATA_FLOW / ACTIVE: integration_service, data_flow_5281, evidence_47
2. FINDING REPORT_REMAINING_RECORD / PRESENT: search_service, search_2591, evidence_47
3. REMEDIATION DISABLE_DATA_FLOW / DISABLED: integration_service, data_flow_5281, ""
4. REMEDIATION DELETE_RECORD / ABSENT: search_service, search_2591, ""
5. VERIFICATION VERIFY_DATA_FLOW_DISABLED / DISABLED: integration_service, data_flow_5281, ""
6. VERIFICATION VERIFY_RECORD_ABSENT / ABSENT: search_service, search_2591, ""
7. (probable) VERIFICATION VERIFY_RECORD_PRESENT / PRESENT: legal_service, legal_hold_2227, ""
8. (probable) VERIFICATION VERIFY_RECORD_PRESENT / PRESENT: security_service, audit_record_3441, ""

### Linking
reported_at is 2026-01-29T07:00Z PARTIAL, so the expected window is about 05:30-06:30 with a PARTIAL result.
- activity_334 (06:00:47) DELETE account_8136 PARTIAL
- activity_335 (06:11:31) DELETE account_7244 PARTIAL
- activity_333 (05:51:15) DELETE account_5394 SUCCESS belongs to case_503 (sami-nasser, COMPLETE, same reported_at).

**Ambiguous.** case_504 (oeze0067@fastmail.com, user_502) is also PARTIALLY_COMPLETE at 2026-01-29T07:00Z, so both PARTIAL deletes fit both cases. Neither account id appears in any evidence file, so the ambiguity does not change the steps.

### Probable misses
The burst after the account deletes is interleaved across three subjects:
- activity_336 legal_hold_2227: user_503
- activity_338 data_flow_5281 and activity_341 search_2591: user_503
- activity_339 support_2295: sami-nasser, case_503
- activity_340 export_3120: oeze0067, case_504

No other downstream resource is attributable to user_503. analytics_1558 (evidence_47:15) is fully nulled and not linked by any identifier or activity row.

**Confidence:** high on status and on findings 1-6. Medium on whether the retained-record VERIFY_RECORD_PRESENT steps (7-8) are expected in an INCOMPLETE row.

---

## case_205: nneka.o2286@zoho.com

- Request: requested 2026-06-25T09:00Z, reported COMPLETE at 2026-06-28T09:00Z, **audit_at 2026-07-08T09:00:00Z**.
- **Intent:** "Please treat this message as a request for permanent account deletion..." This authorises deletion.
- **Subject:** user_203, Nneka Okeke (user_identities.csv:204). Email nneka.o2286@zoho.com, sha256 ffa1044e024cf58e501246172fc06d2bf0e740483533b452553cf95d14f77122 (computed, matches), phone +234 803 640 1873. There are no audit-log rows. The "nneka-adeyemi81@proton.me" hits are a different person.
- **Visible files:** evidence files captured up to evidence_20 `evidence/databases/customer_data_read_replica_20260708.sql` (captured 2026-07-08T09:00:00Z, equal to audit_at). Subject hits occur **only in evidence_20**. Visible images and PDFs were checked and are unrelated.

### Resources

| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| integration_service | data_flow_3530 | ACTIVE (enabled continuous_sync, selector = subject email) | evidence_20 read_replica_20260708.sql:30 (primary) and :69 (replica) `"subject_selector":"nneka.o2286@zoho.com","enabled":true,"mode":"continuous_sync"`; activity_2571 (06-28T09:56) "Active connector repopulated downstream resource search_540" | data flow | DISABLED |
| search_service | search_540 | PRESENT (name, email, user_203) | evidence_20 :37 and :76 `"display_name":"Nneka Okeke","email":"nneka.o2286@zoho.com","customer_reference":"user_203"`; activity_2573 DELETE FAILED | SEARCH_INDEX_ENTRY | ABSENT |
| security_service | audit_record_5023 | PRESENT | evidence_20 :23 and :62 `"subject_reference":"user_203","event_name":"account_deletion_reviewed"` | SECURITY_AUDIT_LOG | PRESENT (retain) |
| account_service | (account_2399 or account_6726) | no visible evidence | see Linking | ACCOUNT_TOMBSTONE / profile | not determinable |

### Expected status: **INCOMPLETE**
The reported COMPLETE is contradicted by the active connector and the remaining search entry.

### Expected steps
1. FINDING REPORT_ACTIVE_DATA_FLOW / ACTIVE: integration_service, data_flow_3530, evidence_20
2. FINDING REPORT_REMAINING_RECORD / PRESENT: search_service, search_540, evidence_20
3. REMEDIATION DISABLE_DATA_FLOW / DISABLED: integration_service, data_flow_3530, ""
4. REMEDIATION DELETE_RECORD / ABSENT: search_service, search_540, ""
5. VERIFICATION VERIFY_DATA_FLOW_DISABLED / DISABLED: integration_service, data_flow_3530, ""
6. VERIFICATION VERIFY_RECORD_ABSENT / ABSENT: search_service, search_540, ""
7. (probable) VERIFICATION VERIFY_RECORD_PRESENT / PRESENT: security_service, audit_record_5023, ""

### Linking
reported_at is 2026-06-28T09:00Z COMPLETE, so the expected result is SUCCESS at about 07:30-08:30.
- activity_2562 (07:54) account_9268 PARTIAL fits case_204 (sdarwish4367, user_202, PARTIAL).
- activity_2563 (08:05) account_2399 SUCCESS
- activity_2564 (08:14) account_6726 SUCCESS

**Ambiguous between account_2399 and account_6726.** case_203 (ana-varga, user_201) is also COMPLETE at the same reported_at. Neither id appears in any evidence file.

### Probable misses
The burst runs 08:31-10:15:
- analytics_2463 ANONYMIZE (08:31), support_9505 REDACT, data_flow_5877 DISABLE and backup_9519 BLOCK (08:38-08:52). The last three belong to user_202 (evidence_20 :45, :32, :29). analytics_2463 (all-null, evidence_20:15) sits in the user_202 burst and is not attributable to user_203.
- support_8903 and search_7542 belong to ana-varga / user_201.
- data_flow_3530 and search_540 belong to user_203.

No other subject resource was found.

**Confidence:** high on status and findings. Medium on step 7.

---

## case_347: zayd-farouk@proton.me

- Request: requested 2026-04-14T09:00Z, reported PARTIALLY_COMPLETE at 2026-04-15T09:00Z, **audit_at 2026-04-29T09:00:00Z**.
- **Intent:** "I am requesting deletion of the account registered to this email address..." This authorises deletion.
- **Subject:** user_345, Zayd Farouk (user_identities.csv:346). Email zayd-farouk@proton.me, sha256 2b719aa2f012ad43b0e6870b9fa5dc63e4ed07ced5975b5477bc236da305357e (matches). Current phone +971 52 124 4036. Historical phone +971 52 085 5901 (user_audit_log.csv audit_58, 2025-09-30). Look-alikes that are **not** the subject: zayd.k7314@zoho.com, zayd.d5724@outlook.com, zayd-elsayed@gmail.com.
- **Visible files:** captured up to evidence_32 (backup_restore_console_20260429.png, 09:00, unrelated). Subject hits occur **only in evidence_71** `evidence/records/service_resource_export_20260429_083222.json` (captured 08:32:22Z).

### Resources

| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| search_service | search_8185 | PRESENT (email) | evidence_71 json:220-237 `"email": "zayd-farouk@proton.me" ... "resource_id": "search_8185"`, observed 07:51:48Z; activity_1449 DELETE FAILED | SEARCH_INDEX_ENTRY | ABSENT |
| support_platform | support_9474 | PRESENT (requester_email = subject) | evidence_71 json:301-309 `"message_excerpt": "Customer contacted support about account access." ... "requester_email": "zayd-farouk@proton.me" ... "resource_id": "support_9474"`; activity_1446 DELETE_RECORD FAILED | most likely SUPPORT_ATTACHMENT (see note) | ABSENT |
| account_service | (account_3372 or account_9881) | no visible evidence | see Linking | | |

**Note on support_9474.** The worker attempted DELETE_RECORD on it, not REDACT_RECORD. Across the dataset, every support resource the worker DELETEs and that reappears elsewhere is shown in snapshot bundles as a `ticket_attachments` record. Examples: support_3615 (customer_data_snapshot_bundle_20260322.json:357-363, plus a service-export "tickets" row with the same "account access" excerpt) and support_3896, support_3684 and support_5830, each with the same pattern. Tickets that are redacted (customer_reference kept, email null) were only ever REDACT_RECORD targets. So service-export "tickets" rows that the worker DELETEs are attachments, and rule_06 requires DELETE. The alternative reading is SUPPORT_MESSAGE, which would give REDACT and REPORT_EXPOSED_PII.

### Expected status: **INCOMPLETE**

### Expected steps
1. FINDING REPORT_REMAINING_RECORD / PRESENT: search_service, search_8185, evidence_71
2. FINDING REPORT_REMAINING_RECORD / PRESENT: support_platform, support_9474, evidence_71
3. REMEDIATION DELETE_RECORD / ABSENT: search_service, search_8185, ""
4. REMEDIATION DELETE_RECORD / ABSENT: support_platform, support_9474, ""
5. VERIFICATION VERIFY_RECORD_ABSENT / ABSENT: search_service, search_8185, ""
6. VERIFICATION VERIFY_RECORD_ABSENT / ABSENT: support_platform, support_9474, ""

The relative order of search_8185 and support_9474 is uncertain. The worker order was support then search (activity_1446 before activity_1449).

No data flow, backup, audit or legal record for user_345 is visible. data_flow_3178 (enabled) selects yaw.f2622@zoho.com, so it belongs to case_349.

### Linking
reported_at is 2026-04-15T09:00Z PARTIAL.
- activity_1440 (07:51) account_421 SUCCESS fits case_348 (iobi4703, COMPLETE).
- activity_1441 (08:02) account_3372 PARTIAL
- activity_1442 (08:11) account_9881 PARTIAL

**Ambiguous** with case_349 (yaw.f2622@zoho.com, PARTIAL, same reported_at). Neither account id appears in evidence. The four 404 lookups in evidence_71 (account_1949, 5059, 5214, 8834) belong to deletes on other dates (activity_1397, 1490, 1492, 1532), not this case.

### Probable misses
The burst runs 09:38-10:42:
- support_9474 and search_8185 belong to the subject.
- export_4871, search_6170, support_2897 and analytics_9196 belong to iobi4703.
- data_flow_3178 and search_3944 belong to yaw.

Nothing else is attributable to the subject.

**Confidence:** high on INCOMPLETE and on search_8185. Medium on the support_9474 treatment (DELETE / REMAINING_RECORD vs REDACT / EXPOSED_PII).

---

## case_191: KARIM-HADDAD@PROTON.ME

- Request: requested 2026-06-29T11:00Z, reported PARTIALLY_COMPLETE at 2026-06-30T11:00Z, **audit_at 2026-07-18T11:00:00Z**.
- **Intent:** "I want to close this account and have its associated personal data deleted..." This authorises deletion. The email is upper-case but matches case-insensitively.
- **Subject:** user_189, Karim Haddad (user_identities.csv:190). Email karim-haddad@proton.me, sha256 44376f7cd89a3d14bcbf5f24f05c62c7b7dd769c6a94b02fe87b62ddb3bd912c (matches), phone +971 56 868 6752. There are no audit-log rows.
- **Visible files:** captured up to evidence_18 (account_history_report_20260718.pdf, 11:00, unrelated: user_18 Ingrid Dahl). Subject hits occur **only in evidence_83** `evidence/records/service_resource_export_20260718_104335.json` (captured 10:43:35Z). Neither the email nor the hash appears anywhere, only user_189.

### Resources

| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| backup_service | backup_3010 | restore_allowed false (BLOCKED), reference only | evidence_83 json:102-108 `"customer_email": null, "customer_reference": "user_189" ... "restore_allowed": false`; activity_2597 BLOCK_RESTORE SUCCESS | BACKUP_ARCHIVE | RETAIN + BLOCKED |
| integration_service | data_flow_1611 | enabled false, stopped | evidence_83 json:126-133 `"customer_email": null, "customer_reference": "user_189", "enabled": false, "last_delivery_status": "stopped"`; activity_2595 DISABLE SUCCESS | data flow | DISABLED |
| security_service | audit_record_7493 | PRESENT, retention_until 2033-12-31 | evidence_83 json:302-306 `"SUBJECT_REQUEST_AUDITED" ... "subject_reference": "user_189"` | SECURITY_AUDIT_LOG | PRESENT |
| support_platform | support_5049 | REDACTED (customer_reference only; email, name and phone null) | evidence_83 json:322-328 `"customer_reference": "user_189", "message_excerpt": "Customer followed up about an order update.", "requester_email": null, "requester_name": null, "requester_phone": null`; activity_2594 REDACT SUCCESS | SUPPORT_MESSAGE | REDACTED |
| analytics_platform | analytics_5614 (probable) | ANONYMIZED (all identifiers null) | evidence_83 json:80-87; attributed only by burst timing: activity_2593 (06-30T10:31) ANONYMIZE SUCCESS, directly before the user_189 burst | ANALYTICS_PROFILE | ANONYMIZED |
| account_service | account_9317 (possible) | 404 / absent | evidence_83 json:43-47 `"profile": null, "resource_id": "account_9317", "status_code": 404`; ownership ambiguous, see Linking | profile / tombstone | |

### Expected status: **COMPLETE**
The reported PARTIALLY_COMPLETE is not supported. Every subject-linked resource visible at audit_at is in its required state, and there is no active flow or restore path. The only open issue is the account, see Linking.

### Expected steps (all VERIFICATION, cited evidence_83)
1. VERIFY_RECORD_ANONYMIZED / ANONYMIZED: analytics_platform, analytics_5614, evidence_83 (probable)
2. VERIFY_RECORD_REDACTED / REDACTED: support_platform, support_5049, evidence_83
3. VERIFY_DATA_FLOW_DISABLED / DISABLED: integration_service, data_flow_1611, evidence_83
4. VERIFY_RESTORE_BLOCKED / BLOCKED: backup_service, backup_3010, evidence_83
5. VERIFY_RECORD_PRESENT / PRESENT: security_service, audit_record_7493, evidence_83

Possible additional step: VERIFY_RECORD_ABSENT on account_service, account_9317, evidence_83, but only if account_9317 is the subject's. The order above follows the worker burst order; the canonical order is unknown.

### Linking
reported_at is 2026-06-30T11:00Z PARTIAL.
- activity_2591 (10:02) account_6608 PARTIAL
- activity_2592 (10:13) account_9317 PARTIAL
- account_9877 SUCCESS (10:52) and account_1090 / account_8423 FAILED (11:01, 11:12) fit the 12:00 reported_at cases 176 (COMPLETE) and 177/178 (NOT_STARTED).

**Ambiguous** with case_192 (eokafor9339@fastmail.com, user_190, PARTIAL, same reported_at). Burst order points weakly to the first account delete (account_6608) going with the first burst (case_191 at 10:31-10:52, with case_192's burst at 11:57-12:54), but that is a guess. account_9317 shows 404 in evidence_83, while account_6608 is in no evidence file.

Tension: rule_15 implies an ACCOUNT_TOMBSTONE keeping user_189, because retained records (support_5049, audit_record_7493, backup_3010) still reference user_189. A 404 for the subject's account would mean the tombstone was removed rather than redacted. Visible evidence cannot settle this.

### Probable misses
- analytics_5614 is attributable only by timing.
- case_192's burst (export_2705, search_6680, support_5493, analytics_4472) clearly belongs to eokafor, by the email in evidence_83.

**Confidence:**
- Medium-high on COMPLETE.
- Medium on including analytics_5614.
- Low on any account step.

Open question: if the grader expects the account to be shown as a tombstone, the case could be INCOMPLETE, but no visible file shows a user_189 account at all.
