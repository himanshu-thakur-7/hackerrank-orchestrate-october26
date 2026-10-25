# 02 — Data Notes

Discovery passes over `dataset/`. Each claim cites the file and the row ID (`case_id`, `user_id`, `audit_id`, `activity_id`, `rule_id`, `file_id`) or a line number. Statuses and `reported_result` values are recorded as **claims**, not facts. Scripts live in `scratch/`, which is gitignored.

---

## Pass 1 — CSVs

Scripts: `scratch/pass1_csvs.py`, `scratch/pass1b.py`.

### 1.1 Row counts and columns

Counts are parsed with `csv.DictReader`; `wc -l` matches, so no fields span multiple lines.

| File | Rows | Columns |
| --- | --- | --- |
| `deletion_requests.csv` | 518 | case_id, email, requested_at, reported_status, reported_at, audit_at, request_text |
| `sample_deletion_requests.csv` | 32 | same as above |
| `sample_output.csv` | 32 | case_id, deletion_status, steps_json |
| `user_identities.csv` | 850 | user_id, name, email, phone, email_hash, updated_at |
| `user_audit_log.csv` | 306 | audit_id, user_id, event_time, field_name, old_value, new_value |
| `system_activity.csv` | 4011 | activity_id, event_time, event_type, source_system, target_system, resource_id, reported_result, details |
| `deletion_rules.csv` | 15 | rule_id, data_category, condition, required_action |
| `evidence_files.csv` | 94 | file_id, file_path, origin, captured_at |
| `output.csv` (template) | 0 | case_id, deletion_status, steps_json |

### 1.2 case_id format, which resolves ambiguity A1

- **Eval IDs are NOT zero-padded.** They run from `case_33` to `case_550`, with 67 two-digit and 451 three-digit IDs, all unique.
- The file is already in **numeric** order (`case_33, case_34, …`). Lexicographic order differs, for example `case_100` sorts before `case_33`.
- Sample IDs are `case_01` to `case_32`, all two digits, so lexical and numeric order agree there and the sample cannot reveal which one the grader expects.
- Eval and sample case numbers do not overlap.
- **Decision still open (A1).** Numeric order matches the input file, so it is the likely intent. The decision goes to the contract doc; I have not chosen yet.

### 1.3 Distributions

- `reported_status` (claims):
  - eval: COMPLETE 254, PARTIALLY_COMPLETE 152, NOT_STARTED 112
  - sample: COMPLETE 17, NOT_STARTED 10, PARTIALLY_COMPLETE 5
- `sample_output.deletion_status`: INCOMPLETE 22, COMPLETE 10, **NOT_APPLICABLE 0**. The sample has no non-deletion example.
- `system_activity.event_type` counts:

  | Event type | Count |
  | --- | --- |
  | DELETE_RECORD | 890 |
  | UPDATE_RECORD | 672 |
  | SYNC_RECORD | 447 |
  | INDEX_RECORD | 400 |
  | SEND_EMAIL | 368 |
  | REFRESH_CACHE | 284 |
  | RETAIN_RECORD | 206 |
  | ANONYMIZE_RECORD | 204 |
  | REDACT_RECORD | 173 |
  | CREATE_EXPORT | 155 |
  | CHECK_DATA_FLOW | 89 |
  | DISABLE_DATA_FLOW | 36 |
  | BLOCK_RESTORE | 36 |
  | CHECK_RESTORE_ACCESS | 28 |
  | LINK_RESOURCE_IDENTITY | 12 |
  | CLASSIFY_REQUEST | 10 |
  | RESTORE_BACKUP | 1 |

- `reported_result` (claims): SUCCESS 2914, FAILED 721, PARTIAL 376.
- `resource_id` prefixes in activity:

  | Prefix | Count |
  | --- | --- |
  | account | 1046 |
  | search | 690 |
  | analytics | 566 |
  | support | 425 |
  | email_delivery | 368 |
  | cache | 284 |
  | audit_record | 197 |
  | export | 189 |
  | data_flow | 157 |
  | backup | 66 |
  | tombstone | 11 |
  | legal_hold | 10 |
  | object | 1 |
  | marketing | 1 |

- `target_system`, top values: account_service 980, search_service 954, analytics_platform 566, email_delivery_service 368, cache_service 284, archive_service 196, support_platform 193, object_store 155, integration_service 126, backup_service 65, account_replication_cluster 55.
  - Rarer targets: export_service 34, identity_service 11, legal_service 10, privacy_case_management 10, account_failover_replica 1, object_storage 1, marketing_platform 1, security_service 1.
  - Note that `object_store` (155 rows) and `object_storage` (1 row) are near-duplicate system names.
- `user_audit_log.field_name`: email 107, email_hash 107, phone 92. There are no name changes.
- Evidence file types: .json 28, .log 26, .sql 24, .png 11, .pdf 4, .txt 1. That is 94 files, which matches the sum of the directory counts (databases 24, documents 4, images 11, logs 26, records 29).

