# 01 — Challenge Contract

Sources read: `problem_statement.md` (PS), `README.md` (RM), `agent_trace_instructions.md` (AT), `AGENTS.md` (AG).
Quotes are verbatim, and line numbers refer to each file at commit `8f5e824`. Nothing in this document comes from `dataset/`.

---

## 1. Output contract

### 1.1 File

- Location: the repository root. RM:32 says "Write the final predictions to `output.csv` in the repository root". RM:40 says "The blank template at `dataset/output.csv` is provided as a reference. Your final generated file for submission must be the root-level `output.csv`."
- Header (PS:64, RM:70), quoted exactly:

  ```text
  case_id,deletion_status,steps_json
  ```

  RM:67 says "Create `output.csv` with these columns in this exact order".
- Rows: PS:73 says "The final file must contain exactly 518 data rows, sorted by `case_id`." RM:75 says "518 data rows sorted by `case_id` (plus the header row)."
- One row per case: PS:61 says "Produce exactly one row in `output.csv` for every case in `deletion_requests.csv`".

### 1.2 Columns (PS:67-71)

| Column | Meaning |
| --- | --- |
| `case_id` | "Case being audited" |
| `deletion_status` | "`COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`" |
| `steps_json` | "Ordered JSON array of findings, remediation actions, and verification checks" |

Parsing: PS:99 says "The grader parses `steps_json` as JSON. JSON object-key order and whitespace are ignored; array order is not."

### 1.3 Step object schema (PS:75-87)

"Each object in `steps_json` must contain:"

```json
{
  "step_no": 1,
  "phase": "FINDING",
  "system_id": "account_service",
  "resource_id": "account_005",
  "operation": "REPORT_REMAINING_RECORD",
  "state": "PRESENT",
  "evidence_id": "evidence_01"
}
```

AG §6.3 says "Each step contains **exactly** these fields". That gives seven keys and no extras:

| Key | Type (from the example) | Constraint |
| --- | --- | --- |
| `step_no` | integer | PS:89: "Step numbers start at `1` and increase consecutively." |
| `phase` | string | PS:89: "`phase` must be `FINDING`, `REMEDIATION`, or `VERIFICATION`." |
| `system_id` | string | Must be one of the triples in §1.4. |
| `resource_id` | string | — |
| `operation` | string | Must be one of the 15 triples in §1.4. |
| `state` | string | Fixed by the operation (§1.4). |
| `evidence_id` | string | A `file_id`, `activity_id` or `audit_id`, or `""` (§1.6). |

### 1.4 The 15 allowed (phase, operation, state) triples (PS:103-119)

The rank is the position in the PS table. It is used by the sort key in §2.

| Rank | Phase | Operation | State | Meaning (PS, verbatim) |
| --- | --- | --- | --- | --- |
| 1 | `FINDING` | `REPORT_REMAINING_RECORD` | `PRESENT` | "A record that should have been deleted still exists." |
| 2 | `FINDING` | `REPORT_EXPOSED_PII` | `PRESENT` | "A record may remain, but it still contains identifiers that should have been redacted or anonymized." |
| 3 | `FINDING` | `REPORT_ACTIVE_DATA_FLOW` | `ACTIVE` | "An active process can copy or recreate the user's data." |
| 4 | `FINDING` | `REPORT_RESTORE_RISK` | `ACTIVE` | "A backup or restore path can bring deleted data back." |
| 5 | `REMEDIATION` | `DISABLE_DATA_FLOW` | `DISABLED` | "Stop the process that can copy or recreate the data." |
| 6 | `REMEDIATION` | `BLOCK_RESTORE` | `BLOCKED` | "Prevent the affected backup from restoring the user's data." |
| 7 | `REMEDIATION` | `DELETE_RECORD` | `ABSENT` | "Remove the entire record." |
| 8 | `REMEDIATION` | `REDACT_RECORD` | `REDACTED` | "Keep the record but remove the identifying fields required by policy." |
| 9 | `REMEDIATION` | `ANONYMIZE_RECORD` | `ANONYMIZED` | "Keep the record after irreversibly unlinking it from the user." |
| 10 | `VERIFICATION` | `VERIFY_RECORD_ABSENT` | `ABSENT` | "Confirm that a record no longer exists." |
| 11 | `VERIFICATION` | `VERIFY_RECORD_PRESENT` | `PRESENT` | "Confirm that a policy-required retained record still exists." |
| 12 | `VERIFICATION` | `VERIFY_RECORD_REDACTED` | `REDACTED` | "Confirm that required identifying fields have been removed." |
| 13 | `VERIFICATION` | `VERIFY_RECORD_ANONYMIZED` | `ANONYMIZED` | "Confirm that the record can no longer be linked to the user." |
| 14 | `VERIFICATION` | `VERIFY_DATA_FLOW_DISABLED` | `DISABLED` | "Confirm that the relevant data flow is inactive." |
| 15 | `VERIFICATION` | `VERIFY_RESTORE_BLOCKED` | `BLOCKED` | "Confirm that the affected data cannot be restored." |

