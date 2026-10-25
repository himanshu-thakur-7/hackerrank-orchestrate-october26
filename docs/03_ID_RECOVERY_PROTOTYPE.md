# 03 — Prototype: recovering account and analytics IDs from the request row

**Question.** Gold answers name `account_N` and anonymized `analytics_N` IDs that no pre-audit evidence ties to the person's email. Can a system recover them from participant-visible data captured at or before `audit_at`?

**Prototype.** The throwaway scripts live in `scratch/`, which is gitignored and not committed. Each one runs with `python3 -I scratch/<name>.py`.

| Script | Purpose |
| --- | --- |
| `proto_account_link.py` | gold-account activity timing |
| `proto_account_heuristic.py` | H1 window heuristic, its sensitivity, and the H2 downstream offsets |
| `proto_account_assign.py` | H1 plus the evidence filter and global one-to-one elimination, and H2 batch attribution |
| `proto_account_a23.py` | the same, plus pre-audit sub-snapshots inside later files used for linking (ambiguity A23) |
| `proto_account_final.py` | rank tie-break, plus the hand-written / 42 h regimes |
| `proto_analytics.py` | H4, anonymized analytics recovery |
| `proto_ident_index.py` / `proto_png_transcripts.py` | identifier index and the manual transcription of all 11 PNGs |
| `proto_recount.py` | the evidence recount (§5) |

Per the user's instruction, no throwaway branch was created. The code stays in `scratch/` and only this verdict is committed.

---

## 1. Timing of DELETE_RECORD → account_service vs the request row

Source: `proto_account_link.py`. The sample data contains **three regimes**:

| Regime | Cases | `reported_at − requested_at` | Gold account delete vs `reported_at` | `reported_result` vs `reported_status` |
| --- | --- | --- | --- | --- |
| **Generated** | samples case_09, case_11 to case_32 (23); **eval 506 of 518** | exactly **24 / 48 / 72 h** | **0.75 to 1.23 h before** | **23/23 match**: COMPLETE↔SUCCESS (11), NOT_STARTED↔FAILED (10), PARTIALLY_COMPLETE↔PARTIAL (2) |
| Hand-written samples | case_01 to case_08, case_10 | irregular (13.32 h to 55.47 h) | −0.14 to +0.06 h (at `reported_at`); `account_004` has **no activity at all** | 6/8 match; case_06 and case_08 are PARTIALLY_COMPLETE but SUCCESS |
| **42 h eval family** | eval case_33, 34, 35, 39, 45, 46, 50, 52, 53, 55, 61, 63 | exactly **42 h** | **no account delete anywhere near `reported_at`** | — |

Example rows from the generated regime:

| Case | Activity | Account | Result | Before `reported_at` |
| --- | --- | --- | --- | --- |
| case_26 | `activity_3600` | account_5684 | FAILED | 0.85 h |
| case_24 | `activity_3599` | account_5334 | SUCCESS | 1.01 h |
| case_19 | `activity_3323` | account_9102 | PARTIAL | 1.13 h |

- The activity `details` for the generated regime always read "Deletion worker submitted primary profile account_N to account_service."
- The hand-written regime reads "…reported the requested operation as completed. Target resource: account_N."
- **No column names the user.** The only correlates with the request row are the time offset from `reported_at` and `reported_result` ↔ `reported_status`.

---

## 2. The primary-account heuristic (H1) and how it scores

The candidates for a case are the `DELETE_RECORD` rows with target `account_service` where:

- `event_time` is in `[reported_at − 1.5 h, reported_at − 0.5 h]`;
- `event_time` is at or before `audit_at`;
- `reported_result` equals `RESULT_OF[reported_status]`.

Exact unique hits on the 32 samples:

| Variant | Hits | Ambiguous | Wrong | None |
| --- | --- | --- | --- | --- |
| H1: window plus result match | 12 | 12 | 0 | 8 |
| H1 without the result match | 1 | 23 | 0 | 8 |
| H1 + pre-audit evidence filter (drop accounts tied to *another* user; keep one tied to *this* user) | 17 | 7 | 0 | 8 |
| H1 + global one-to-one elimination across all 550 requests | 12 | 12 | 0 | 8 |
| H1 + evidence + global | **19** | 5 | 0 | 8 |
| … + A23 links (pre-audit sub-snapshots inside a post-audit file; linking only) | **21** | 3 | 0 | 8 |
| … + **rank tie-break** (tied cases sorted by numeric case_id ↔ tied deletes sorted by time) | **23** | 0 | **1** (case_23) | 8 |

- **The 8 "none" are the hand-written samples.** A separate ±15-minute window around `reported_at` (any result) finds the gold account for 7 of 8. The eighth, `account_004`, exists nowhere. Eval has **no** cases in this regime, so this rule does not need to ship.
- **Remaining ambiguity on the samples:**
  - case_23 is a triple (account_410, account_7015, account_9155) and the rank tie-break picks the wrong one;
  - case_28/case_29 are a symmetric pair resolved only by the rank tie-break;
  - case_25/case_26 are resolved by A23, through `evidence_02`'s 09-09 sub-snapshot showing account_5684 for user_26.
- **On eval**, excluding the 10 non-deletion cases:

  | Candidates per case | H1 + evidence + global | + rank tie-break |
  | --- | --- | --- |
  | 0 | 12 (exactly the 42 h family) | 12 |
  | 1 | 360 | **494** |
  | 2 | 110 | 2 |
  | 3 | 26 | 0 |

  No eval delete is claimed by two cases.
- **The rank tie-break is a generator artifact, not evidence.** It assumes the case_id numbering follows the order of the deletes. It hits 4 out of 5 on samples (the miss is case_23). It is close to the "case-family shortcut" that AGENTS.md §6.7 forbids. **Recommendation:** use it only as a last-resort tie-break with lowered confidence, or leave the tie unresolved (`ambiguous`) and fall back to verifying without that account.

**What is grounded.** For the generated regime, H1 + evidence + global (+ A23 for linking) is fully justified by participant-visible data: timing, result↔status, and identity links captured at or before `audit_at`. It gets 19 to 21 of 23 with **zero wrong picks**.

## 3. Downstream batching, and anonymized analytics IDs

- Source: `proto_account_heuristic.py` (H2). Downstream `deletion_worker` actions follow the account delete:
  - **COMPLETE-style policy actions** (SUCCESS) land +22 to +66 min after it, in a fixed order ANONYMIZE → REDACT → DISABLE → BLOCK. Example, case_26: `activity_3603` +22.7 min, `3605` +30.2, `3606` +36.7, `3607` +44.1.
  - **Failed or check actions** in INCOMPLETE-style cases land +88 to +168 min after it.
- **The actions are batched by clock time across users,** not per user. On 2026-09-02, both `activity_3602` (analytics_1895, case_25) and `activity_3603` (analytics_4566, case_26) run at 11:31. There are 31 two-row minute-batches.
  - So a time window attributes rows poorly: precision 0.22–0.28 with nearest-anchor attribution, and 0.26 at recall 1.00 for a plain 170-minute window.
- **Pre-audit linkability of gold resources** (`proto_downstream_link.py`):

  | Resource kind | Directly linked by a pre-audit record | Unlinked |
  | --- | --- | --- |
  | search, support, data_flow, backup, export, tombstone | **100%** | none |
  | analytics | 12 | **7** (case_03, 04, 21, 25, 26, 27, 28). These are exactly the ones already anonymized, with null PII everywhere before the audit. |
  | account | 15 (+1 A23) | 19 |
  | audit_record | 17 (+4 A23) | 3 (case_09 audit_record_4902, case_18 audit_record_6645, case_20 audit_record_5569) |