### 1.4 Time ranges

| Field | Range |
| --- | --- |
| eval requested_at | 2026-01-05T06:00:00Z .. 2026-09-24T08:00:00Z |
| eval audit_at | 2026-01-29T12:00:00Z .. 2026-10-01T12:00:00Z |
| activity event_time | 2026-01-04T14:56:29Z .. 2026-10-01T10:18:34Z |
| audit event_time | 2024-12-14T16:31:44Z .. 2026-06-03T08:42:31Z |
| evidence captured_at | 2026-01-29T11:44:59Z .. 2026-10-01T12:00:00Z |

- Every eval row satisfies `requested_at <= reported_at <= audit_at`; there are 0 violations.
- Evidence capture and activity times span all audit windows, so per-case `audit_at` filtering matters.

### 1.5 deletion_rules.csv: 15 rules, one per category

| rule | data_category | required_action | condition |
| --- | --- | --- | --- |
| rule_01 | USER_PROFILE | DELETE | Always |
| rule_02 | SECONDARY_IDENTIFIER | DELETE | Always |
| rule_03 | SEARCH_INDEX_ENTRY | DELETE | Always |
| rule_04 | CACHE_ENTRY | DELETE | Always |
| rule_05 | SUPPORT_MESSAGE | **REDACT** | Conversation contains shared customer, agent, or order context that must be retained |
| rule_06 | SUPPORT_ATTACHMENT | **DELETE** | Attachment belongs only to the deletion subject |
| rule_07 | ANALYTICS_PROFILE | ANONYMIZE | Record is still attributable to a user |
| rule_08 | PRODUCT_TELEMETRY | ANONYMIZE | Record is still attributable to a user |
| rule_09 | USER_EXPORT | DELETE | Always |
| rule_10 | MARKETING_PROFILE | DELETE | Always |
| rule_11 | EMAIL_DELIVERY_LOG | REDACT | Log contains a user email address |
| rule_12 | SECURITY_AUDIT_LOG | RETAIN | Record is within the supplied retention period |
| rule_13 | LEGAL_HOLD_RECORD | RETAIN | A supplied legal hold is active |
| rule_14 | BACKUP_ARCHIVE | RETAIN | Restore access can be blocked |
| rule_15 | ACCOUNT_TOMBSTONE | REDACT | Account is deleted and only a stable internal user_id is needed to preserve references to retained records |

Implications:

- **A9 (support message vs attachment).** The rules make these separate categories with opposite actions: rule_05 REDACTs a message, and rule_06 DELETEs an attachment that is the subject's alone.
- **A17 (backups).** rule_14 says RETAIN a backup when restore can be blocked. That points to `REPORT_RESTORE_RISK` → `BLOCK_RESTORE`, not deletion. Pass 2 will confirm this against the sample.
- Several rules are conditional (rules 05, 06, 07, 08, 11, 12, 13, 14, 15). The condition has to be established from evidence, for example "within the supplied retention period" and "a supplied legal hold is active".

### 1.6 Identities and email_hash

- `user_identities.csv`: 850 unique `user_id`s. No field is empty, and no two rows share an email, even case-insensitively. **All current emails are lowercase.**
- **email_hash = sha256(email), lowercase hex.** This matched 850/850 rows. `sha256(lower(strip(email)))` also matched 850/850, because all stored emails are already lowercase. MD5 matched 0/850.
- The audit log has email and email_hash changes paired at the same `(user_id, event_time)`. That gives 107 pairs, and every pair has both `old_value` and `new_value` hashes equal to `sha256` of the corresponding email (107/107 each). Example: `audit_121`/`audit_122` for user_10.
  - This means a historical **hash** can be recomputed from a historical email, so hash-only evidence can be linked back to the user.
- There are 105 users with email changes. Two users changed email twice:
  - user_10: `audit_121` nadia.ionescu → nadia.petrescu, then `audit_238` → n.petrescu.
  - user_35: `audit_179` abena.o189491 → abena.o189466, then `audit_305` → abena.o1894.
  - Note the look-alike emails within one user's history, which are relevant to pass 5.
- The chains are consistent. Each change's `new_value` equals the next change's `old_value` (0 breaks), and the last `new_value` equals the current snapshot (0 mismatches). No audit event is later than the user's `updated_at`, and no audit row refers to an unknown user.
- Phone changes (92) also exist, so evidence may carry an **old phone number**.

### 1.7 Resolving request emails to users

The classification checks the current snapshot first, then the email audit history, first exactly and then case-insensitively.

| Bucket | Eval (518) | Sample (32) |
| --- | --- | --- |
| current, exact | 403 | 29 |
| historical, exact | 95 | 3 (case_10, case_29, case_30) |
| current, case-insensitive only | 15 | 0 |
| historical, case-insensitive only | 5 | 0 |
| unresolved | **0** | 0 |
| ambiguous (more than one user) | **0** | 0 |

