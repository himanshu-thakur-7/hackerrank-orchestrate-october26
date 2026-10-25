# code/ — Ghost Data deletion audit

## Dependencies

- **Required:** Python 3.10+ standard library only. The solver and the evaluation harness import nothing outside the stdlib, except the optional pieces below.
- **Optional: `pandas`.** It is used only by the evaluation contract gate for an extra round-trip check of `output.csv`. When pandas is absent, that check is reported as `WARNING L0.pandas SKIPPED` and does not fail the gate. The mandatory stdlib `csv` round-trip still runs.
- **PDF text:** the four dataset PDFs are read from the committed text cache `ghostaudit/loaders/pdf_text_cache.py` (generated with `pdftotext -layout`, keyed by sha256), so the default run needs no PDF tool. Only a PDF outside the cache needs `pdftotext` (poppler-utils) or `pip install pypdf`; with neither, the run stops with `PdfTextUnavailable`.
- **Screenshots** are read from committed transcriptions (`ghostaudit/loaders/screens_data.py`, keyed by the PNG's sha256), so the no-key run reproduces `output.csv`. A PNG without a transcription stops the run.
- **Optional: OpenAI API** (`pip install openai`), intent only, pinned `gpt-5.4-mini-2026-03-17` (ADR 0008).
  - Rules decide clear texts; the model decides only texts where deletion and negation/scope cues both fire.
  - Verdicts are cached in the generated module `ghostaudit/llm_cache.py` (sha256 keys, answers only). A live call happens only on a cache miss with `OPENAI_API_KEY` set in the environment; the key is never read by our code, printed or stored.
  - With no key (or `--intent rules`), all 518 rows are produced, and the committed cache reproduces `output.csv` exactly.
  - `python3 code/evaluation/main.py intent` compares the rules and the model on every unique request text and writes `evaluation/intent_disagreements.md`.
  - The prompt is in `code/prompts/intent_classifier.md`.

## Degradation (never a crash, never a different output for cached texts)

- `OPENAI_API_KEY` set without the `openai` package: one warning on stderr and in the usage log; the intent uses rules + the committed cache.
- API errors (auth, connection, timeout, rate limit, malformed JSON, schema violation): each text gets at most 1 + 2 attempts with a small backoff, then the rules decide it. The failure is recorded in the usage log and counted as "degraded by error"; it is never cached and not retried again in that run.
- Every run ends with `intent decisions (...): rules (clear) N, cache N, live model N, rules fallback N, degraded by error N`.
- `pandas` (gate extra check), `pypdf` (PDF fallback) and `typesafe-sdk` (spike only, not used by `code/`) are optional; none is imported on the default path.

## Known risks

- **ADR 0015, INCOMPLETE with `[]`.** A deletion request with nothing grounded to report is written as `INCOMPLETE,[]`. The problem statement only requires `[]` for NOT_APPLICABLE, and a placeholder step would be fabricated. The contract gate reports these rows as the warning `L0.empty_incomplete` (a progress metric), not as a violation. **Revert path, if the grader rejects such rows:** in `code/evaluation/gate.py`, change `if status == "COMPLETE" and not steps:` back to `if status != "NOT_APPLICABLE" and not steps:` so the gate fails on them again. A fallback for those cases is then needed.

## Evaluation

```text
python3 code/evaluation/main.py selftest                   # gate + scorer + split + audit + history self-check
python3 -m unittest discover -s code/evaluation/tests -t code
python3 code/evaluation/main.py contract                    # check ./output.csv against dataset/deletion_requests.csv
python3 code/evaluation/main.py score --pred PRED.csv      # PRED.csv = predictions for dataset/sample_deletion_requests.csv
```
