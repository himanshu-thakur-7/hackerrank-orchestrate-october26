# ADR 0001 — Rows are sorted by case_id, numerically

- **Status:** Accepted (owner ruling 2026-10-25)
- **Recommendation matched the ruling:** yes

## Question

`output.csv` must be "sorted by `case_id`" (problem_statement.md line 73), but eval IDs are unpadded (`case_33` … `case_550`). Should the sort be lexical or numeric?

## Context

- The rule names no collation (ambiguity A1).
- Measured (`docs/02_DATA_NOTES.md` §1.2): 518 unique eval IDs, 67 with two digits and 451 with three. The input file is already in **numeric** order; lexical order differs (`case_100` < `case_33`).
- The sample IDs (`case_01` … `case_32`) are padded, so the sample cannot tell the two apart.

## Recommendation

Numeric. It matches the order of the input file, and it is the reading a human would expect.

## Decision

**Sort rows by the integer suffix of `case_id`, ascending** (`case_33`, `case_34`, …, `case_550`).

## Consequences

- The writer must use an integer key, not a string sort.
- If the grader joins rows by `case_id`, the order is harmless either way; if it compares row order, numeric order is the defensible reading.

## Rejected alternatives

- **Lexical string sort:** contradicts the input order for 451 of 518 IDs.
- **Zero-padding the IDs:** that would change the `case_id` values themselves, which are keys.