- **Case sensitivity matters in eval only.** Twenty eval requests use an UPPERCASE email, for example `case_38` SIPHO.MOKOENA@GMAIL.COM → user_36 (current) and `case_40` CHOI.JIHOON94@GMAIL.COM → user_38 (historical). Matching must lowercase the email. The sample never exercises this.
- Examples of historical emails: `case_37` abena.o189491@zoho.com → user_35, which is user_35's *first* email (two changes back), and `case_41` lucas-souza95@gmail.com → user_39.
- **Repeated subject.** `case_33` and `case_52` both use ingrid.dahl@outlook.com, which maps to user_18. They have different windows: case_52 has requested_at 2026-06-16 and audit_at 2026-06-19, while case_33 has requested_at 2026-07-16 and audit_at 2026-07-19. The same user is audited at two points in time, so the answers may differ. `activity_4004` (2026-06-18, export_1260) and `activity_4009` (2026-07-18, export_1842) each link a different export to this user, one inside each window.

### 1.8 Request text and non-deletion requests

- The eval set has 27 distinct 40-character openings.
  - There are 12 English deletion templates, used 23 to 52 times each.
  - There are 5 non-English deletion templates with 12 to 14 cases each: Portuguese, Korean, Spanish, Japanese and French. That makes 62 non-ASCII texts.
  - There are **10 one-off texts, all non-deletion**, in `case_533` to `case_542`, all with `reported_status = NOT_STARTED`:

  | Case | Request type | Text |
  | --- | --- | --- |
  | case_533 | correction | "The mobile number on my profile is out of date. Please replace it… leave the account active." |
  | case_534 | marketing opt-out | "…I am not asking for deletion." |
  | case_535 | export / portability | "…Please keep the account as it is." |
  | case_536 | login help | "Do not close the account." |
  | case_537 | correction | "…without removing any of my records?" |
  | case_538 | marketing opt-out | "Please remove me from marketing lists only." |
  | case_539 | access | "…not a request to erase it." |
  | case_540 | invoice copy | "…leave my profile and purchase history in place." |
  | case_541 | email change | "I want to continue using the service." |
  | case_542 | access | "…please don't delete or change anything." |

  - case_538 is a **trap**: it contains the word "remove" but asks only for removal from marketing lists.
- There are 10 `CLASSIFY_REQUEST` activities (`activity_3486` … `activity_3827`), all with the text "classified request for account_N as non-deletion; no destructive action was authorized". These are claims, but they probably correspond to the 10 non-deletion cases. Linking them needs `account_N` → user, which is not tested yet.
- The sample texts are more varied, with case-specific hints. Examples:
  - `case_17`: "You may retain backups if required, but they must not be able to restore my personal profile."
  - `case_19`: "…clean my personal details out of earlier support conversations. Some of those messages also relate to another customer"
  - `case_28`: "A search result with a similar email belongs to someone else"
  - `case_31`/`case_32`: deleted-account reference (tombstone)

  Eval texts are generic templates, so **eval request text carries little case-specific signal** apart from deletion vs non-deletion.

### 1.9 Identity links inside activity

- Only 12 activity rows name an email or `user_N` in `details`, and all of them are `LINK_RESOURCE_IDENTITY` from `data_catalog` (`activity_4000` … `activity_4011`). Each one links one resource to an email and user. In every case the email resolves to that same user through the identity tables. Examples:
  - `activity_4000` account_5762 → haruka.s1838@zoho.com, user_11
  - `activity_4006` backup_9287 → areed1433@gmail.com, user_16
  - `activity_4011` tombstone_17 → leonie.g9352@outlook.com, user_17
- No activity row mentions a `case_N`.
- **Implication.** For most of the 4011 rows, the link from a resource to a user must come from evidence-file contents (SQL rows, JSON and logs carrying email, hash, phone or user_id), not from activity. Pass 3 will check this.

### 1.10 Activity semantics observed (claims)

- `CHECK_DATA_FLOW`, e.g. `activity_48`: "Connector status check confirmed that data flow data_flow_3518 remains enabled." This reads as an observed state.
- `CHECK_RESTORE_ACCESS`, e.g. `activity_49`: "Restore-access check confirmed that archive backup_8264 can still be restored."
- `DISABLE_DATA_FLOW` and `BLOCK_RESTORE`, e.g. `activity_95` and `activity_96`: the detail is a generic "Policy action completed for …". This is a claim that needs corroboration.
- `RESTORE_BACKUP` appears once, as `activity_3387` (2026-08-22, backup_9287): "Restore job repopulated downstream resource search_4882." `activity_4006` links backup_9287 to user_16, so this is a **recreation event**.
- `SYNC_RECORD` from account_service → analytics_platform, e.g. `activity_12`, is the sync path that can recreate deleted data.

---

## Pass 2 — sample_output.csv

