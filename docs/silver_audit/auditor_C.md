# Blind silver audit C: case_33, case_55, case_531

Sources used: dataset/ only (deletion_requests.csv, sample_deletion_requests.csv for collision checks, user_identities.csv, user_audit_log.csv, system_activity.csv, deletion_rules.csv, evidence_files.csv, evidence/**). No code/, docs/, output.csv or sample_output.csv were read.

Identifier sweep: all evidence text files were grepped for each subject's email, sha256, phone digits (spaced and unspaced), `user_NN` (word boundary) and full name. Visible PNG/PDF artifacts were inspected manually (evidence_46, 42, 32, 28, 27, 23, 19, 18).

---

## case_33: ingrid.dahl@outlook.com

- Request (deletion_requests.csv, case_33): requested 2026-07-16T08:00Z, reported COMPLETE at 2026-07-18T02:00Z, audit_at 2026-07-19T13:00Z.
- **Intent:** "Please close my account and process the associated personal-data deletion..." This authorises deletion, with no negation and no scope limit.
- **Subject:** user_18, Ingrid Dahl. user_identities.csv: `user_18,Ingrid Dahl,ingrid.dahl@outlook.com,+46 70 787 39 30,0649edda...f8af`. The sha256 of the email matches the stored hash (computed). user_audit_log.csv has no rows for user_18, so there are no historical identifiers.
- **Visible files:** captured_at <= 2026-07-19T13:00Z, which means evidence_62 through evidence_18 (the latest is evidence_18, 2026-07-18T11:00Z).
- **Text grep hits:** none in visible files. The only text hits are in evidence_01 (2026-09-15), which is after audit_at and therefore not used.
- **Catalog claims** (system_activity.csv):
  - l.4005 `activity_4004,2026-06-18T12:07:01Z,LINK_RESOURCE_IDENTITY,...,export_service,export_1260,... to ingrid.dahl@outlook.com and user_18`. The artifact captured just before it is evidence_23 `images/customer_export_console_20260618.png` (2026-06-18T12:00Z). It shows row "export_1260 customer_export_1260.zip ingrid.dahl@outlook.com Ready 18 Jun 06:42 UTC" and a detail pane with Owner ingrid.dahl@outlook.com, Expires 25 Jun 2026 06:42 UTC, Download count 0, Included Profile/Orders/Saved addresses. **The artifact supports the claim.**
  - l.4010 `activity_4009,2026-07-18T11:07:01Z,LINK_RESOURCE_IDENTITY,...,export_service,export_1842,SUCCESS,Data catalog linked export_1842 (NST-2026-0718-1842) to ingrid.dahl@outlook.com and user_18`. The artifact is evidence_18 `documents/account_history_report_20260718.pdf` (2026-07-18T11:00Z). pdftotext shows "Statement NST-2026-0718-1842 / Customer Ingrid Dahl / user_18 / ingrid.dahl@outlook.com / order ORD-20261260 / Delivery address 24 Fjordgata, 7010 Trondheim". **The artifact supports the claim.**

| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| export_service | export_1260 | PRESENT (Ready). No later visible evidence of deletion. | evidence_23 PNG: "export_1260 … ingrid.dahl@outlook.com Ready"; catalog activity_4004 (system_activity.csv:4005) | USER_EXPORT (rule_09) | DELETE / ABSENT |
| export_service | export_1842 | PRESENT. Created after the request and 9 h after the COMPLETE claim. | evidence_18 PDF: "Statement NST-2026-0718-1842 … Ingrid Dahl … user_18 … ingrid.dahl@outlook.com"; catalog activity_4009 (system_activity.csv:4010) | USER_EXPORT (rule_09), as catalogued under export_service | DELETE / ABSENT |

- **Expected status: INCOMPLETE.** Both exports are visibly present and the COMPLETE claim is contradicted.
- **Expected steps:**
  1. FINDING REPORT_REMAINING_RECORD export_service export_1260 PRESENT evidence_23
  2. FINDING REPORT_REMAINING_RECORD export_service export_1842 PRESENT evidence_18
  3. REMEDIATION DELETE_RECORD export_service export_1260 ABSENT ""
  4. REMEDIATION DELETE_RECORD export_service export_1842 ABSENT ""
  5. VERIFICATION VERIFY_RECORD_ABSENT export_service export_1260 ABSENT ""
  6. VERIFICATION VERIFY_RECORD_ABSENT export_service export_1842 ABSENT ""
- **Linking:**
  - No DELETE_RECORD -> account_service row exists in the 0.5–1.5 h window before reported_at (2026-07-18T00:30–01:30Z). The only row from 07-17T20:00 to 07-18T06:00 is activity_2864 (UPDATE_RECORD account_8152, 02:55). The nearest deletes are 07-17 04:49–05:09 (activity_2845–2847, all SUCCESS), more than 20 h earlier, and 07-19 07:08+ (activity_2872+). Neither is plausible.
  - The primary account is therefore not linkable at audit_at.
  - Note: a second request for the same email exists: **case_52** (requested 2026-06-16, reported COMPLETE 2026-06-18T03:00Z, audit 2026-06-19T14:00Z), which would see export_1260 (evidence_23).
- **Post-audit corroboration (not used for the answer):**
  - evidence_01 log line 68: `resource_id=export_1260 event=export_download_check_completed file=customer_export_1260.zip available=true` (2026-09-15, trace tr-2805623 started with owner_key "ingrid.dahl@outlook.com", line 65).
  - activity_3328 (2026-08-19) DELETE export_1260 PARTIAL.
  - evidence_01 line 69: account_2373 returned 404 for the ingrid.dahl lookup (trace tr-1410012). activity_3324 deleted account_2373 at 2026-08-19 SUCCESS, which may instead belong to case_103 (reported 2026-08-19T12:00 COMPLETE). All of this is after audit_at.
- **Probable misses:** no deletion_worker rows were found for export_1842 or for any user_18 resource before audit_at.
- **Confidence:** medium. INCOMPLETE is high confidence; the step set is medium.
- **Open questions:**
  1. Does the grader attribute export_1260 to case_52 only, which would leave case_33 with export_1842 alone (3 steps)? Strict evidence says export_1260 is still present at case_33's audit_at, so I would include it.
  2. Is the PDF statement truly a USER_EXPORT? The catalog places it in export_service. No legal-hold or retention record names it (evidence_27 legal register has no user_18/Dahl match).
  3. Step order between the two exports is unknown; I ordered by resource id.

---

## case_55: areed1433@gmail.com

- Request: requested 2026-04-27T06:00Z, reported NOT_STARTED at 2026-04-29T00:00Z, audit_at 2026-04-30T11:00Z.
- **Intent:** "Please treat this message as a request for permanent account deletion. Please include information linked through current or earlier account identifiers." This authorises deletion.
- **Subject:** user_16, Amelia Reed, areed1433@gmail.com, +44 7700 900016, sha256 7001f886…eb62 (computed, matches). There are no user_audit_log rows for user_16.
- **Visible files:** captured_at <= 2026-04-30T11:00Z, i.e. evidence_62 … evidence_32 (latest evidence_32 2026-04-29T09:00Z; evidence_71 2026-04-29T08:32Z).
- **Text grep hits:** none in visible files. The only hits are in evidence_01, which is post-audit.
- **Catalog claim:** system_activity.csv l.4007 `activity_4006,2026-04-29T09:07:01Z,LINK_RESOURCE_IDENTITY,data_catalog,backup_service,backup_9287,... to areed1433@gmail.com and user_16`. The artifact is evidence_32 `images/backup_restore_console_20260429.png` (2026-04-29T09:00Z). Its archives table row 3 reads "backup_9287 areed1433@gmail.com eu-west-1 26 Apr 02:00 84.7 GB AES-256 Archive". The detail pane shows Account areed1433@gmail.com, Path s3://northstar-backups/customer-platform/weekly/segment-42-20260426.tar.zst, Retention end 26 Jul 2026. **The artifact supports the claim.** No restore block or deletion block is shown, and the activity feed lists other backups as restored ("backup_9286 restored · Completed").

| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| backup_service | backup_9287 | PRESENT, restore access NOT shown blocked. No visible BLOCK_RESTORE event. | evidence_32 PNG row "backup_9287 areed1433@gmail.com … Archive"; activity_4006 (system_activity.csv:4007) | BACKUP_ARCHIVE (rule_14) | RETAIN, with restore BLOCKED |

- **Expected status: INCOMPLETE.**
- **Expected steps:**
  1. FINDING REPORT_RESTORE_RISK backup_service backup_9287 ACTIVE evidence_32
  2. REMEDIATION BLOCK_RESTORE backup_service backup_9287 BLOCKED ""
  3. VERIFICATION VERIFY_RESTORE_BLOCKED backup_service backup_9287 BLOCKED ""
- **Linking:**
  - No DELETE_RECORD -> account_service row exists in 2026-04-28T22:30–23:30Z. The rows from 04-28T18:00 to 04-29T04:00 are activity_1637 (INDEX search_1045) and activity_1638 (RETAIN audit_record_4275).
  - The nearest account deletes are 04-28 05:52–06:12 (activity_1624–1626, SUCCESS) and 04-29 09:47+ (SUCCESS). None is FAILED and close enough to be plausible, so the account cannot be linked.
- **Post-audit corroboration (not used for the answer):**
  - evidence_01 l.94: `resource_id=backup_9287 event=restore_candidate_evaluated eligible=true deletion_block=false` (trace tr-5638333 started with subject_key "areed1433@gmail.com", l.91).
  - activity_3387 (2026-08-22): RESTORE_BACKUP backup_9287 repopulated search_4882.
- **Probable misses:** none visible before audit_at.
- **Confidence:** medium-high.
- **Open question:** restore access is not explicitly shown in the visible artifact. I treat an unblocked archive of the subject as a restore risk, given the NOT_STARTED claim and the absence of any BLOCK_RESTORE.

---

## case_531: k.amponsah80@gmail.com

- Request: requested 2026-01-10T12:00Z, reported NOT_STARTED at 2026-01-12T12:00Z, audit_at 2026-01-29T12:00Z.
- **Intent:** "I would like the account associated with this address to be erased..." This authorises deletion.
- **Subject:** user_529, Kwame Amponsah, k.amponsah80@gmail.com, +233 24 878 8141, sha256 ed33bcca…7348 (computed, matches). There are no user_audit_log rows. Look-alike Amponsah users (user_87, 308, 490, 711) are different people and are excluded.
- **Visible files:** only **evidence_62** `records/service_resource_export_20260129_114459.json` (captured 2026-01-29T11:44:59Z). evidence_49, captured 2026-01-31, is after audit_at and contains k.amponsah80/user_529 at l.186/365; it was not used.
- **Grep hit** in evidence_62 lines 101-108 (backup_service.restore_entries): `"archive_key": "archive/customer-data/backup_3382.tar.zst", "customer_email": "k.amponsah80@gmail.com", "observed_at": "2026-01-29T11:39:19Z", "resource_id": "backup_3382", "restore_allowed": true`.
- **Corroboration:** system_activity.csv l.98 `activity_97,2026-01-12T12:38:02Z,CHECK_RESTORE_ACCESS,deletion_worker,backup_service,backup_3382,SUCCESS,Restore-access check confirmed that archive backup_3382 can still be restored.`
- **No LINK_RESOURCE_IDENTITY rows** exist for this subject.

| system_id | resource_id | state at audit_at | proof | category | required end state |
|---|---|---|---|---|---|
| backup_service | backup_3382 | PRESENT, restore_allowed=true | evidence_62 l.104–108 | BACKUP_ARCHIVE (rule_14) | RETAIN, with restore BLOCKED |
| account_service | account_3146 (linked by timing) | Unknown. The delete was FAILED (claim) and no visible state is shown; it is not in evidence_62 profile_lookups. | activity_89 (system_activity.csv:90) | USER_PROFILE (rule_01) | DELETE / ABSENT |

- **Linking:**
  - Window 2026-01-12T10:30–11:30Z, with reported_at 12:00:
    - activity_89 10:53:10 account_3146 **FAILED**
    - activity_90 11:04:53 account_6169 PARTIAL
    - activity_91 11:13:26 account_470 SUCCESS
  - Requests reported at 2026-01-12T12:00: case_530 (PARTIALLY_COMPLETE, so account_6169), case_531 (NOT_STARTED, so account_3146) and case_532 (COMPLETE, so account_470). **Exactly one plausible candidate: account_3146.** No other request claims a FAILED delete in this window.
  - Consistent check: evidence_62 shows account_6169 and account_470 as 404 (l.22, l.40). account_3146 is absent from the export, so its state is unknown.
- **Expected status: INCOMPLETE** (high confidence).
- **Expected steps (primary, high confidence on the backup portion):**
  1. FINDING REPORT_RESTORE_RISK backup_service backup_3382 ACTIVE evidence_62
  2. REMEDIATION BLOCK_RESTORE backup_service backup_3382 BLOCKED ""
  3. VERIFICATION VERIFY_RESTORE_BLOCKED backup_service backup_3382 BLOCKED ""
- **Optional (low-medium confidence):** add REPORT_REMAINING_RECORD account_service account_3146 PRESENT activity_89 as finding 2. Then add DELETE_RECORD account_3146 after BLOCK_RESTORE, and VERIFY_RECORD_ABSENT account_3146 after VERIFY_RESTORE_BLOCKED.
  - The only support is the FAILED result, which is a claim, plus the NOT_STARTED status. No visible artifact shows account_3146 present.
  - I would *not* include it unless the pipeline's policy is to treat a FAILED primary-account delete as proof of a remaining record.
- **Alternative evidence choice:** evidence_62 (the latest, 2026-01-29) is preferred over activity_97 (2026-01-12) for the restore-risk citation.
- **Probable misses:**
  - Other deletion_worker rows after the account delete on 01-12 (activity_92–96) concern analytics_3744/893, support_7724, data_flow_6987 and backup_6344.
  - evidence_62 ties data_flow_6987, backup_6344 and support_7724 to user_530 (case_530), not to the subject.
  - None of these is attributable to user_529.
- **Confidence:** high for status and for the backup steps. The account step is an open question.
