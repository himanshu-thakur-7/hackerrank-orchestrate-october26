# ADR 0008 — LLM scope: language (intent) and vision (screenshots) only, cached, with a rules-only fallback

- **Status:** Accepted (owner ruling)
- **Recommendation matched the ruling:** yes

## Question

Where may a model be used, and how is the run kept deterministic and reproducible?

## Context

- Intent: 508 deletion requests across 17 templates in 6 languages, plus 10 non-deletion requests (case_533–542). Negation traps such as "remove me from marketing lists only" (`docs/02` §5.5).
- Vision: 11 PNGs with no OCR available (`docs/02b`).
- Everything else (identity resolution, state, policy, ordering) is deterministic over parsed data.
- README.md: "Automated code evaluation ignores raw data files (`.csv`, `.tsv`, `.json`, `.jsonl`, `.sql`, `.log`)".

## Recommendation

Only intent and vision go through a model, and their outputs are cached. Ship a rules-only path (multilingual keyword + negation rules for intent; committed transcriptions for screenshots) so all 518 rows are produced without any key.

## Decision

- **Intent:** OpenAI `gpt-5.4-mini-2026-03-17`. **Vision:** OpenAI `gpt-5.4-2026-03-05`. These are pinned IDs.
- Keys come only from environment variables: `OPENAI_API_KEY`, and `TYPESAFE_API_KEY` for the evaluation judge (ADR 0013). They are never committed or logged.
- Calls are deterministic (temperature 0 or the equivalent) and cached by input hash.
- **The cache is committed as a generated `.py` data module** (or `.md`/`.txt`), **never** `.json`/`.jsonl`/`.csv`, so the cache is reviewable as code; data files such as `.json` are commonly excluded from code review and indexing tooling.
- **With no key, the rules-only fallback** produces all 518 rows.

## Consequences

- The run is reproducible from the committed cache.
- `usage_report.md` reports the model calls of the final full run (cache misses), with tokens and cost.
- The model IDs are recorded as given and must be checked against the provider at build time.

## Rejected alternatives

- **An LLM deciding state or policy:** not deterministic, and it would act on claims.
- **A JSON cache:** data files such as `.json` are commonly excluded from code review and indexing tooling.