Scripts: `scratch/pass2_sample.py` (pretty-prints every case and validates the schema) and `scratch/pass2b.py` (tests the sort key, serialization and evidence timing). Each statement below cites a `case_id` from `sample_output.csv`.

### 2.1 Schema

All 32 rows pass the following checks:

- every step has exactly the 7 keys;
- `step_no` runs 1..n;
- the phase matches the operation's phase;
- the state matches the operation's state, as in the triple table in `docs/01_CONTRACT.md` §1.4.

No other operation or state appears anywhere.

### 2.2 Sort-key test

The hypothesis is `(op_rank, system_id, resource_id)` ascending, with `step_no` assigned after sorting. **It holds for 32 of 32 cases.**

How much this test actually proves:

| Key tested | Failures |
| --- | --- |
| `(op_rank, system_id, resource_id)` | 0 |
| `(op_rank, system_id)` | 0 |
| `(op_rank, resource_id)` | 0 |
| `(phase, system_id, resource_id)` | **19** (e.g. case_11, where REDACT support_platform comes before ANONYMIZE analytics_platform) |
| `(phase, resource_id)` | **17** |

- **Operation rank beats system within a phase.** case_11 steps 6 to 8 are DELETE search_service, REDACT support_platform, ANONYMIZE analytics_platform. This is operation order, not alphabetical by system.
- **The `system_id` tiebreak is supported.** The sample has 30 adjacent pairs with the same operation, and all 30 have `system_id` strictly ascending. Example: case_11 steps 2 and 3 are REPORT_EXPOSED_PII on analytics_platform, then support_platform.
- **The `resource_id` tiebreak is never exercised.** None of the 30 same-operation pairs share a `system_id`, so whether the order is lexical or natural is still unknown (A2).
- **A3 (dependency order vs sort key) never comes up.** Remediation is always DISABLE → BLOCK → DELETE → REDACT → ANONYMIZE, which is plain table order. No sample case has two DELETEs where downstream and source would conflict.

### 2.3 Serialization (claim: the grader ignores key order)

- `steps_json` is compact JSON with no spaces.
- The key order varies:
  - case_01, case_02, case_04 to case_08 and case_10 use `sort_keys` order (`evidence_id, operation, phase, …`).
  - The other 24 cases use schema order (`step_no, phase, system_id, …`). An example is case_03.
- The CSV field is double-quoted, with inner quotes doubled. This is standard `csv` module quoting.

### 2.4 COMPLETE cases

There are 10: case_01 to case_04, case_21 and case_25 to case_28, plus case_31.

- They contain **only VERIFICATION** steps, and every one has a non-empty `evidence_id`.
- **The primary account always appears.** Every case has `VERIFY_RECORD_ABSENT account_service account_N` (10 of 10).
- **A retained security record usually appears.** `VERIFY_RECORD_PRESENT security_service audit_record_N` is in 7 of 10 cases; the exceptions are case_01, case_02 and case_04. This matches rule_12, SECURITY_AUDIT_LOG → RETAIN.
- The remaining verification steps list every other relevant record **in its compliant end state**:
  - `VERIFY_RECORD_ANONYMIZED analytics_platform` (rule_07);
  - `VERIFY_RECORD_REDACTED support_platform` (rule_05);
  - `VERIFY_DATA_FLOW_DISABLED integration_service data_flow_N`;
  - `VERIFY_RESTORE_BLOCKED backup_service backup_N` (rule_14);
  - `VERIFY_RECORD_REDACTED identity_service tombstone_N` (rule_15), in case_31.
- case_26, case_27 and case_28 are the fullest examples, with all six kinds of verification step.
- **COMPLETE does not depend on the reported status.** case_25, case_26 and case_28 are reported NOT_STARTED but are COMPLETE, and case_02 is reported PARTIALLY_COMPLETE but is COMPLETE.
- In the other direction, case_05, case_07, case_10, case_11, case_18, case_22, case_24 and case_30 are reported COMPLETE but are INCOMPLETE. **reported_status is noise.**

### 2.5 INCOMPLETE cases (22)

**Findings → remediation → verification mapping.** Every finding gets exactly one matching remediation and one matching verification on the same `(system_id, resource_id)`:

| Finding | Seen on | Remediation | Verification |
| --- | --- | --- | --- |
| REPORT_REMAINING_RECORD | account, search, support, export, analytics (case_12) | DELETE_RECORD | VERIFY_RECORD_ABSENT |
| REPORT_EXPOSED_PII | analytics_platform | ANONYMIZE_RECORD | VERIFY_RECORD_ANONYMIZED |
| REPORT_EXPOSED_PII | support_platform | REDACT_RECORD | VERIFY_RECORD_REDACTED |
| REPORT_EXPOSED_PII | identity_service tombstone (case_32) | REDACT_RECORD | VERIFY_RECORD_REDACTED |
| REPORT_ACTIVE_DATA_FLOW | integration_service data_flow_N | DISABLE_DATA_FLOW | VERIFY_DATA_FLOW_DISABLED |
| REPORT_RESTORE_RISK | backup_service backup_N (case_09, case_14, case_17) | BLOCK_RESTORE | VERIFY_RESTORE_BLOCKED |

