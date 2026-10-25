# Blind silver audit D: case_63, case_61, case_540

Sources used: dataset/ only (CSV, evidence text files, PNGs viewed, PDFs via pdftotext). No code/, docs/, output.csv, sample_output.csv, runs/, scratch/.
Paths below are relative to dataset/.

---

## case_63 (deletion_requests.csv:32)

- requested_at 2026-09-14T04:20Z, reported NOT_STARTED at 2026-09-15T22:20Z, audit_at 2026-09-17T09:20Z.

### 1. Intent
"Please permanently delete the account associated with this email address..." -> authorises deletion.

### 2. Subject
- user_09, Kwame Mensah (user_identities.csv:10)
- email kwame-mensah@proton.me; sha256 e7ce7f1fd5cd4e5873576243ee7a0ca8599c51d0e9f2197f6184efc514e5bd2a (computed, matches email_hash)
- phone +233 24 456 1267
- user_audit_log.csv: no rows for user_09 (no historical identifiers).
- Look-alikes NOT the subject: kwame-asante@gmail.com (user_399), kwame-frimpong@proton.me (user_789), n.mensah16@gmail.com, kmensah735794@gmail.com, kwame.g4940@outlook.com.

### 3. Visible files
84 manifest rows with captured_at <= 2026-09-17T09:20Z (evidence_01..ish; includes evidence_60 marketing_profile_console.png captured 2026-09-16T07:20Z, evidence_55, evidence_58 PDFs, 10 PNGs).

### 4. Discovery
- grep (case-insensitive) for kwame-mensah@proton, hash prefix e7ce7f1fd5cd4e58, phone `456 1267`/`4561267`, `\buser_09\b`, "Kwame Mensah" across all visible text/SQL/JSON/log files: **0 hits**. Loose grep kwame|mensah|1267 only returned look-alike other people (e.g. syslog_archive_ap_southeast_20260325.log:83 kmensah735794@gmail.com; customer_data_snapshot_bundle_20260416.json:388 n.mensah16@gmail.com; customer_data_inventory_20260404.sql:23 kwame-asante@gmail.com).
- PDFs (account_history_report_20260718, legal_retention_register_20260529, security_retention_extract, delivery_correction_attachment): pdftotext + grep -> 0 hits.
- PNGs viewed (all 11 visible): none shows Kwame Mensah / user_09.
- LINK_RESOURCE_IDENTITY: system_activity.csv:4009 activity_4008 2026-09-16T07:27:01Z "Data catalog linked marketing_001 (marketing_001) to kwame-mensah@proton.me and user_09."
  - Verification against the artifact captured 7 min earlier: evidence_60 evidence/images/marketing_profile_console.png (evidence_files.csv:61, 2026-09-16T07:20Z) shows **"Soo-jin Park · marketing_001 · sj.park@naver.com · +82 10-5837-9451", market South Korea**. That is a different person (sj.park@naver.com is not in user_identities.csv). **Catalog claim is contradicted -> marketing_001 is not the subject's record.**

### 5/6. Resource table
| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| marketing_platform | marketing_001 | PRESENT but belongs to Soo-jin Park, not subject | evidence_60 marketing_profile_console.png header "Soo-jin Park / marketing_001 / sj.park@naver.com"; contradicts activity_4008 (system_activity.csv:4009) | MARKETING_PROFILE (rule_10 DELETE) | not applicable to subject (decoy) |
| account_service | (unknown) | unknown | no evidence | USER_PROFILE / ACCOUNT_TOMBSTONE | unknown |

### 8. Linking (account delete)
- reported_at 2026-09-15T22:20Z, NOT_STARTED -> expect FAILED delete around 20:50-21:50Z. **No deletion_worker rows exist between 2026-09-15T10:52Z (activity_3856) and audit_at.**
- Sep 15 09:47-10:07 deletes (activity_3849 account_2064 PARTIAL, activity_3850 account_6523 SUCCESS, activity_3851 account_7566 SUCCESS) align with reported_at 2026-09-15T11:00Z requests case_44 (PARTIALLY_COMPLETE) and case_03 (COMPLETE), and none is FAILED. -> **No plausible account delete for case_63.**

### 9. Misses
Sep 15 downstream deletion_worker rows (activity_3852..3856: analytics_9406, analytics_5589, support_1066, data_flow_223, backup_6266) belong to the 11:00Z batch; none visibly references the subject.

### 10. Verdict
- No visible evidence ties any record to user_09; the only claim (marketing_001) is disproved by the screenshot.
- **Expected status: COMPLETE, steps_json = []** (no subject records remain that can be proven; no flow/restore risk shown). Alternative if grader requires at least one step: none can be cited honestly.
- Confidence: **low-medium**. Open questions: whether the design expects the decoy to be rejected (→ COMPLETE []) vs. a naive catalog-trusting INCOMPLETE on marketing_001 (REPORT_REMAINING_RECORD marketing_platform marketing_001 evidence_60 / DELETE_RECORD / VERIFY_RECORD_ABSENT) — I reject the latter because evidence_60 shows a different person. Reported NOT_STARTED is only a claim.

---

## case_61 (deletion_requests.csv:30)

- requested_at 2026-02-11T05:00Z, reported PARTIALLY_COMPLETE at 2026-02-12T23:00Z, audit_at 2026-02-14T10:00Z.

### 1. Intent
"Please treat this message as a request for permanent account deletion..." -> authorises deletion.

