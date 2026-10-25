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

---

## Pass 4 — Cross-checks of sample citations

Script: `scratch/pass4_cites.py`, with output in `scratch/pass4_out.txt`. For every step in `sample_output.csv`, it greps the resource_id (word-bounded) in the cited file and in every other evidence file (PDFs via pdftotext), and lists the `system_activity` rows for that resource. PNGs were checked by viewing them.

### 4.1 Is the cited resource named in the cited file?

**Yes for 85 of 89 cited steps.** Examples with line numbers:

| Case | Resource | Cited file and line |
| --- | --- | --- |
| case_05 | account_005 | `evidence_54` line 13 |
| case_06 | search_001 | `evidence_57` line 9 |
| case_09 | backup_4978 | `evidence_93` line 24 |
| case_11 | search_052 / analytics_2034 / support_864 / data_flow_9522 | `evidence_03` lines 26, 16, 46, 25 |
| case_12 | analytics_9914 | `evidence_01` line 92 |
| case_26 | all six steps | `evidence_92` lines 40, 309, 349, 78, 194, 121 |
| case_32 | tombstone_9178 | `evidence_51` line 26 |

**The 4 exceptions are all `VERIFY_RECORD_ABSENT` on `account_service` in COMPLETE cases.** Each cites a file that covers the account store but does **not contain** the account:

| Case | Resource | Cited file | How absence is shown |
| --- | --- | --- | --- |
| case_01 | account_001 | `evidence_54` | Neither `customer_profiles_primary` (lines 20–22) nor `customer_profiles_failover_replica` (lines 13–17) lists it. |
| case_02 | account_002 | `evidence_54` | same |
| case_04 | account_004 | `evidence_54` | same; **account_004 appears in no file and no activity row at all** |
| case_31 | account_4857 | `evidence_51` | The account_service `customer_profiles` snapshot is `records: []` (lines 4–8). |

- **Rule:** absence can be proven by a snapshot that covers the system or table and omits the resource. That is a *closed-world* proof.
- Positive absence evidence also exists and is cited when available:
  - 404 lookups: `evidence_92` line 10 `account_3136 … status_code 404`;
  - `rows=0 http_status=404` in `evidence_94` lines 18–19 for account_7566;
  - `NOT_FOUND` rows in `evidence_03` line 9 for account_3677.

### 4.2 How each state is proven (the observed state field per operation)

| Step | Proving field in the cited file |
| --- | --- |
| VERIFY_RECORD_ABSENT | `status_code 404` / `rows=0` / `NOT_FOUND`, or omission from a covering snapshot (4.1) |
| REPORT_REMAINING_RECORD | the row exists with the user's identifiers. Examples: `evidence_54` line 13 "Leila Haddad, +212 6 48 27 15 93"; `evidence_57` line 9 jonas.berg; `evidence_03` line 43 `support_4218 FOUND` |
| REPORT_EXPOSED_PII | the record exists **and** still holds an identifier that policy says to remove. Examples: `evidence_03` line 16 `analytics_2034 IDENTIFIABLE novak.tomasz@…`; `evidence_51` line 26 tombstone_9178 with name, email, phone and hash |
| VERIFY_RECORD_ANONYMIZED / _REDACTED | the record exists with all PII fields null. Examples: `evidence_92` line 60 analytics_1895; `evidence_51` line 17 tombstone_440 |
| VERIFY_RECORD_PRESENT (audit_record) | the record exists, e.g. `evidence_92` line 309 audit_record_5416 with `retention_until` |
| REPORT_ACTIVE_DATA_FLOW | `enabled=true` / `ACTIVE`, e.g. `evidence_03` line 25 data_flow_9522 ACTIVE |
| VERIFY_DATA_FLOW_DISABLED | `enabled=false`, `stopped`, e.g. `evidence_92` line 194 data_flow_6244 |
| REPORT_RESTORE_RISK | `restore_allowed=1` / `ACTIVE`, e.g. `evidence_93` line 24 backup_4978; `evidence_03` line 19 backup_3870 |
| VERIFY_RESTORE_BLOCKED | `restore_allowed=false` / `BLOCKED`, e.g. `evidence_92` line 121 backup_3120 |