The counts in INCOMPLETE agree: 21 REMAINING / 21 DELETE, 11 EXPOSED / (6 REDACT + 5 ANONYMIZE), 6 FLOW / 6 DISABLE, and 3 RESTORE / 3 BLOCK.

**Verification in INCOMPLETE covers more than the remediated records (resolves A15).** Two kinds of extra step always appear, even though their records were never findings:

- The **primary account** gets `VERIFY_RECORD_ABSENT account_service account_N` with empty evidence in all 22 cases. For example, in case_06 the account was not a finding but is still verified absent.
- The **retained security record** gets `VERIFY_RECORD_PRESENT security_service audit_record_N` in 17 of 22 cases. It is absent in case_05 to case_08 and case_10, the same "early" group that lacks it in COMPLETE.

The rule appears to be **verify the required final state of every relevant record**, not only remediated ones. Open question: does an already-compliant record (for example an analytics row that is already anonymized) also get a VERIFY step in INCOMPLETE? The sample never shows one, so it is unresolved.

Other findings from the INCOMPLETE cases:

- **Backups are never deleted (resolves A17).** All three restore-risk cases use REPORT_RESTORE_RISK → BLOCK_RESTORE → VERIFY_RESTORE_BLOCKED on `backup_service`, which matches rule_14 RETAIN.
- **Tombstone steps (resolves A16).** case_32 is REPORT_EXPOSED_PII → REDACT_RECORD → VERIFY_RECORD_REDACTED on `identity_service tombstone_9178`, with **no** VERIFY_RECORD_PRESENT for the tombstone. In COMPLETE case_31, `tombstone_440` is likewise only VERIFY_RECORD_REDACTED.
- **Support message vs attachment (A9), evidence so far:**
  - case_07 (an identity document sent to support) has `support_001` → REPORT_REMAINING_RECORD → DELETE. That is the attachment, rule_06.
  - case_10 has `support_002` → DELETE.
  - case_11, case_18, case_19, case_29 and case_30 have `support_N` → REPORT_EXPOSED_PII → REDACT. That is the message, rule_05; case_19's text says "messages also relate to another customer".
  - **Both use `system_id = support_platform`.** The category has to come from the evidence content, which pass 3 will look at.
- **Analytics is not always anonymized.** In case_12, `analytics_9914` is REPORT_REMAINING_RECORD → DELETE, while every other analytics finding is EXPOSED_PII → ANONYMIZE. The user changed email (see the request text), so this may be a record keyed by an old identifier, i.e. rule_02 SECONDARY_IDENTIFIER → DELETE. That will be checked against `evidence_01` in pass 4.
- The **account itself** is a finding only in case_05, case_16 and case_24 (REMAINING → DELETE).

### 2.6 Evidence citation patterns (resolves A5 and A7 in part)

- **Usually one evidence file per case.**
  - 31 of 32 cases cite a single `file_id` for every finding and every COMPLETE verification.
  - The exception is case_04, which cites `evidence_54` for `account_004` and `evidence_56` for `analytics_901`.
  - **No sample step cites an `activity_id` or `audit_id`.** Every cited ID is a `file_id`.
- **Shared bundle files.**
  - `evidence_92`: 10 cases, case_21 and case_23 to case_30.
  - `evidence_01`: 4 cases (case_12, case_15, case_17, case_19).
  - `evidence_03`: 3 cases (case_11, case_13, case_14).
  - `evidence_94`: 3 cases (case_03, case_18, case_20).
  - `evidence_05`: 2 cases (case_16, case_22).
  - `evidence_51`: 2 cases (case_31, case_32).
  - `evidence_54`: 4 cases (case_01, case_02, case_04, case_05).
  - Any one file can therefore hold many users, so case membership must come from file **contents**, as AG §6.6 says.
- **The cutoff is inclusive.** Every cited file has `captured_at <= audit_at`. In 7 cases it is **equal**: case_11, case_13 and case_14 (`evidence_03` at 2026-10-01T12:00:00Z), case_16 and case_22 (`evidence_05` at 2026-09-21T10:00:00Z), and case_31 and case_32 (`evidence_51` at 2026-09-15T12:00:00Z). So "at or before" includes the boundary.
- **The latest file is not always cited.** case_05 (audit_at 2026-09-08) cites `evidence_54`, captured 2026-09-02T23:00, which is six days before the audit. Whether a newer qualifying file existed, and so whether the rule is "latest file naming the resource" or something else, is checked in pass 4.

### 2.7 Open items carried forward

- A2: the `resource_id` collation is still untested.
- A15 (part): whether an already-compliant record gets a VERIFY step in an INCOMPLETE case.
- case_12: why analytics gets DELETE rather than ANONYMIZE.
- case_05: whether the cited file is the latest one.
- The support category signal (A9) has to come from evidence content.