- **H4, anonymized analytics IDs.** Take `ANONYMIZE_RECORD` rows within 180 min after the case's account delete, exclude analytics IDs tied pre-audit to another user, and then apply the case_id-order tie-break inside identical candidate sets.
  - The unlinked ones it recovers are case_21, case_25, case_26, case_27 and case_28.
  - Overall it gets 7 of 12 sample cases that have gold analytics. The misses are where evidence already links the analytics ID, so **apply evidence first and activity second**.
  - The same rank-artifact caveat as §2 applies.

## 4. Verdict

1. **The primary account is recoverable for the generated regime** (98% of eval) from timing plus result↔status, then disambiguated by pre-audit identity evidence and global one-to-one assignment. This is grounded, and gave 19 to 21 of 23 with 0 wrong.
   - The residual ties (about 136 eval cases before tie-breaking) can only be settled by the rank artifact. Flag them.
2. **The 42 h eval family (12 cases) has no account-delete signal.** Their resources come from one `LINK_RESOURCE_IDENTITY` activity about a day before the audit (`activity_4000` to `activity_4011`), plus a screenshot or PDF. Treat this family separately.
3. **Anonymized analytics IDs are only recoverable through clock-time batches plus the rank artifact.** Because these records are already compliant, a missed ID costs only a verification step in COMPLETE cases. Do not invent IDs.
4. **3 audit_records and account_004 are unreachable.** Accept the loss.

## 5. Recount: eval cases with only post-audit evidence (replaces Pass 5 §5.4)

Source: `proto_recount.py`. A case counts a file only if the file is captured at or before `audit_at` and names the subject by an exact identifier:

- current or historical email, case-insensitive;
- sha256 of **every** current or historical email;
- phone (digits-normalised, current or historical);
- `user_id` (word-bounded);
- name, but only together with another identifier in the same record unit.

All 11 PNGs were transcribed by eye (`proto_png_transcripts.py`).

| Pre-audit files naming the subject | Eval cases |
| --- | --- |
| 0 | **11** |
| 1 | 503 |
| 2 | 4 |

Identifier kinds behind the matches: email 392, user_id 308, name (with another) 68, phone 30, hash 17, UPPERCASE email 16.

**The "16" from pass 5 was wrong.** Pass 5 ignored PNGs and phones. Those cases are **screenshot-backed**:

| Case | Screenshot | Shows |
| --- | --- | --- |
| case_35 | `evidence_09` | search_428, user_13 |
| case_39 | `evidence_14` | data_flow_1121, jain.aditi@gmail.com |
| case_50 | `evidence_19` | analytics_7438, user_20 |
| case_52 | `evidence_23` | export_1260, ingrid.dahl@outlook.com |
| case_53 | `evidence_28` | support_1034, Kofi Agyeman |
| case_55 | `evidence_32` | backup_9287, areed1433@gmail.com |
| case_34 | `evidence_04` | account_5762, user_11 |

**The 11 cases with zero files:**

- **9 are non-deletion requests** (case_534 to case_542). They need no evidence and are NOT_APPLICABLE. Their only mention is `evidence_50`, captured 10-01T12:00, after their audits; case_533 is exactly at its audit time, so it counts.
- **case_61** (user_07, audit 2026-02-14T10:00):
  - The only pre-audit artifact is the PNG `evidence_46` (`object_storage_browser`, 02-13), which shows `delivery_confirmation_19.pdf` and **no person identifier**.
  - The link is the claim `activity_4007` (2026-02-13, object_19 → priya.raman@gmail.com, user_07).
  - `evidence_58` (which names Priya) is captured 09-12, after the audit.
- **case_63** (user_09, audit 2026-09-17T09:20):
  - The PNG `evidence_60` shows `marketing_001` with **"Soo-jin Park, sj.park@naver.com, +82 10-5837-9451", who is not any known user**.
  - `activity_4008` (09-16) claims marketing_001 → kwame-mensah@proton.me / user_09.
  - **The screenshot contradicts the claim.** That is a trap, and it needs a decision.

Both deletion cases with zero files are screenshot-only cases whose person link rests on a `LINK_RESOURCE_IDENTITY` activity claim.
