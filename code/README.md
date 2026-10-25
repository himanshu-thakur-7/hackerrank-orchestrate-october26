# code/ — Ghost Data deletion audit

## Dependencies

- **Required:** Python 3.10+ standard library only. The solver and the evaluation harness import nothing outside the stdlib, except the optional pieces below.
- **Optional: `pandas`.** It is used only by the evaluation contract gate for an extra round-trip check of `output.csv`. When pandas is absent, that check is reported as `WARNING L0.pandas SKIPPED` and does not fail the gate. The mandatory stdlib `csv` round-trip still runs.
- **Planned external tool (T12): `pdftotext`** (poppler-utils), to read the four PDF evidence files.
- **Planned optional (T11/T12): OpenAI API.** It is used only when `OPENAI_API_KEY` is set. A committed cache and a rules-only fallback produce all rows without any key (ADR 0008).

## Evaluation

```text
python3 code/evaluation/main.py selftest                   # gate + scorer + split + audit + history self-check
python3 -m unittest discover -s code/evaluation/tests -t code
python3 code/evaluation/main.py contract                    # check ./output.csv against dataset/deletion_requests.csv
python3 code/evaluation/main.py score --pred PRED.csv      # PRED.csv = predictions for dataset/sample_deletion_requests.csv
```