---

## Pass 3 — Evidence formats

Scripts: `scratch/pass3_ts.py`, which compares the ISO timestamps inside each file with the manifest `captured_at`. Representative files were also read directly. PDFs were read with `pdftotext -layout`, and PNGs were viewed as images. **`tesseract` is not installed**, so PNG text needs a vision model or manual transcription.

There are 94 files: sql 24, json 28 (27 in `records/` plus 1 elsewhere), log 26, txt 1, pdf 4, png 11. **Each file holds many users**, mostly unrelated decoys, so case membership comes only from the identifiers inside.

### 3.1 How a record identifies its owner (across all shapes)

An owner is named by **one or more** of the fields below. Coverage varies by record; many records carry just one identifier and leave the rest `null`.

| Identifier | Example |
| --- | --- |
| `user_id` / `customer_reference` / `subject_reference` / `subject_selector` = `user_N` | `evidence_93` line 23: `backup_3933 … 'user_62'` |
| current or **historical** email, sometimes **UPPERCASE** | `evidence_93` line 29: `search_684 … 'JULES-LAURENT@PROTON.ME'` |
| `email_hash` (sha256) | `evidence_51` tombstone_9178 `email_hash 4f4b9c98…` |
| phone, current or old | `evidence_54` line 14 `+212 6 48 27 15 93` |
| full name | the PDFs and PNGs, e.g. `evidence_58` "Priya Raman" |
| a `subject_reference` that holds an **email instead of a user_id** | `evidence_29` line 29: `backup_4935 … "subject_reference":"j.castillo4893@gmail.com"` |
| `lookup_key`, `match_key` or `subject_key` on a log *started* line, joined to the *completed* line by `trace_id` | `evidence_94` lines 2–3: `trace_id=rb-074950-001 … lookup_key=charlotte.wright@outlook.com` then `… resource_id=account_2064 rows=0 http_status=404` |

**Some records carry no identifier at all.** Anonymized analytics rows and 404 account lookups name only the `resource_id`. Examples:

- `evidence_92` analytics_1895: every PII field is null.
- `evidence_92` account_3136: `status_code 404, profile null`.

Yet sample case_25 cites exactly these to verify ANONYMIZED and ABSENT. So **the resource → user link must come from elsewhere**: earlier evidence, `system_activity` rows for that resource_id, or `LINK_RESOURCE_IDENTITY`. Pass 4 will establish how.

### 3.2 Per shape

#### SQL (`databases/`, 24 files): SQLite-compatible, loadable with `sqlite3`

There are three layouts:

1. **Typed tables per system**, as in `customer_data_inventory_*` (e.g. `evidence_93`).
   - Tables: `customer_profiles`, `customer_search_documents`, `customer_analytics_profiles`, `support_records`, `customer_exports`, `connector_subscriptions`, `backup_restore_entries`, `security_audit_records`, plus `snapshot_scope(origin_system, captured_at)`.
   - The `snapshot_scope` table **declares which systems the snapshot covers**. That supports a closed-world absence claim, but only for the systems listed.
   - State columns:
     - `account_status`, e.g. `'DELETION_PENDING'` at line 20;
     - `enabled` 0/1 (line 26 `data_flow_2406 … '1'`);
     - `restore_allowed` 0/1 (line 24 `backup_4978 … '1'`, which is the case_09 restore risk);
     - `retention_until` on audit records.
   - A null PII column means the field has been removed.
2. **Primary vs replica tables**, as in `customer_accounts_failover_replica_*` (`evidence_54`), `*_read_replica_*`, `*_regional_replicas_*` and `*_reporting_replica_*`.
   - The same schema is repeated per topology: `customer_profiles_primary` vs `customer_profiles_failover_replica`.
   - In some files it is a generic `customer_data_primary(resource_id, system, collection, <json blob>, ts)`, with `customer_data_replica_ap_south`, `customer_data_replica_eu_west` or `customer_data_read_replica` alongside.
   - **Replication drift is the signal.** In `evidence_54`, `account_005` / `user_05` "Leila Haddad" appears **only** in `customer_profiles_failover_replica` (line 14) and not in `_primary` (lines 20–22). That makes it the case_05 REMAINING finding, because the replica still holds the deleted account.
3. **Single-system primary**, e.g. `customer_search_primary_20260910` (`evidence_57`): `search_documents_primary(resource_id, display_name, email, source_resource_id, indexed_at …)`.

There is also a header comment, `-- Captured at: …` / `-- Database topology: …` (`evidence_54` lines 3–4), or a trailing `-- snapshot_completed_at=…` (`evidence_93` line 43).

#### JSON (27 files in `records/`): several schemas