### 4.3 Is the cited file captured at or before `audit_at`? Is it the latest?

- **It is always at or before** (see 2.6 for the 7 equal-time cases).
- **The cited file is always the latest file at or before `audit_at` that names the resource.** Later files exist and are skipped:
  - case_09 (audit 09-16T09:00): backup_4978 is also in `evidence_06` line 83, captured **09-18**, which is after the audit. The sample cites `evidence_93` (09-16T08:37).
  - case_21 to case_30 (audit 09-15T12:00): every resource is also in `evidence_02` (`customer_data_snapshot_bundle_20260917.json`, captured **09-17**). Examples: line 43 account_5334, line 299 data_flow_6244, line 251 backup_3120. The sample cites `evidence_92` (09-15T11:44:55).
  - **`evidence_02` is the main "later evidence" trap;** it is checked against `evidence_92` for contradictions in pass 5.
- In case_12, case_15, case_17 and case_19 (audit 09-15T12:00), the cited file is `evidence_01` (09-15T11:59:39), not `evidence_92`, because these users' resources are only in `evidence_01`. **The rule is "the latest file naming that resource", not "the latest file overall".**

### 4.4 How a resource is tied to the user (the hard part)

On the cited line itself, the user's identifier is **often absent**:

| Linkage | Where the identifier lives | Examples |
| --- | --- | --- |
| Same line names the user | The cited line carries the email, name, phone, hash or user_N. | `evidence_03` (all), `evidence_05` (case_16, case_22), `evidence_54` (case_05) |
| Hash only | The cited line carries the user's **email_hash**. | `evidence_01` line 92 for case_12 `analytics_9914`: `44a65154…`, which is sha256 of a user_12 email (current or historical) |
| Paired log lines | The *started* line (identifier) and *completed* line (resource) share a `trace_id`. | `evidence_94`: case_03 account_7566 lines 18–19 via `l.fontaine46@yahoo.com`; case_18 lines 10–11, 22–25, 52–53 via `mori.ren@gmail.com` |
| **Not on the line** | `evidence_92` rows for 404 accounts, null-PII analytics and support, and audit_records carry **no user identifier**. Some entries carry `customer_reference=user_N` (backup_3120 → user_26, data_flow_2295 → user_27). | case_21, case_25 to case_28 |
| Different file | `evidence_58` names "Priya Raman / priya.raman@gmail.com" on a different line from `support_001`. | case_07: lines 2/9 vs 12–14 |

**How null-identifier resources still get attributed**, from the evidence in this pass:

- **(a) Earlier observations.** A resource seen *before* deletion in an earlier file can carry the identifier. That will be tested in the build phase by indexing every file.
- **(b) `customer_reference` siblings in the same export.**
- **(c) Deletion-worker activity bursts.**
  - Each user's workflow appears as a run of `deletion_worker` activity rows within roughly 1–3 hours, starting with `DELETE_RECORD account_N`.
  - Example for case_26 / user_26: `activity_3600` (11:08, account_5684), `3603` analytics_4566, `3605` support_4715, `3606` data_flow_6244, `3607` backup_3120 (11:52).
  - **Bursts of different users interleave on the same day.** On 2026-09-02, `activity_3597` (account_3136, case_25), `3599` (account_5334, case_24) and `3601` (account_7225, an unrelated or eval user) fall in the same 30 minutes. A burst alone does not determine ownership; it needs an anchor resource that *is* linked, such as backup_3120 → user_26.
  - **The activity `details` never name the user**, except the 12 `LINK_RESOURCE_IDENTITY` rows.
