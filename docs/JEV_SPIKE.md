# T17 spike: TypeSafe Jev as an advisory judge (gate before any judge code)

- **Question:** can Jev (`typesafe-sdk` 0.7.5, `client.system_one`, pinned `model="jev-1.14.0"`) judge atomic evidence propositions reliably enough to serve as an advisory judge?
- **Gate:** AUROC ≥ 0.90 **and** repeat-stability max |Δp| ≤ 0.05.
- **Verdict: FAIL** on repeat stability, so no judge code is built (ADR 0013 stays evaluation-only).

## Setup

- **Network reach:** a one-question request answered in 0.46 s, echoing `jev-1.14.0` (271 input / 20 output tokens). Reachable from this container.
- **Propositions (50):** 25 true and 25 false, built from `dataset/sample_output.csv`.
  - **True:** every cited gold step whose evidence is a text file (SQL/JSON/log), randomly sampled with seed 20261025.
  - **False:** one perturbation of a true step, 5 of each kind:
    - wrong resource id;
    - flipped state (e.g. remaining → absent);
    - wrong operation (e.g. "data flow enabled" for a record);
    - decoy owner (the subject of another case with the same evidence);
    - post-cutoff (a real `evidence_02` line captured 2026-09-17 for a 2026-09-15 audit).
- **`state`** contains the subject identifiers, `audit_at`, the cited file's `captured_at`, and the raw lines (logs: the line and its trace partners; JSON: the whole record object). The claim is only in the question.
- **Questions:** each proposition gets two separate atomic `Noul` questions, "Does the evidence **support** this claim?" and "Does the evidence **contradict** this claim?". There is no negated question and no "unclear" option. A generic rules sentence (no dataset text) precedes each question.
- **Code:** `scratch/proto_jev_spike.py` (throwaway, git-ignored). There is no prompt file in `code/`.

## Results (88 calls)

| Measure | Value | Gate |
| --- | --- | --- |
| AUROC, p(supports) | **0.959** | ≥ 0.90 ✓ |
| AUROC, p(supports) − p(contradicts) | **0.945** | ≥ 0.90 ✓ |
| Repeat stability: same request × 20, max − min p(supports) | **0.090** (0.66 … 0.75, 10 distinct values) | ≤ 0.05 ✗ |
| Option-order bias: one 3-option `Choice` over all 6 orders × 3 repeats | 0 verdict changes (all `present_with_identifiers`) | (reported) |
| Echoed model id | `jev-1.14.0` on every call | pinned ✓ |
| Tokens | 60,871 input / 3,614 output (≈ 692 in per call) | |
| Latency | median 107 ms, p95 143 ms | |
| Cost | ≈ $0.0026 at $0.042 / 1M input, output free (aggregator listings; no TypeSafe price table found) | |

Mean probabilities per proposition kind (supports / contradicts):

| Kind | n | supports | contradicts |
| --- | --- | --- | --- |
| gold (true) | 25 | 0.78 | 0.25 |
| wrong resource | 5 | 0.04 | 0.51 |
| flipped state | 5 | 0.18 | 0.67 |
| wrong operation | 5 | 0.43 | 0.21 |
| decoy owner | 5 | 0.52 | 0.41 |
| post-cutoff | 5 | 0.02 | 0.49 |

## Reading

- Ranking quality is good. The weak kinds are **decoy owner** (0.52 support, so ownership reasoning is unreliable) and **wrong operation** (0.43).
- The model is **not repeatable** at the precision the gate demands: 20 identical requests gave p(supports) from 0.66 to 0.75. A verdict threshold near 0.7 would flip on reruns.
- Per ADR 0013 and the board, the judge stays disabled and `output.csv` is untouched.

## Fallback (proposed)

Keep the **blind sub-agent audit** (`docs/SILVER_AUDIT.md`) as the independent check on unlabeled cases. It already found one real engine bug.

If a judge is wanted later, these could be re-spiked:
- averaging k repeats per proposition (it costs k× calls and must itself be shown stable);
- or reporting Jev only as an aggregate ranking signal (AUROC) over many propositions, never as a per-row verdict.
