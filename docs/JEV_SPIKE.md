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

## Follow-up spike: does the mean of k = 10 calls give a stable ranking signal?

**Decision rule (written 2026-10-25T02:47:54Z, before any follow-up call):**
- If the mean-of-10 score passes **both** gates (AUROC ≥ 0.90, and max per-proposition |round 1 − round 2| ≤ 0.05) in **both** independent rounds, a judge may later be built as a **ranker only**: advisory, never editing output.csv, writing a per-step risk score and a review queue to a report.
- Otherwise stop: the blind sub-agent audit stays the independent check, and the Jev result is recorded as a measured negative result in the evaluation report.
- The same rule applies separately to the variant with precomputed facts in `state` (part 2).

### Setup

- Same 50 propositions (25 true / 25 false, 5 per perturbation kind).
- Each call asks the separate `supports` and `contradicts` Noul questions. k = 10 calls per proposition give mean(supports) and mean(contradicts); score = mean(supports) − mean(contradicts).
- **Two independent rounds**, with shuffled call orders (seeds 1 and 2), 8 parallel workers.
- **Part 2** adds to `state` facts computed in code, not by the model: `identifier_match` (exact/none: does any subject email or user_id appear in the evidence lines), `evidence_captured_before_audit` and `resource_mentioned_in_evidence`.
- Code: `scratch/proto_jev_followup.py` (throwaway, git-ignored). The API key is read by the SDK from the environment only.

### Results

| Variant | AUROC round 1 / round 2 | max \|r1 − r2\| (score) | p95 \|r1 − r2\| | Gate |
| --- | --- | --- | --- | --- |
| Part 1: mean of 10, state as before | 0.949 / 0.949 | 0.030 | 0.020 | **PASS** |
| Part 2: mean of 10, + precomputed facts | 0.962 / 0.962 | 0.037 | 0.031 | **PASS** |

Mean score per kind (round 1 / round 2):

| Kind | n | Part 1 | Part 2 |
| --- | --- | --- | --- |
| gold (true) | 25 | +0.54 / +0.54 | +0.52 / +0.52 |
| wrong resource | 5 | −0.44 / −0.43 | −0.40 / −0.39 |
| flipped state | 5 | −0.47 / −0.49 | −0.50 / −0.48 |
| post-cutoff | 5 | −0.47 / −0.47 | −0.51 / −0.51 |
| **wrong operation** | 5 | **+0.20 / +0.20** | **+0.11 / +0.11** |
| **decoy owner** | 5 | **+0.12 / +0.12** | **+0.16 / +0.16** |

- **Totals for the follow-up:** 2,000 calls, model echoed `jev-1.14.0` every time, 1,474,680 input / 76,000 output tokens, median latency 88 ms, p95 137 ms, 24 s wall time, ≈ $0.062 (at $0.042 / 1M input, output free; aggregator listings).

### Reading and decision

- **The hypothesis holds.** Averaging 10 calls makes the score repeatable (max round-to-round difference 0.030–0.037 ≤ 0.05) while keeping AUROC ≥ 0.90. By the pre-registered rule, a **ranker-only** judge may be built later. It would be advisory, never edit `output.csv`, and write a per-step risk score and a review queue to a report. It is **not** built in this job.
- **Both weak kinds remain weak.** Decoy-owner and wrong-operation propositions still score positive on average (+0.12…+0.20), i.e. they rank among the true propositions.
- **The precomputed `identifier_match` fact did not fix decoy owner** (+0.12 → +0.16). It only nudged wrong operation (+0.20 → +0.11).
- So Jev ranks **state and time** errors well (wrong resource, flipped state, post-cutoff) but not **ownership** or **operation-type** errors. Ownership must stay a deterministic check in code, which it already is: exact identifier matching and ADR 0004/0005.
- If a ranker is built, it should only rank state/time claims, and its review queue must not be read as covering ownership mistakes.
- n = 5 per false kind is small. The per-kind means are indicative, not precise.