AG §6.4 says "Do not invent additional phases, operations, or states."

Every operation belongs to exactly one phase, so the operation alone determines both phase and state.

### 1.5 `NOT_APPLICABLE` row shape (PS:93-97)

```csv
case_000,NOT_APPLICABLE,[]
```

### 1.6 Evidence citation (PS:127)

> "Findings and verification steps for `COMPLETE` cases must cite a `file_id`, `activity_id`, or `audit_id`. Proposed remediation and future verification steps for `INCOMPLETE` cases use an empty `evidence_id`."

AG §6.6 adds the following:

> "A finding must use the participant-visible `file_id`, `activity_id`, or `audit_id` that proves it."
> "A verification step for a `COMPLETE` case must cite the evidence that proves the current compliant state."
> "Never cite organizer-only truth or an evidence item captured after the case's `audit_at`."

Summary:

| Step kind | `evidence_id` |
| --- | --- |
| FINDING (only appears in INCOMPLETE) | a non-empty, proving ID |
| REMEDIATION (INCOMPLETE) | `""` |
| VERIFICATION in INCOMPLETE | `""` |
| VERIFICATION in COMPLETE | a non-empty, proving ID |

---

## 2. Ordering rules

### 2.1 Rows

PS:73 says "sorted by `case_id`." No collation is specified (see A1).

**Row sort key:** `case_id`, ascending. The comparison is assumed to be byte/lexicographic, which is still open (A1).

### 2.2 Steps within a case

The rule text in PS:126:

> "Order steps by phase: findings, remediation, then verification. Within each phase, follow the operation order in the table above, followed by `system_id` and `resource_id` in ascending order."

RM:75 says "Within a phase, follow the operation order in the problem statement, then sort by `system_id` and `resource_id`."

**Step sort key**, applied before step numbers are assigned:

```text
key(step) = ( phase_rank(step.phase),         # FINDING=1, REMEDIATION=2, VERIFICATION=3
              op_rank(step.operation),        # 1..15 per §1.4
              step.system_id,                 # ascending, collation unspecified (A2)
              step.resource_id )              # ascending, collation unspecified (A2)
```

Then `step_no = 1..n` in that sorted order. Because `op_rank` already implies `phase_rank`, the first element is redundant but harmless.

AG §6.5 states a dependency rule, which may conflict with this key (A3):

> "Within remediation, disable data flows and block unsafe restores before changing dependent records. Process downstream copies before their source records when the dependency requires it."

---

## 3. Status requirements (rule text)

### 3.1 Definition of complete

From PS:24-29:

> "A deletion is complete only when:
> - every relevant copy has received the treatment required by `deletion_rules.csv`;
> - no active sync, import, or restore path can recreate the data;
> - retained records contain only the identifiers permitted by the rules; and
> - records that must be retained remain available."

AG §6.5 says the same thing:

> "A deletion is `COMPLETE` only when every relevant copy has the required treatment, every required retained record remains available, and no active sync, import, or restore path can recreate prohibited data."

### 3.2 `COMPLETE`

PS:91 says "For `COMPLETE`, include only verification steps proving the current state."

AG §6.3 says "For a `COMPLETE` case, include only evidence-backed verification steps proving the state at `audit_at`."

Every step in a COMPLETE case is therefore a VERIFICATION step with a non-empty `evidence_id`.

### 3.3 `INCOMPLETE`

PS:91 says "For `INCOMPLETE`, include findings, the complete remediation plan, and the checks that must pass afterward."

AG §6.5 adds:

> "For an incomplete case, report every relevant policy violation and recreation risk supported by participant-visible evidence."
> "Verification must cover the required final state for each remediated record or process."

AG §6.3 adds "Findings cite participant-visible evidence. Proposed remediation and future verification steps use an empty `evidence_id`."

### 3.4 `NOT_APPLICABLE`

PS:91 says "For `NOT_APPLICABLE`, use an empty JSON array (`[]`) because no deletion or deletion verification is authorized."

AG §6.5 says "First determine whether `request_text` authorizes deletion. A request for access, correction, export, marketing opt-out, or another non-deletion action is `NOT_APPLICABLE`, even if other fields resemble a deletion case."

AG §6.2 says "`request_text` contains the person's request and may be written in different languages."

### 3.5 Cross-cutting decision rules

- **Time:** AG §6.2 says "Use only information available at or before `audit_at` when deciding the case. Evidence created later must not change the answer for that case."
- **Claims:** PS:57 says "`reported_status` … is a claim from the existing deletion workflow, not proof of the true state." PS:124 says "Reported workflow statuses and operation results are claims."
- **Identity:** PS:123 says "Resolve the user's current and historical identifiers." AG §6.2 says "`email` … may be a current or historical email address."
- **Policy:** PS:125 says "Apply `deletion_rules.csv` to every relevant record, including account tombstones, active data flows, and restore risks."
- **Tombstone:** PS:13 says "the stable user reference may remain, but direct identifiers such as name, email, phone, and email hash must be removed." AG §6.5 says "For an `ACCOUNT_TOMBSTONE`, preserve the stable subject reference and remove the name, email, phone, email hash, and any other direct identifiers required by the applicable `REDACT` rule."
- **Retention:** AG §6.5 says "Do not delete data that policy requires to be retained, redacted, anonymized, or preserved as a tombstone."

---

## 4. Deliverables

| Item | Source text | Notes |
| --- | --- | --- |
| `output.csv` | RM:123 "One answer row for each of the 518 requests in `dataset/deletion_requests.csv`" | At the repo root. |
| `code.zip` | RM:122 "Runnable solution, prompts, configuration, `README.md`, and `evaluation/` reports" | The packaging command is in RM:134: `zip -r code.zip README.md code -x "*/__pycache__/*" "*/.venv/*" "*/venv/*" "*/node_modules/*" "*/.git/*" "*/.DS_Store"` |
| `evaluation_report.md` | PS:133-139 "case-level status accuracy; step-level and field-level accuracy; sequence accuracy; at least three additional evaluation cases created by your team; and failures found and improvements made." | The path is inconsistent across files (A10). |
| `usage_report.md` | PS:158 "summarize the final full-dataset run that produced `output.csv`, including model providers and names, model calls, input and output tokens, total and average tokens per request, and estimated total and per-request cost. If multiple models are used, include both per-model and overall totals in the same file." | Same path issue (A10). |
| `log.txt` (`chat_transcript`) | RM:113 "Upload `log.txt` directly as your `chat_transcript` submission on HackerRank." RM:156 "`log.txt` follows the `AGENTS.md` turn format" | AG §5 sets the format: append-only, with `tool=` and `model=` in every entry. |
| `agent-trace.zip` | AT:3 "Please submit the complete agent trace for the work you did on this challenge as a **ZIP file**." AT:130 "Submit `agent-trace.zip` with your challenge submission." | Claude Code traces live under `~/.claude/projects/`, plus a `/export` transcript, placed in `agent-trace/claude-code/` (AT:19-34). This file is not in the PS or RM submission tables (A11). |
| `README.md` (inside the zip) | RM:127 "Include clear setup and execution instructions in `README.md` inside `code.zip`." | — |
| AI interview | RM:125 "Live explanation of your architecture, approach, and evaluation" | — |

Other submission requirements:

- RM:99 says the reports must have their content inline: "write your complete evaluation metrics, custom evaluation test cases, and token/cost breakdowns directly inside those Markdown files, and keep prompts in source code or Markdown files. Automated code evaluation ignores raw data files (`.csv`, `.tsv`, `.json`, `.jsonl`, `.sql`, `.log`)".
- RM:37 gives the entry point: "`python3 code/main.py`". AG §6.7 says "Be runnable from the terminal."

### 4.1 Pre-submit checklist (RM:149-157, verbatim)