### 2. Subject
- user_07, Priya Raman (user_identities.csv:8)
- email priya.raman@gmail.com; sha256 284c7b87b8237e241293c9e81c8f0bef10c4dc1dffefb382c45107ea40c39668 (computed, matches)
- phone +91 98765 73142
- No user_audit_log.csv rows for user_07.

### 3. Visible files (captured_at <= 2026-02-14T10:00Z)
evidence_46 images/object_storage_browser_20260213.png (02-13T08:00), evidence_47 databases/customer_data_reporting_replica_20260208.sql, evidence_48 logs/operations_stream_me_central_20260203.log, evidence_49 records/customer_data_snapshot_bundle_20260131.json, evidence_62 records/service_resource_export_20260129_114459.json, evidence_63 databases/customer_data_inventory_20260213.sql.

### 4. Discovery
- grep priya|raman|73142|9876573142|284c7b|\buser_07\b across the 5 text files: **0 hits**.
- system_activity.csv:4008 activity_4007 2026-02-13T08:07:01Z LINK_RESOURCE_IDENTITY data_catalog -> object_storage object_19: "Attachment catalog confirmed object_19 (delivery_confirmation_19.pdf) belongs only to priya.raman@gmail.com and user_07; no other subject is linked."
- Verification against evidence_46 (evidence_files.csv:47, captured 2026-02-13T08:00Z, 7 min before the link): Nimbus Object Storage, bucket northstar-customer-data, eu-west-1/support-attachments/2026/02, row 1 "delivery_confirmation_19.pdf, 684 KB, modified 12 Feb 18:42, Standard, v3", detail pane uploader support-service. **No person shown** (neither the subject nor anyone else) — claim not contradicted; artifact establishes the object exists at 2026-02-13T08:00Z.
- Unrelated note: delivery_confirmation_19.pdf also appears in databases/customer_data_regional_replicas_20260330.sql:39 as support_3802 uploaded_by lucia-garcia@proton.me — captured after audit_at and a different resource/person; ignored.
- No later visible evidence (before audit_at) shows object_19 deleted; no deletion_worker row targets object_19.

### 5/6. Resource table
| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| object_storage | object_19 | PRESENT | evidence_46 object_storage_browser_20260213.png row 1 "delivery_confirmation_19.pdf ... v3"; ownership per activity_4007 (system_activity.csv:4008) "belongs only to priya.raman@gmail.com and user_07" | SUPPORT_ATTACHMENT (rule_06: attachment belongs only to subject -> DELETE) | ABSENT |
| account_service | (unknown) | unknown | no evidence | USER_PROFILE | unknown |

### 7. Expected steps (INCOMPLETE)
1. FINDING REPORT_REMAINING_RECORD PRESENT object_storage object_19 evidence_46
2. REMEDIATION DELETE_RECORD ABSENT object_storage object_19 ""
3. VERIFICATION VERIFY_RECORD_ABSENT ABSENT object_storage object_19 ""

### 8. Linking
- reported_at 2026-02-12T23:00Z PARTIAL -> expect PARTIAL delete ~21:30-22:30Z Feb 12. **No deletion_worker rows on 2026-02-12 at all.**
- Feb 11 batch: activity_515 account_1957 PARTIAL 09:51, 516 account_9034 SUCCESS, 517 account_7023 SUCCESS, 519 account_6373 SUCCESS, 520 account_2761 SUCCESS, 521 account_3584 PARTIAL 11:12 — these fit requests reported 2026-02-11T11:00Z/12:00Z (case_470/471/472 and case_455/456/457; the two PARTIALs map to case_472 and case_456). Feb 14 batch (activity_560+) fits reported_at 2026-02-14T10:00-12:00 cases. -> **No plausible account delete for case_61**; primary account not identifiable.

### 9. Misses
None found; Feb 11 downstream rows (activity_518..531) not tied to subject by any visible evidence.

### 10. Verdict
- **Expected status: INCOMPLETE**, steps as in §7.
- Confidence: **medium**. Open questions: (a) evidence_46 shows no person, ownership rests on the catalog claim activity_4007 (its distinctive "belongs only to ... no other subject is linked" wording matches rule_06's condition, suggesting it is meant to be trusted); (b) finding could alternatively cite activity_4007 — I prefer evidence_46 as the artifact proving presence; (c) system_id taken from activity_4007 target_system "object_storage".

---

## case_540 (deletion_requests.csv:509)

- requested_at 2026-08-27T12:00Z, reported NOT_STARTED at 2026-08-29T12:00Z, audit_at 2026-09-24T12:00Z.

### 1. Intent
"I need a copy of last year's invoices for my records. Please leave my profile and purchase history in place." -> access/copy request with explicit instruction NOT to delete. **Does not authorise deletion.**

### 2. Subject
user_538 Ingrid Eriksen, ieriksen5151@fastmail.com, +46 70 571 37 96 (user_identities.csv:539). No audit-log rows. No system_activity row names her.

### Supporting
system_activity.csv:3513 activity_3512 2026-08-29T10:47:38Z CLASSIFY_REQUEST privacy_intake "classified request for account_2176 as non-deletion; no destructive action was authorized" — ~1.2 h before reported_at, consistent with this request (link not needed for the verdict).

### Verdict
- **Expected: NOT_APPLICABLE, steps_json = []**. Confidence: **high**.