- **`service_resource_export_*`** (12 files, e.g. `evidence_92`).
  - Layout: `service_exports.<system>.<collection>[]`, one entry per probed resource, each with `observed_at`.
  - Collections and their state fields:

    | Collection | State fields |
    | --- | --- |
    | account `profile_lookups` | `status_code` 404/200 and `profile` |
    | analytics `profiles` | PII fields nullable |
    | backup `restore_entries` | `restore_allowed` bool |
    | export `exports` | — |
    | integration `connectors` | `enabled` bool, `last_delivery_status` |
    | search `index_queries` | `query` plus `hits.documents[]`, `hits.total` |
    | security `audit_records` | `retention_until` |
    | support `tickets` | requester_* fields, `message_excerpt` |

- **`customer_data_snapshot_bundle_*`** (12 files, e.g. `evidence_51`).
  - Layout: `snapshots[] {captured_at, data_store, collection, records[]}`.
  - An **empty `records` list** is evidence of absence for that collection. For example, `evidence_51` account_service `customer_profiles` has `records: []`.
  - Tombstones live in `identity_service.deleted_customer_references`, with `subject_reference`, PII fields and `account_status: DELETED`. Examples: `tombstone_440` is all-null, so it is REDACTED; `tombstone_9178` still has name, email, phone and hash, so its PII is EXPOSED (case_32).
  - The per-snapshot `captured_at` can be **earlier** than `exported_at`. In `evidence_12` they range 2026-08-11 to 2026-08-19, so the observation time for a record is the snapshot's time, not the file's.
- **Flat result registers** (`connector_configurations_*` `evidence_13`, `customer_export_manifest_*`, `customer_export_jobs_*` `evidence_59`, `customer_analytics_report_*` `evidence_56`, `security_audit_ledger_*` `evidence_50`).
  - `records[] {recorded_at, system, resource_id, record_type, result, subject_reference}`.
  - **`record_type` gives the data category directly** (USER_PROFILE, …), and **`result` gives the state** (NOT_FOUND, …).
  - Export jobs carry `created_at`, `expires_at` and `download_available` (`evidence_59` lines 10–12).

#### LOG (`logs/`, 26 files): about 7 dialects of the same events

| Dialect | Example |
| --- | --- |
| logfmt | `evidence_01`, `evidence_94`, `evidence_93`-style |
| bracketed `[LEVEL] [service]` | `evidence_16`, `evidence_44` |
| cloud-runtime with escaped `message="…"` | `evidence_25`, `evidence_53` |
| pipe-delimited | `evidence_21`, `evidence_48` |
| timestamp + JSON object | `evidence_06`, `evidence_34` |
| RFC5424 syslog `<15>1 node-N …` | `evidence_11`, `evidence_39` |
| key=value record dumps with `record_type` | `notification_delivery` `evidence_41`, `search_index_diagnostic` `evidence_08` |

- **Readback traces** (`resource_lookup_trace_*`, e.g. `evidence_94`):
  - The `*_started` line carries `lookup_key` (an email or user_N).
  - The `*_completed` line carries the resource and its state: `rows=0 http_status=404`, `enabled=false`, `restore_allowed=false`, `result=hit total_hits=1`, `requester_email=…`.
  - The two lines are joined on `trace_id`.
- **Service-event logs** (`evidence_01`) mix relevant traces with noise (`dns_cache`, `secret_agent`, `webhook_delivery`).
  - The identifier appears as `match_key="…"` or `subject_key="…"` on the started line. The `resource_id` only appears on the completed line of the **same `trace_id`**. Example: `evidence_01` lines 2 and 6, `tr-5887496` `g.silva76.jr@gmail.com` → `search_1874 result=hit`.
  - The intervening `dependency_retry` and `dependency_recovered route=primary` lines are noise. They may also signal *which store* answered (`pool=search_service_replica`).
  - Note the look-alike `g.silva76.jr@gmail.com` vs `g.silva76@gmail.com`, which is the identity `activity_4001` links to user_13.

#### TXT (1 file): `customer_account_handover_20261001.txt` (`evidence_03`)

- Pipe-delimited shift handover rows: `time | system | resource_id | CATEGORY | STATE | identifier`.
- **The category is explicit**, which settles A9 where it is present:
  - line 43: `support_4218 | SUPPORT_ATTACHMENT | FOUND | noor-khalil@proton.me` → DELETE (sample case_13);
  - line 46: `support_864 | SUPPORT_MESSAGE | IDENTIFIABLE | novak.tomasz@icloud.com` → REDACT (sample case_11).
- State vocabulary: NOT_FOUND, FOUND, IDENTIFIABLE, ANONYMIZED, REDACTED, ACTIVE, DISABLED, BLOCKED.
- **Some rows carry no identifier**, e.g. line 17 `analytics_6830 | ANONYMIZED | no direct identifier`.
- Identifiers mix lowercase, UPPERCASE and user_N.

#### PDF (4 files in `documents/`): business documents with no verdict

