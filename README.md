# Ghost Data Still Exists: deletion-audit agent

For each request in `dataset/deletion_requests.csv`, this agent:
- decides whether deletion was really requested;
- reconstructs the subject's current and historical identifiers;
- rebuilds every relevant record's state at `audit_at` from the evidence;
- applies `deletion_rules.csv`;
- writes `output.csv` (`case_id,deletion_status,steps_json`), with findings, an ordered remediation plan and verification checks.

The challenge contract is in `problem_statement.md` and `AGENTS.md` in the repository.

## Run

```text
python3 code/main.py                                  # reads dataset/, writes ./output.csv (518 rows)
python3 code/main.py --explain case_12                # the evidence trace behind one row
python3 code/main.py --data /path/to/dataset --out /tmp/output.csv
```

- **Requirements:** Python 3.10+ and the standard library only.
- **No key or network needed:** the default run needs no API key, no network and no PDF or OCR tool. This holds because these committed modules supply everything:
  - `code/ghostaudit/llm_cache.py`: the cached intent verdicts;
  - `code/ghostaudit/loaders/pdf_text_cache.py`: the PDF text;
  - `code/ghostaudit/loaders/screens_data.py`: hand-verified transcriptions of the screenshots.

  Each module is keyed by sha256 and holds no request text.
- **Runtime:** about 3 s for all 518 cases.

## Reproduce and validate

```text
python3 code/evaluation/main.py final                 # every gate + a clean-room run of code.zip (below)
python3 code/package.py                               # builds ./code.zip (README.md + code/ only) and lists it
python3 code/evaluation/main.py report                # regenerates code/evaluation/evaluation_report.md
python3 code/evaluation/main.py usage                 # regenerates code/evaluation/usage_report.md
python3 code/evaluation/main.py score                 # scores the 32 labeled samples (dev / holdout split)
```

`final` runs these steps:
- unit tests;
- the contract gate;
- determinism (two runs, byte-identical);
- invariants on all 518 rows;
- metamorphic relations;
- custom cases;
- a literal audit (no case ids or golden labels in code);
- the selftest;
- the usage report, whose measured run must equal `output.csv`;
- a key-pattern scan of the repository;
- a **clean room**: it unzips `code.zip` into an empty temp directory and runs it there against `dataset/` with no API keys in the environment. The resulting `output.csv` must have the same sha256 as the committed one.

## Optional pieces (nothing on the default path imports them)

| Piece | Used for | Without it |
| --- | --- | --- |
| `openai` package + `OPENAI_API_KEY` | Intent for the few request texts where deletion and negation/scope cues both fire. The model is pinned to `gpt-5.4-mini-2026-03-17`, with seed and strict JSON schema (ADR 0008). | Cache hits serve the committed verdicts, and rules decide everything else. Output is identical. |
| `typesafe-sdk` + `TYPESAFE_API_KEY` | `python3 code/evaluation/main.py jev-rank`: an advisory, evaluation-only review queue (ADR 0013). | Cached scores are used, and any other step is reported as skipped. It never touches `output.csv`. |
| `pandas` | An extra round-trip check in the contract gate. | That check is skipped, with a warning. |
| `pdftotext` / `pypdf` | Only for a PDF that is not in the committed text cache. | The run stops with `PdfTextUnavailable`. |

- **Environment variables (names only):** `OPENAI_API_KEY`, `TYPESAFE_API_KEY`.
- **How keys are handled:** keys are read from the environment only, by the SDKs. Our code never prints, logs or stores them, and there is no `.env` loading.
- **Model calls never crash the run:** failed calls get a bounded retry, then the rules decide that text. Failures are never cached and are counted as "degraded by error".

## Determinism

- **Same input, same bytes:** the same `dataset/` always gives a byte-identical `output.csv`. With or without keys, and with the Jev ranker on or off, the sha256 is identical; tests and `final` check this.
- **How:**
  - rows are sorted by `case_id`;
  - steps are ordered by the contract's phase and operation rank, then by `system_id` and `resource_id`;
  - JSON is serialized with fixed separators;
  - model verdicts come from the cache.

## Architecture (code/)

```text
code/main.py                 CLI: load → per-case engine → writer
code/ghostaudit/
  loaders/                   evidence by content signature (SQL, JSON, logs, text, PDF text cache, screen transcriptions)
  store.py                   Observations and Coverage, cut at audit_at (EvidenceStore.as_of; ADR 0002)
  identity.py                current + historical emails, phones, email hashes (exact matching only)
  linking.py                 grounded account links from activity; global one-to-one elimination; ties stay unresolved (ADR 0003, 0004)
  policy.py                  category precedence and treatment from deletion_rules.csv (ADR 0009–0012)
  engine.py                  per-resource state, verdict and ordered plan; contradicted or stale links rejected (ADR 0005, 0016)
  contract.py, writer.py     step triples, ordering, serialization
  intent.py, llm_intent.py   rules pre-screen + cached pinned model (ADR 0008); usage.py tracks tokens and cost
code/prompts/                intent_classifier.md, jev_ranker_questions.md
code/evaluation/             gate, scorer, frozen split, metamorphic, invariants, loss ledger, custom cases, reports, final
code/package.py              builds code.zip
```

- **ADRs:** the decisions behind each stage are recorded as ADRs 0001–0016 in `docs/adr/` in the repository; the modules above name the ones they follow.
- **Further docs:** `docs/03_DESIGN.md` (design), `docs/LOSS_LEDGER.md` (accepted losses) and `docs/BOARD.md` (task history).
- **Reports:**
  - `code/evaluation/evaluation_report.md` (accuracy, custom cases, failures and fixes);
  - `code/evaluation/usage_report.md` (models, calls, tokens, cost).

## Known risks

- **ADR 0015: INCOMPLETE with `[]`.** A deletion request with nothing grounded to report is written as `INCOMPLETE,[]`. Three eval rows are affected. The contract gate reports them as the warning `L0.empty_incomplete`.
  - **One-line revert,** if the grader rejects such rows: in `code/evaluation/gate.py`, change `if status == "COMPLETE" and not steps:` back to `if status != "NOT_APPLICABLE" and not steps:`. The gate then fails on those rows, and a fallback is needed for them.
- **Unresolved account links (ADR 0004).** About 136 eval cases have tied account candidates. These links are never guessed, so the account steps for those cases are omitted and logged. This is the largest accepted loss (`docs/LOSS_LEDGER.md`).
- **Absence by omission (ADR 0014).** A record missing from a covering snapshot, captured at or before `audit_at`, counts as absent. It is weaker evidence than an explicit 404 or a deletion row.
- **Screenshots** are read from committed transcriptions keyed by the PNG's sha256. A new or changed PNG stops the run instead of guessing.
