# ADR 0009 — Untagged support records: category from the activity event type, state from evidence

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes

## Question

Most support records carry no category tag. How does the system choose SUPPORT_MESSAGE (rule_05 REDACT) vs SUPPORT_ATTACHMENT (rule_06 DELETE)?

## Context (`docs/02` §7.2, §7.5)

- Gold: 11 support pairs, 9 untagged. For 8 of the 9, the `deletion_worker` event type (REDACT_RECORD / DELETE_RECORD) **agrees with gold 8/8**. The ninth (case_07 `support_001`) has no activity; its category comes from the PDF content ("uploader customer", an attachment).
- Against explicit tags across all evidence: **31/31** agree.
- Eval: 164 untagged (case, support) pairs in **159 cases** depend on it; 163 of those pairs have the claim at or before `audit_at`.

## Recommendation and decision

Use the activity event type as a **category claim** for untagged support records:

- REDACT_RECORD → SUPPORT_MESSAGE → REDACT;
- DELETE_RECORD → SUPPORT_ATTACHMENT → DELETE.

Precedence:

1. an explicit tag;
2. artifact content (an uploaded file → attachment);
3. the activity type;
4. otherwise, no category, and the record is logged as unresolved.

**State (present, redacted, absent) comes only from evidence.**

## Consequences

- The same mechanism applies to analytics: DELETE_RECORD vs ANONYMIZE_RECORD agrees 13/13 (case_12).

## Rejected alternatives

- **Defaulting all support to REDACT:** wrong for 3 of 11 gold.
- **Inferring from message text with an LLM:** unnecessary, and less reliable than 31/31.