- `delivery_correction_attachment.pdf` (`evidence_58`) is a support attachment `support_001` / CS-4827 for "Priya Raman, priya.raman@gmail.com, +91 98765 73142", uploaded 18 Jun 2026. It is the case_07 REMAINING finding, as a SUPPORT_ATTACHMENT.
  - **Look-alike:** `evidence_54` line 17 has "Priya Ramanathan, p.ramanathan@gmail.com", a different user.
- `account_history_report_20260718.pdf` (`evidence_18`) is a customer statement naming "Ingrid Dahl, user_18, ingrid.dahl@outlook.com", order ORD-20261260. That is the repeated subject from eval case_33 and case_52. It has **no `resource_id`**, so it is unclear which system or resource it evidences.
- `legal_retention_register_20260529.pdf` (`evidence_27`) is a disputed-order register: `ORD-… | user_08 | Card dispute | … | Retain until 04 May 2033`. It is the supplied "legal hold" for rule_13. There is no `legal_hold_N` resource_id in the text, so the mapping to resources is open.
- `security_retention_extract.pdf` (`evidence_55`): `audit_record_003`, subject user_03, retain until 25 Aug 2027. This is the "supplied retention period" for rule_12.
- Dates inside PDFs are human-format ("18 Jun 2026", "05 Sep 2026 06 30 UTC") and need custom parsing.

#### PNG (11 files in `images/`): admin-console screenshots

- `backup_restore_console_20260429.png` (`evidence_32`) is a Vault Recovery Manager table of archives (backup_9286, 9287, 9288, 9291) with Account emails. The detail pane shows `backup_9287 · areed1433@gmail.com`, Created 26 Apr 2026, Retention end 26 Jul 2026.
  - There is **no explicit restore_allowed field**; the activity pane shows "backup_9286 restored · Completed".
  - It ties to `activity_4006` (backup_9287 → user_16) and `activity_3387` (RESTORE_BACKUP backup_9287 repopulated search_4882).
  - It also contains decoy rows (`miller.logistics@company.com`, etc.).
- `support_ticket_console_20260524.png` (`evidence_28`) is the Helpline Console for ticket CS-5034, `support_1034`, "Kofi Agyeman, kagyeman8947@fastmail.com".
  - The conversation includes agent **Maya Chen** and an order, which is the *shared agent/order context* in rule_05. So this is a SUPPORT_MESSAGE → REDACT, not DELETE.
  - It ties to `activity_4005`, which links support_1034 → user_22.
- Times in screenshots are partial ("26 Apr 02:00", "09:12") or human dates. **The year is often implied.**
- Other screens (from file names; full transcription comes in pass 4 where cited): account admin console, search index inspector, connector management, analytics profile view, customer export console, security audit explorer, deleted-account reference (tombstone), object storage browser, marketing profile console.

### 3.3 Timestamps inside files vs manifest `captured_at`

From `scratch/pass3_ts.py`:

- **In-file event times usually run *up to* `captured_at`.** For example, `evidence_06` spans 2026-09-10 to 2026-09-18 with capture 09-18T11:55:24Z, and `evidence_94` starts 07:49:50, about 3 hours before its 10:38:56 capture.
  - So a single file can hold several observations of the same resource at different times, and **the latest one at or before `audit_at` wins**.
  - For a file captured before `audit_at` this is moot, but the order inside the file still matters.
- **Stamps after `captured_at` are all legitimate future-dated fields, not later observations.**
  - `retention_until` / "Retain until": 2031–2034, e.g. `evidence_93` line 31.
  - Export `expires_at`: `evidence_59` line 11 `2026-10-04T16:11:00Z`.
  - `evidence_29` line 31: `export_9860 … "expires_at":"2026-06-18T06:00:00Z"`.
  - No file contains an *observation* timestamp later than its manifest `captured_at`, so the manifest time is a safe upper bound for "when this was known".
- **Possible trap:** an export with `expires_at` before `audit_at` but `download_available: true`. It is unclear whether the expiry means it is gone (absent) or still a remaining record. Pass 5 will look at this.
- `snapshot_bundle` internal `captured_at` values can be **days earlier** than the file's `exported_at` / manifest time (`evidence_12`: 08-11 and 08-17 vs 08-19). When judging "state at `audit_at`", use the per-snapshot time.

### 3.4 Implications for the parser

- Per-shape adapters are needed:
  - 3 SQL layouts (load each with `sqlite3`);
  - about 5 JSON schemas;
  - about 7 log dialects, normalised to `(ts, service, trace_id, event, k=v…)` and then joined by `trace_id`;
  - the txt handover;
  - `pdftotext` for PDFs;
  - vision or manual transcription for the 11 PNGs.
- Normalise every observation to the shape `(file_id, observed_at, system_id, resource_id, category?, state, identifiers{user_id, emails, hashes, phones, names})`.
- The category comes from explicit `record_type` / CATEGORY fields where present, otherwise from the system and collection: support_platform splits into message vs attachment, analytics, and so on.
