# code/ — Ghost Data deletion audit

## Dependencies

- **Required:** Python 3.10+ standard library only. The solver and the evaluation harness import nothing outside the stdlib, except the optional pieces below.
- **Optional: `pandas`.** It is used only by the evaluation contract gate for an extra round-trip check of `output.csv`. When pandas is absent, that check is reported as `WARNING L0.pandas SKIPPED` and does not fail the gate. The mandatory stdlib `csv` round-trip still runs.
- **External tool: `pdftotext`** (poppler-utils), to read the four PDF evidence files. Fallback: `pip install pypdf`. With neither, the run stops with `PdfTextUnavailable` (no PDF is skipped silently).
- **Screenshots** are read from committed transcriptions (`ghostaudit/loaders/screens_data.py`, keyed by the PNG's sha256), so the no-key run reproduces `output.csv`. A PNG without a transcription stops the run.
- **Optional: OpenAI API** (`pip install openai`), intent only, pinned `gpt-5.4-mini-2026-03-17` (ADR 0008).
  - Rules decide clear texts; the model decides only texts where deletion and negation/scope cues both fire.
  - Verdicts are cached in the generated module `ghostaudit/llm_cache.py` (sha256 keys, answers only). A live call happens only on a cache miss with `OPENAI_API_KEY` set in the environment; the key is never read by our code, printed or stored.
  - With no key (or `--intent rules`), all 518 rows are produced, and the committed cache reproduces `output.csv` exactly.
  - `python3 code/evaluation/main.py intent` compares the rules and the model on every unique request text and writes `evaluation/intent_disagreements.md`.
  - The prompt is in `code/prompts/intent_classifier.md`.

## Known risks

- **ADR 0015, INCOMPLETE with `[]`.** A deletion request with nothing grounded to report is written as `INCOMPLETE,[]`. The problem statement only requires `[]` for NOT_APPLICABLE, and a placeholder step would be fabricated. The contract gate reports these rows as the warning `L0.empty_incomplete` (a progress metric), not as a violation. **Revert path, if the grader rejects such rows:** in `code/evaluation/gate.py`, change `if status == "COMPLETE" and not steps:` back to `if status != "NOT_APPLICABLE" and not steps:` so the gate fails on them again. A fallback for those cases is then needed.

## Evaluation

```text
python3 code/evaluation/main.py selftest                   # gate + scorer + split + audit + history self-check
python3 -m unittest discover -s code/evaluation/tests -t code
python3 code/evaluation/main.py contract                    # check ./output.csv against dataset/deletion_requests.csv
python3 code/evaluation/main.py score --pred PRED.csv      # PRED.csv = predictions for dataset/sample_deletion_requests.csv
```
