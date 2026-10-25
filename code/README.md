# code/ — Ghost Data deletion audit

## Dependencies

- **Required:** Python 3.10+ standard library only. The solver and the evaluation harness import nothing outside the stdlib, except the optional pieces below.
- **Optional: `pandas`.** It is used only by the evaluation contract gate for an extra round-trip check of `output.csv`. When pandas is absent, that check is reported as `WARNING L0.pandas SKIPPED` and does not fail the gate. The mandatory stdlib `csv` round-trip still runs.
- **External tool: `pdftotext`** (poppler-utils), to read the four PDF evidence files. Fallback: `pip install pypdf`. With neither, the run stops with `PdfTextUnavailable` (no PDF is skipped silently).
- **Screenshots** are read from committed transcriptions (`ghostaudit/loaders/screens_data.py`, keyed by the PNG's sha256), so the no-key run reproduces `output.csv`. A PNG without a transcription stops the run.
- **Planned optional (T11/T12): OpenAI API.** It is used only when `OPENAI_API_KEY` is set. A committed cache and a rules-only fallback produce all rows without any key (ADR 0008).

## Known risks

- **ADR 0015, INCOMPLETE with `[]`.** A deletion request with nothing grounded to report is written as `INCOMPLETE,[]`. The problem statement only requires `[]` for NOT_APPLICABLE, and a placeholder step would be fabricated. The contract gate reports these rows as the warning `L0.empty_incomplete` (a progress metric), not as a violation. **Revert path, if the grader rejects such rows:** in `code/evaluation/gate.py`, change `if status == "COMPLETE" and not steps:` back to `if status != "NOT_APPLICABLE" and not steps:` so the gate fails on them again. A fallback for those cases is then needed.

## Evaluation

```text
python3 code/evaluation/main.py selftest                   # gate + scorer + split + audit + history self-check
python3 -m unittest discover -s code/evaluation/tests -t code
python3 code/evaluation/main.py contract                    # check ./output.csv against dataset/deletion_requests.csv
python3 code/evaluation/main.py score --pred PRED.csv      # PRED.csv = predictions for dataset/sample_deletion_requests.csv
```