- **(d) PNG consoles give explicit links.**
  - `evidence_04` (`account_admin_console_20260926.png`) shows "Haruka Sato · user_11 · account_5762", email haruka.s1838@zoho.com, support `CS-8538 · support_9538`. This is eval case_34 (haruka.s1838@zoho.com).
  - `evidence_37` (`security_audit_explorer_20260905.png`) shows Subject filter `user_03` with audit_record_001 to 006 and the detail for audit_record_003 (`account_closure_recorded`, recorded 2026-08-25T04:03:00Z). That matches `evidence_55` (PDF) for audit_record_003.

### 4.5 Gold verification resources with no visible source (unreachable)

Some INCOMPLETE verification steps use `evidence_id = ""`, so they need no citation. But the **resource_id** still has to come from somewhere:

| Case | Resource | Where it appears |
| --- | --- | --- |
| case_18 | `audit_record_6645` | **nowhere**: no evidence file (PDF text included), no activity row |
| case_20 | `audit_record_5569` | **nowhere** |
| case_18 | `account_5521` | only `activity_3732` (2026-09-09T09:52, DELETE_RECORD SUCCESS, no user named) |
| case_20 | `account_5037` | only `activity_3734` |
| case_22 | `account_4990` | only `activity_3573` |
| case_23 | `account_410` | only `activity_3662` |
| case_29 | `account_7012` | only `activity_3532` |
| case_30 | `account_4163` | only `activity_3465` |
| case_32 | `account_8858` | only `activity_3685` |
| case_04 | `account_004` | nowhere at all, yet COMPLETE cites `evidence_54` for its absence |

- user_50 (case_18) and user_48 (case_20) are not named in **any** evidence file. Their links exist only through email `lookup_key`s in `evidence_94`.
- **Implication.** Some gold resource IDs, especially the primary `account_N` and the retained `audit_record_N`, can only be derived from activity-burst membership. A few cannot be derived at all. Expect a ceiling below 100% on step-level accuracy, and **do not overfit** heuristics to reach them.
- The best available approach is to attach to the user the `DELETE_RECORD account_service` row in the same burst as the user's linked resources (case_18: `activity_3732` 09:52, then `3744` support_5569 11:43, `3747` search_4013, `3751` analytics_037, `3753` data_flow_4890). That needs disambiguation where bursts interleave (`activity_3734` account_5037 at 10:14 belongs to case_20).

### 4.6 Answers to the carried-forward questions

- **case_12, analytics DELETE vs ANONYMIZE.** `evidence_01` line 92 shows `analytics_9914` identified only by an **email_hash of user_12**. Combined with the user changing email, the record is keyed by an old identifier. It is still REPORT_REMAINING_RECORD → DELETE in the sample, so the category is probably SECONDARY_IDENTIFIER (rule_02 DELETE). The exact category text is still to be confirmed in the build phase.
- **case_05, the cited file.** `evidence_54` (09-02) is the latest file at or before audit (09-08T13:40) that names `account_005`. It is cited because it is the **latest file naming the resource**, which confirms the rule in 4.3.
- **A9, message vs attachment.** The category comes from explicit labels where they exist (`evidence_03` CATEGORY column), and otherwise from content:
  - `evidence_58` is an uploaded PDF file with "uploader customer" and "file delivery_address_correction.pdf", i.e. an attachment.
  - `evidence_28` (PNG) is a conversation including an agent, i.e. a message with shared context.

---

## Pass 5 — Traps

Script: `scratch/pass5_traps.py`, plus direct inspection of the lines quoted below.

### 5.1 Look-alike emails