> - "`output.csv` has the exact header `case_id,deletion_status,steps_json` and contains all 518 data rows sorted by `case_id`;"
> - "every `steps_json` value is a valid JSON array with consecutive step numbers starting at `1`;"
> - "findings cite valid evidence IDs, and `COMPLETE` verification steps cite evidence proving the current state;"
> - "proposed remediation and future verification steps use an empty `evidence_id` (`""`);"
> - "`code.zip` includes your runnable code, `README.md`, `code/evaluation/evaluation_report.md`, and `code/evaluation/usage_report.md`;"
> - "`log.txt` follows the `AGENTS.md` turn format and is uploaded to the `chat_transcript` slot; and"
> - "no API keys, credentials, real personal data, or sensitive configuration values are included."

---

## 5. Must-nots

| Must not | Source text |
| --- | --- |
| Secrets | PS:160 "Do not include API keys, credentials, or sensitive configuration values in the submission." AG §4.4 "Never commit or submit secrets. Read credentials from environment variables and use an uncommitted `.env` file when needed." RM:114 "Do not include API keys, tokens, credentials, or secrets in prompts, code, configuration, or `log.txt`." |
| Dataset in the zip | RM:146 "Do **not** include `dataset/`, virtual environments (`.venv`, `venv`, `node_modules`), or build caches (`__pycache__`)." |
| Nested archives | RM:147 "Do **not** include nested archives (`.zip`, `.tar`, `.gz`, `.tgz`, `.7z`, `.rar`) inside `code.zip` — submissions containing nested archive files will be rejected." |
| Organizer files | AG §4.3 "Organizer-only truth, golden answers, review files, and generator internals must never be used for predictions." AG §6.1 "Organizer-only files live outside `dataset/` and must never be used for predictions, prompt examples, hardcoded labels, or evaluation-time shortcuts." |
| Hardcoding | AG §6.7 "Do not use organizer-only files, hardcoded golden labels, or case-family shortcuts." |
| Later evidence | AG §6.6 "Never cite organizer-only truth or an evidence item captured after the case's `audit_at`." |
| Trusting claims | AG §6.5 "do not accept `reported_status` or `reported_result` as proof." |
| Manifest-only membership | AG §6.6 "Do not infer case membership from the manifest alone." |
| Over-deletion | AG §6.5 "Do not delete data that policy requires to be retained, redacted, anonymized, or preserved as a tombstone." |
| Invented vocabulary | AG §6.4 "Do not invent additional phases, operations, or states." |
| Real personal data | RM:157 "no API keys, credentials, real personal data, or sensitive configuration values are included." |
| Trace credentials | AT:109 "Do **not** include authentication files, settings, or credential stores (such as `auth.json`, `config.json`, `mcp.json`, `mcp_config.json`, or `.env`)." |

---

## 6. Ambiguities (noted, not resolved)

**Ordering**

- **A1 — Unpadded `case_id` sort.** "sorted by `case_id`" (PS:73) names no collation. If IDs are not zero-padded (e.g. `case_9` vs `case_10`), lexicographic and numeric order differ. The examples (`case_000`, `account_005`) suggest padding, but the spec does not guarantee it.
- **A2 — `system_id` / `resource_id` collation.** "in ascending order" (PS:126) has the same question: byte, case-insensitive or natural order, for example `resource_9` vs `resource_10`.
- **A3 — Dependency order vs sort key.** AG §6.5 says "Process downstream copies before their source records when the dependency requires it." PS:126 says to sort within a phase by operation, then `system_id`, then `resource_id`. Two `DELETE_RECORD` steps on a downstream replica and its source are ordered alphabetically by the PS key, which may put the source first. It is unclear which rule wins.
- **A4 — Ties.** The key cannot order two steps with the same operation, `system_id` and `resource_id`, for example the same record cited by two pieces of evidence. It is unclear whether such duplicates are allowed, merged, or tie-broken by `evidence_id`.

**Evidence**

