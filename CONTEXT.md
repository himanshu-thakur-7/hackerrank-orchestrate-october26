# CONTEXT — Domain glossary (Ghost Data Still Exists)

These are the terms used across `docs/` and the ADRs (`docs/adr/`). Each definition is what the term means in this repo.

| Term | Meaning |
| --- | --- |
| **Subject** | The person a request is about. It is resolved from the request email (any case, current or historical) to exactly one `user_id`. |
| **Identifier set** | Everything that names the subject: `user_id`; every current and historical email; sha256 of each email (`email_hash`); every current and historical phone; and the name, but only together with another identifier. |
| **Grounded link** | A tie between a resource and the subject that rests on participant-visible data at or before `audit_at`. Examples: an identifier inside the same record unit of a file, or a unique activity candidate (ADR 0003). Never inferred from ordering, file membership or similar-looking emails. |
| **Record unit** | The smallest chunk of a file describing one entity: a JSON object with a `resource_id`, a SQL `INSERT`, a log `trace_id` group, a text line, a whole PDF, or a screenshot row. |
| **Claim** | Any workflow statement: `reported_status`, an activity `reported_result`, activity `details`, or a `LINK_RESOURCE_IDENTITY` row. Claims never prove state (ADR 0003). An activity event type may serve as a *category* claim (ADR 0009). |
| **Evidence** | A file in `evidence_files.csv` whose content shows a state. Usable for a case only if `captured_at <= audit_at` (ADR 0002). |
| **Strict cutoff** | The inclusive `<= audit_at` rule, applied per file by manifest `captured_at`. A later file is invisible to that case, sub-snapshots included. |
| **Latest naming file** | The citation rule: cite the most recently captured usable file that names the resource (data notes §4.3). |
| **Closed-world absence** | Proving ABSENT from a snapshot that covers the system or table but omits the resource (data notes §4.1). |
| **Replica drift** | A record deleted from a primary table but still present in a replica in the same snapshot. It counts as remaining (data notes §5.2). |
| **Resurrection** | A later observation showing a deleted record present again. The latest observation at or before `audit_at` wins. |
| **Look-alike decoy** | An email or name close to the subject's that is not theirs (`.jr` suffixes, sibling names). It never matches (data notes §5.1). |
| **Primary account** | The subject's `account_N` in `account_service`. It is always verified in deletion cases. |
| **Generated regime** | Requests with `reported_at − requested_at` of exactly 24, 48 or 72 h (506/518 eval). The account delete lands 0.75–1.23 h before `reported_at`. |
| **42 h family** | The 12 eval cases with exactly 42 h between request and report. They have no account-delete signal and are linked through `LINK_RESOURCE_IDENTITY` plus a screenshot or PDF. |
| **Unique candidate** | The single activity-derived link left after the window, result↔status, pre-audit identity filter and global one-to-one elimination (ADR 0003). |
| **Unresolved link** | Two or more equally plausible candidates. No step is emitted, and the tie is logged (ADR 0004). |
| **Contradicted link** | A link the referenced artifact visibly refutes, e.g. case_63's `marketing_001`. It is rejected (ADR 0005). |
| **Attempted but unproven** | A grounded-linked resource with a FAILED or PARTIAL action claim and no pre-audit evidence of its end state. It gets a **future VERIFY step only** (empty evidence_id) and is never a finding citing an activity row. Case status comes from the other grounded findings (ADR 0006, amended). |
| **Unproven (log)** | An unproven resource in a case with no grounded finding. It is omitted from the steps and logged as `UNPROVEN`, because COMPLETE steps must all cite evidence (ADR 0006 edge case). |
| **Not observable** | A category or resource never visible in any evidence file (cache, email delivery log, telemetry). It produces no steps (ADR 0012). |
| **Unlabeled assumption** | A treatment no sample covers: DELETION_PENDING accounts (ADR 0010) and legal holds (ADR 0011). It is listed explicitly in reports. |
| **Account tombstone** | An `identity_service` record kept after account deletion. Compliant means the stable `subject_reference` stays and name, email, phone and hash are null (data notes §7.4). |
| **Support message / attachment** | Message: a conversation with shared context, so REDACT (rule_05). Attachment: an uploaded file belonging only to the subject, so DELETE (rule_06). See ADR 0009. |
| **Rules-only fallback** | The no-key path that produces all 518 rows deterministically, without any model call (ADR 0008). |
| **Shadow vote** | A log-only second opinion on request intent from the evaluation model. It never changes a row (ADR 0013). |