- The evidence holds **769 distinct known emails** (current or historical) and **22 unknown emails**. 19 of the unknown ones are near-copies of a real user's email (SequenceMatcher ratio ≥ 0.85). **They are decoys and must not match.**
- **Pattern 1, a `.jr` suffix** (15 cases). Examples:
  - `evidence_01` line 2: `match_key="g.silva76.jr@gmail.com"` vs user_13 `g.silva76@gmail.com`. The trace `tr-5887496` resolves to `search_1874`, which is therefore **not** user_13's;
  - `evidence_02` line 31: `smartinez6461.jr@gmail.com` vs user_28;
  - `evidence_06` line 8: `zulu.lindiwe.jr@gmail.com` vs user_62;
  - also `evidence_07`, `evidence_10`, `evidence_25`, `evidence_29`, `evidence_31`, `evidence_36`, `evidence_38`, `evidence_40`, `evidence_43`, `evidence_44`, `evidence_45` and `evidence_47`.
- **Pattern 2, sibling names in the same file as the real subject.**
  - `evidence_57` lines 10–11: `jonas.berglund@outlook.com` and `joana.berg@outlook.com` next to user_06 `jonas.berg@outlook.com` on line 9 (sample case_06 cites only `search_001`, line 9).
  - `evidence_61` line 8: `nadia.popescu@yahoo.com`. user_10's real history is nadia.ionescu → nadia.petrescu → n.petrescu (`audit_121`, `audit_238`), so **popescu is a decoy that resembles a historical name**.
  - `evidence_54` line 14: "Karim El-Masri, karim.elmasri@gmail.com" vs user_01 "Amina El-Masri, amina.elmasri@gmail.com". Also line 15 "Mateo Rios Gil" vs user_02 "Mateo Ríos", and line 17 "Priya Ramanathan, p.ramanathan@gmail.com" vs user_07 "Priya Raman".
- **Rule.** Match identifiers **exactly** after lowercasing: email, `user_N`, sha256 hash, or normalised phone. **Never** match by fuzzy email or by name alone.
  - Sample case_28's text even warns: "A search result with a similar email belongs to someone else."

### 5.2 Primary vs replica drift

Loading every SQL file into SQLite shows **11 snapshots with drift**. In every one, a resource exists **only in the replica**: deleted from the primary, still present in the copy. No rows exist only in the primary, and no shared row has different fields.

| file | captured | tables | replica-only |
| --- | --- | --- | --- |
| evidence_54 | 2026-09-02 | customer_profiles_primary vs _failover_replica | account_005 (= sample case_05 REMAINING) |
| evidence_05 | 2026-09-21 | customer_data_primary vs _read_replica | account_994 (= sample case_16 REMAINING, line 52) |
| evidence_10 | 2026-08-27 | primary vs read_replica | account_6345 |
| evidence_15 | 2026-08-02 | primary vs read_replica | account_8023 |
| evidence_20 | 2026-07-08 | primary vs read_replica | account_4348 |
| evidence_24 | 2026-06-13 | primary vs read_replica | account_3150, account_9608 |
| evidence_29 | 2026-05-19 | primary vs replica_ap_south | account_585 |
| evidence_33 | 2026-04-24 | primary vs replica_eu_west | account_6539, account_8105 |
| evidence_38 | 2026-03-30 | primary vs replica_ap_south | account_5389 |
| evidence_43 | 2026-03-05 | primary vs reporting_replica | account_3183 |
| evidence_47 | 2026-02-08 | primary vs reporting_replica | account_1035 |

- **A primary 404 or omission is not enough.** Any replica table in the same snapshot must also lack the record.
- The sample reports the replica copy under `system_id = account_service` with the account's own `resource_id`. There is no separate replica system_id (case_05, case_16).

### 5.3 Later observations that contradict earlier ones

- **Resurrection inside one file.** `evidence_30` (`service_events_sa_east_20260516.log`):
  - line 92, 2026-05-14T11:58:45Z: `account_2088 profile_lookup_completed rows=0 http_status=404`;
  - line 109, 2026-05-16T11:58:23Z: same lookup_key `lars.e5052@outlook.com`, **`rows=1 http_status=200`**, read via `pool=account_service_replica` then `route=primary`.
  - The account came back between the two lookups. **The latest observation at or before `audit_at` wins**, so in-file ordering by timestamp is required.