- **A5 — Which evidence to cite.** A finding needs "the … `file_id`, `activity_id`, or `audit_id` that proves it" (AG §6.6), but one record can be supported by several items: a SQL snapshot file, the activity row that claims deletion, and a later sync activity. The spec does not say whether to cite the primary state evidence (file) or the event (activity), the latest item before `audit_at`, or what to do when more than one qualifies.
- **A6 — Evidence for COMPLETE verifications by type.** For `VERIFY_RECORD_ABSENT`, the proof could be a snapshot showing absence or a deletion activity, and activities are "claims". For `VERIFY_DATA_FLOW_DISABLED` and `VERIFY_RESTORE_BLOCKED`, it is not stated what proves the state.
- **A7 — `audit_at` boundary and timestamps.** "at or before `audit_at`" is inclusive, but it is unclear whether the cutoff applies to the manifest capture time, the event time inside the file, or both. It is also unclear how to treat evidence captured before `audit_at` that is superseded by a later activity that is still before `audit_at`.
- **A8 — Grammar of PS:127.** "Findings and verification steps for `COMPLETE` cases must cite…" can be read as (findings) + (verification for COMPLETE), or as both only for COMPLETE. PS:91 says COMPLETE contains *only* verification steps. AG §6.3 settles that findings always cite evidence, but the PS wording is unclear on its own.

**Resource modelling**

- **A9 — Support message vs attachment.** "support attachments" appear as a data location (PS:5, AG §1). A support ticket can hold PII in the message body and also in an attached PDF or image. The spec does not say whether these are one resource or two (separate `resource_id`s), which `system_id` an attachment belongs to, or whether message and attachment fall under different `deletion_rules.csv` categories (for example, delete the attachment but redact the message).

**Deliverables**

- **A10 — Evaluation report path.** PS:133 and AG §6.8 say `evaluation/evaluation_report.md` and `evaluation/usage_report.md` at the zip root. RM:92-93, RM:99 and RM:155 say `code/evaluation/…`, and the starter has `code/evaluation/main.py`. RM:145 tolerates both.
- **A11 — Agent trace status.** `agent-trace.zip` is requested in AT but is missing from the PS:143-148 and RM:120-125 submission tables. It is unclear whether it is required or optional.
- **A12 — `chat_transcript` definition.** PS:147 says "Transcript showing how the system was developed or used". RM:124 says it is specifically "The root `log.txt` file generated by your coding agent".
- **A13 — Usage report for a deterministic run.** If the final run makes no model calls, it is unclear whether `usage_report.md` should report zeros, or also cover LLM calls made during development.
- **A14 — Submission URL.** AG §4.1 gives `https://wwww.hackerrank.com/...` (four `w`s) and requires that "exact URL" to be used verbatim. That looks like a typo.

**Semantics**

- **A15 — Verification coverage in INCOMPLETE.** AG §6.5 says verification covers "each remediated record or process". It is unclear whether retained records that are already compliant also get `VERIFY_RECORD_PRESENT` (with `""` evidence) in an INCOMPLETE case.
- **A16 — Shape of a tombstone or redaction finding.** For an account tombstone with exposed PII, it is unclear whether the expected sequence is `REPORT_EXPOSED_PII` → `REDACT_RECORD` → `VERIFY_RECORD_REDACTED` alone, or also `VERIFY_RECORD_PRESENT`.
- **A17 — Backups: delete or block.** It is unclear whether a backup containing the user is a `REPORT_REMAINING_RECORD` + `DELETE_RECORD`, a `REPORT_RESTORE_RISK` + `BLOCK_RESTORE`, or both.
- **A18 — `resource_id` for flows.** For `REPORT_ACTIVE_DATA_FLOW` and `REPORT_RESTORE_RISK`, it is unclear whether `resource_id` is the job or pipeline ID, the target record, or the backup ID.
- **A19 — Partial or mixed requests.** The spec does not cover requests that ask to delete some data and keep other data, requests that combine deletion with export or access, or requests that are conditional or withdrawn. It is unclear whether such a request "authorizes deletion".
- **A20 — Identity edge cases.** It is unclear what to do when the request email maps to no user, or when an email was reused by another user after a change; resolution likely has to be time-aware as of `requested_at` or `audit_at`.
- **A21 — Definition of "exactly 518".** PS:73 requires "exactly 518 data rows" while also saying one row "for every case" (PS:61). If the input file had a different count or duplicate IDs, these two would conflict. That needs checking once the data is loaded.
- **A22 — CSV quoting.** `steps_json` contains commas and quotes, so it must be CSV-quoted. The spec defers to `sample_output.csv` (RM:73) for the exact quoting style, and it is unclear whether the grader is sensitive to that style.