- **A later file contradicts an earlier one.** `evidence_02` (`customer_data_snapshot_bundle_20260917.json`, manifest 09-17) vs `evidence_92` (09-15T11:44:55):
  - `evidence_02` lines 519–530 (internal snapshot `captured_at 2026-09-17T12:00:00Z`) show **`account_3866` ACTIVE**, with customer_reference user_27, "Ananya Nair", ananya-nair@gmail.com.
  - `evidence_92` line 16 has the same account as `status_code 404` on 09-15.
  - Sample case_27 (audit 2026-09-15T12:00) is **COMPLETE** with `VERIFY_RECORD_ABSENT account_3866` citing `evidence_92`. **The post-audit resurrection must be ignored** for that case, and it would make any later case on user_27 INCOMPLETE.
- **The other `evidence_02` rows agree with `evidence_92` on state.** There are 31 shared resources:
  - `backup_3120` `restore_allowed false`;
  - `data_flow_6244` `enabled false`;
  - `data_flow_3827` / `data_flow_8524` `enabled true`;
  - `support_4715` `"message_text": "[REDACTED]"`.
  - `evidence_02` usually carries **more identifiers**: user_N, full name, phone, hash.
- **New ambiguity A23.** `evidence_02` is one file with manifest `captured_at` 09-17, but it contains **internal snapshots dated earlier**: 09-09T12:00 at lines 4–20, and 09-15T09:00 and 09-15T12:00 from line 22 onward.
  - The 09-09 snapshot shows `account_5684` ACTIVE for user_26, which is the only place that **links account_5684 to user_26** (case_26).
  - The sample never cites `evidence_02` for audit_at 09-15, consistent with excluding the whole file by manifest time.
  - It is undecided whether internal sub-snapshots at or before `audit_at` may be used for *identity linking* (not citation).
  - **Proposed default:** filter by manifest `captured_at` for both evidence and linkage, because AGENTS.md §6.2 says "Evidence created later must not change the answer". This goes to the decision log.

### 5.4 Files captured after audit_at

- **Every eval case has at least one file captured after its `audit_at`,** because the latest capture is 2026-10-01T12:00. The time filter is mandatory.
- In **16 eval cases** the subject's text identifiers (email, user_N or hash, current or historical, not phone) appear **only** in files captured after `audit_at`. Examples:
  - `case_35` (user_13), `case_39` (user_14), `case_50` (user_20) and `case_55` (user_16): only `evidence_01` (09-15);
  - `case_52` (user_18, audit 06-19): only `evidence_01` and `evidence_18` (PDF, 07-18);
  - `case_53` (user_22): only `evidence_02`;
  - `case_61` (user_07): only `evidence_58` (09-12);
  - `case_534`: only `evidence_50`.
- For these cases there is no citable participant evidence at the audit time. COMPLETE is impossible to prove, which argues for INCOMPLETE or a different link such as activity or PNG. **This needs a decision.**
- `case_63` (user_09) is named in **no text-format evidence at all**. Its only link is the PNG `marketing_profile_console.png` (`evidence_60`) and `activity_4008` (`marketing_001` → user_09). That makes it a PNG-only case.

### 5.5 Requests that are not deletions

- The 10 non-deletion texts (case_533 to case_542, listed in §1.8) are **corroborated by activity and evidence**:
  - The 10 `CLASSIFY_REQUEST` rows (`activity_3486` … `activity_3827`, "classified … as non-deletion; no destructive action was authorized") name `account_N`s.
  - `evidence_50` (`security_audit_ledger_20261001.json`) maps each of those accounts to a non-deletion requester's email with `result FOUND`. Examples:
    - `account_1733` → haruka-kato@gmail.com (case_533);
    - `account_2176` → ieriksen5151@fastmail.com (case_540);
    - `account_228` → omar.nasser@gmail.com (case_542);
    - `account_2461` → elena.h3070@zoho.com (case_541).
  - The accounts still exist, as they should. **These 10 cases are `NOT_APPLICABLE` with `[]`.**
- The classification must come from `request_text`; activity is only a claim. `evidence_50` is captured 10-01, after most of their audit_at dates (09-22 to 10-01), so it is not usable as evidence anyway.
- **Trap wording:**
  - case_538 "Please **remove** me from marketing lists only";
  - case_536 "Do not close the account";
  - case_539 "not a request to erase it".
  - A keyword classifier on "remove", "delete" or "erase" would misfire. Use an LLM or a negation-aware rule.
- **The reverse trap was not found.** No deletion request is phrased so that it looks like a non-deletion one. All 508 others use the 17 deletion templates in 6 languages.
- `case_52` vs `case_33` (the same user_18, a month apart) is a *temporal* trap. The same subject gets different evidence windows and possibly different answers. For example, `activity_4004` links export_1260 inside case_52's window, and `activity_4009` links export_1842 inside case_33's.

### 5.6 Summary of traps, as a checklist for the builder

1. Exact identifier matching only; reject `.jr` and sibling-name look-alikes (5.1).
2. Lowercase request emails, since 20 eval requests are UPPERCASE (1.7).
3. Resolve historical emails and hashes through the audit chain, including users with two changes (1.6).
4. Check **every** replica table in a SQL snapshot, not just the primary (5.2).
5. Order observations by time **inside** files; the latest at or before `audit_at` wins (5.3, `evidence_30`).
6. Drop every file whose manifest `captured_at` is after `audit_at`, even if its sub-snapshots are earlier (5.3, `evidence_02`; A23 open).
7. Treat `reported_status`, `reported_result` and activity `details` as claims (2.4: whether reported_status is COMPLETE disagrees with the true status in 15 of 32 samples: case_02, 05, 07, 10, 11, 12, 14, 15, 18, 22, 24, 25, 26, 28, 30).
8. Non-deletion detection must be negation-aware (5.5).
9. The same user can appear in several cases with different audit windows (5.5, case_33/case_52).
10. Some gold resources are unreachable (4.5). Do not hard-code them.

---

## Loop outcome

All 5 passes are done, and each one added new findings. The loop stops here, as the prompt asked.

New ambiguity: **A23**, sub-snapshots inside a post-audit file. Ambiguities closed by data:

- A1 (eval IDs are unpadded; numeric order is likely);
- A5 and A7 (cite the latest file at or before `audit_at` that names the resource; the boundary is inclusive);
- A9 (category label or content: message REDACT vs attachment DELETE);
- A15 (INCOMPLETE verifies the primary account plus the retained audit record plus every remediated record);
- A16 (tombstone is redact plus verify-redacted only);
- A17 (backup is BLOCK, never DELETE).

Still open: A2 (resource_id collation), A3 (dependency order vs sort key), A23, the 16 eval cases with only post-audit evidence (5.4), and the unreachable gold resources (4.5).

---

## Correction to Pass 5 §5.4 (after the recount in docs/03_ID_RECOVERY_PROTOTYPE.md §5)

The "16 eval cases with only post-audit evidence" count was **wrong**. It ignored PNG screenshots and phone numbers. Recounting with every identifier type, and with all 11 PNGs transcribed, gives:

| Pre-audit files naming the subject | Eval cases |
| --- | --- |
| 0 | 11 |
| 1 | 503 |
| 2 | 4 |

- **9 of the 11 are non-deletion requests** (case_534 to case_542), which need no evidence.
- The two deletion cases, **case_61** and **case_63**, are screenshot-only cases whose person link rests on `LINK_RESOURCE_IDENTITY` activity claims (`activity_4007` / `activity_4008`).
- In case_63, the screenshot `evidence_60` shows a different, unknown person (sj.park@naver.com) for `marketing_001`.
