# BOARD — ghost-audit build

- **Board backend:** this file. The `kanban-init` skill needs the `sqlite3` CLI, which is not installed in this cloud container (checked at session start), so the SQLite board was not created and this Markdown board is the source of truth.
- **Update this file whenever a task moves.**
- **Log:** T01 doing → done 2026-10-25 (selftest green, 34 unit tests). T01 fixes: optional pandas + specific check ids (39 tests). T02 doing → done (12 tests; acceptance green). Baseline run exposed 3 T01 bugs, fixed test-first (43 evaluation tests). T03 doing → done (10 store tests).
- **Statuses:** `todo` → `doing` → `review` → `done` (plus `blocked`).
- **Priorities:** P0 (must ship), P1 (should ship), P2 (only if time and gates allow).
- **Build slice** refers to `docs/03_DESIGN.md` §9. ADRs are in `docs/adr/`.

## Board

| ID | Title | Pri | Slice | Depends on | Acceptance command | Expected result | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | Evaluation core: contract gate, sample scorer (frozen 22/10 split), literal audit, run history + diff gate | P0 | 1 | — | `python3 code/evaluation/main.py selftest` | `CONTRACT OK (sample_output.csv, 32 rows)`; scorer gold-vs-gold = 1.000 on every metric; literal audit `0 hits`; the history line is written | done |
| T02 | CSV loaders, identity resolver, rules-only intent, output writer; baseline run writes 518 valid rows (trivial engine: every row NOT_APPLICABLE) | P0 | 1 | T01 | `python3 code/main.py && python3 code/evaluation/main.py contract && python3 code/main.py --report` | `CONTRACT OK (output.csv, 518 rows)`; numeric order; report shows intent 508 DELETION / 10 NOT_DELETION (exactly case_533–542) and identity resolved 518/518 (engine placeholder emits NOT_APPLICABLE for all, because an empty INCOMPLETE is invalid under the gate) | done |
| T03 | Observation/Coverage/Link models + Evidence Store with identifier/resource/time indexes and the `as_of(cutoff)` view | P0 | 2 | T02 | `python3 -m unittest discover -s code/tests -p 'test_store*.py'` | All pass, including: a later file is invisible through `as_of`; inclusive `<=` boundary (evidence_03 at case_11's audit_at); latest-observation ordering (evidence_30 account_2088 404 → 200), all modelled as synthetic observations until the loaders land in T04–T07 | done |
| T04 | Loaders: handover txt + service-export JSON + readback logs (trace_id join) | P0 | 2/4/5 | T03 | `python3 code/evaluation/main.py loaders --files evidence_03,evidence_92,evidence_94` | Every sample-cited (file, resource) pair in those files is found with the correct state, and the identifier is resolved via trace_id; `0 unknown signatures` | todo |
| T05 | Loaders: inventory SQL (snapshot_scope coverage) + replica SQL (primary vs replica drift) | P0 | 3 | T03 | `python3 code/evaluation/main.py loaders --kind sql` | All 24 SQL files load; replica-only resources = the 11 listed in data notes §5.2 (incl. account_005, account_994); 8 DELETION_PENDING rows found (§7.6) | todo |
| T06 | Loaders: snapshot bundles, record-list JSON (registers, ledger), notification/record_lookup logs | P1 | 4 | T03 | `python3 code/evaluation/main.py loaders --kind json,register-log` | evidence_51 tombstone_440 is REDACTED and tombstone_9178 EXPOSED; `records: []` produces coverage; all 28 JSON files load; `0 unknown signatures` | todo |
| T07 | Loaders: observability logs, all dialects (trace join, PII scans, heartbeats, restore candidates) | P1 | 5 | T03, T04 | `python3 code/evaluation/main.py loaders --kind log` | All 26 logs load; evidence_01 line 92 analytics_9914 is linked by hash to user_12; the `.jr` decoy search_1874 is NOT linked to user_13 | todo |
| T08 | State reconstruction (latest ≤ cutoff, coverage absence, replica rule) + policy/category mapping | P0 | 2–7 | T04, T05 | `python3 code/evaluation/main.py states --split dev` | Per-resource state matches gold-implied state on dev ≥ 0.95; category precedence tag > content > activity > system default | todo |
| T09 | Verdict + step planner + evidence selection + sort + serialisation | P0 | 2 | T08 | `python3 code/main.py && python3 code/evaluation/main.py score --split dev` | Contract OK; sort key holds 32/32; dev status accuracy reported, with the target ≥ 0.85 once T04–T08 are done; no step cites an activity or audit ID | todo |
| T10 | Linking: catalog links + contradiction check, source refs, activity account candidates (unique only, ties omitted and logged) | P1 | 6, 8 | T09, T12 | `python3 code/evaluation/main.py linking` | Samples: 19/32 exact account hits, 0 wrong; eval: 136 tied cases logged as `UNRESOLVED_LINK`; activity_4008 is `CONTRADICTED` and case_63 has no marketing_001 step | todo |
| T11 | Intent: cached OpenAI (pinned) over the rules-only path + usage tracker | P1 | 9 | T02 | `python3 code/main.py` (no key), then `OPENAI_API_KEY=… python3 code/main.py` | With no key: 518 rows, intent from rules + committed cache. With a key: cache misses are called, and the ledger shows model, tokens and cost; a second run makes 0 calls | todo |
| T12 | PDFs (pdftotext) + screenshot facts: committed transcriptions first, cached live vision second | P1 (vision part P2) | 8 | T03 | `python3 code/evaluation/main.py loaders --kind pdf,png` | 4 PDFs and 11 PNGs give the facts in docs/02b; evidence_60 visible identity = sj.park@naver.com | todo |
| T13 | Custom evaluation cases (≥ 6 fixtures) + evaluation_report.md generator | P1 | 10 | T09, T15 | `python3 code/evaluation/main.py custom && python3 code/evaluation/main.py report` | 6/6 fixtures pass (replica-only account, DELETION_PENDING, contradicted screenshot, legal hold, uppercase historical email, post-cutoff resurrection); report written with every required section | todo |
| T14 | usage_report.md, README, packaging script, final validation | P0 | 10 | T09, T11, T13, T16 | `python3 code/package.py && python3 code/evaluation/main.py final` | code.zip contains README.md + code/ only (no dataset/, .env, *.zip, __pycache__); final gates green; output.csv 518 rows | todo |
| T15 | Metamorphic suite: dataset overlay helper + relations | P0 | 10 | T02 (helper), T09 (relations) | `python3 code/evaluation/main.py metamorphic` | All relations hold: shuffled rows, renamed case IDs, uppercase emails, injected post-cutoff file, added `.jr` decoy, contradicted screenshot, earlier audit_at | todo |
| T16 | Invariants on all 518 + blind silver-label audit + score band with per-case loss ledger | P1 | 10 | T09, T10 | `python3 code/evaluation/main.py invariants && python3 code/evaluation/main.py lossledger` | Invariants 518/518; every cited evidence_id exists and is ≤ audit_at; the loss ledger lists unresolved, not-observable, unproven and unlabeled cases with counts | todo |
| T17 | TypeSafe Jev judge (typesafe-sdk, pinned jev-1.14.0, disk-cached, advisory only) behind a spike gate | P2 | 9 | T01, T11 | `python3 code/evaluation/main.py judge-spike` | Spike reports AUROC ≥ 0.90 and repeat-stability ≤ 0.05, otherwise the judge stays disabled; output.csv hash unchanged with the judge on or off | todo |

**Build sequence** (critical path in bold): **T01 → T02 → T03 → T04 → T05 → T08 → T09** → T06 / T07 / T12 → T10 → **T15** → T16 → T13 → T11 → **T14**. T17 can run only after T11, and only if time allows.

---

## Baseline (2026-10-25, after T01–T03; trivial engine: every row NOT_APPLICABLE)

```text
$ python3 code/main.py
wrote 518 rows -> output.csv
$ python3 code/evaluation/main.py contract
CONTRACT OK (output.csv, 518 rows)
$ python3 code/evaluation/main.py determinism
L0.determinism: 2 runs identical (sha256 ce56a9432b8d)
$ python3 code/main.py --report
intent: 508 DELETION / 10 NOT_DELETION   (NOT_DELETION = case_533 … case_542)
identity: 518/518 resolved
$ python3 code/main.py --requests dataset/sample_deletion_requests.csv --out <scratch>/sample_pred.csv
$ python3 code/evaluation/main.py score --pred <scratch>/sample_pred.csv
```

| Split | status | identity | finding F1 | policy | evidence | strict step F1 | field mean | seq exact | LCS mean | row exact | **proxy** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev (22) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** |
| holdout (10) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** |
| all (32) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** |

- `finding_precision` reads 1.000. That is vacuous (no predictions) and is not part of the proxy.
- The first baseline attempt reported proxy 0.111 because field accuracy gave free credit when nothing aligned. That was fixed before this baseline.
- `runs/` (the history) is git-ignored and not committed.

## Where this board deviates from the relayed list (and why)

1. **T02 includes rules-only intent.** In the design, slice 1 is "skeleton end-to-end". A baseline run cannot write 518 *valid* rows without NOT_APPLICABLE detection, and ADR 0008 requires a rules-only path anyway. T11 keeps the cached OpenAI layer and the usage tracker.
2. **The handover txt moves from T06 to T04.** Design slice 2 starts with the handover text: explicit categories, sample case_11, 13 and 14, so it is the cheapest path to the first scored steps. T06 keeps the bundles, registers and record_lookup logs.
3. **T12 is P1 for PDFs and committed screenshot transcriptions, and P2 only for live vision.**
   - ADR 0005 (contradicted links) and the 42 h family (12 eval cases, 7 of them screenshot-backed) need screen facts, and the no-key fallback (ADR 0008) needs them committed.
   - T10's contradiction check therefore **depends on T12**.
4. **T15 is split by dependency.** The overlay helper can start after T02, but the relations need the full engine (T09). It stays P0, because it guards the determinism and cutoff ADRs.
5. **T17's spike gate is kept as given.** "jev-1.14.0" and `typesafe-sdk` are recorded as specified. I have no first-hand knowledge of this SDK, and it is verified in the spike before anything else (ADR 0013).

---

## Task cards

### T01 — Evaluation core [P0] · respects ADR 0001, 0002, 0007

- **Goal:** a trusted yardstick exists before any engine code.
- **Scope:**
  - The contract gate: every rule in `docs/03_DESIGN.md` §7 "Contract validator".
  - Scorer metrics: case status, step P/R/F1, field-level and sequence accuracy.
  - A frozen dev/holdout split (22/10) as a literal list in `code/evaluation/split.py`, balanced by status, and never changed afterwards.
  - The literal audit: grep `code/` for any `case_\d+` literal or any gold resource ID outside `code/evaluation/`.
  - Run history: one Markdown line per run with score and output hash.
  - The diff gate: the run fails if a dev metric drops by more than 0.02 against the last accepted run, unless the drop is explained in the history.
- **Acceptance:** `python3 code/evaluation/main.py selftest` gives `CONTRACT OK` on `dataset/sample_output.csv`, gold-vs-gold = 1.000, and the literal audit reports 0 hits.
- **Depends:** none.

### T02 — CSV loaders, identity, writer, rules-only intent [P0] · ADR 0001, 0008

- **Goal:** an end-to-end skeleton that writes 518 contract-valid rows.
- **Scope:**
  - Read the 7 CSVs.
  - Identity resolver: lowercase; current + historical emails via the audit chain; sha256 of each email; normalised phones; exact match only.
  - Rules-only intent (17 templates × 6 languages, plus negation and scope cues).
  - The writer: numeric sort; compact JSON in schema key order.
  - Deletion cases get `INCOMPLETE []` as a placeholder until T09.
- **Acceptance:** `python3 code/main.py && python3 code/evaluation/main.py contract` gives 518 rows OK; exactly case_533–542 are NOT_APPLICABLE; resolved subjects 518/518.
- **Depends:** T01.

### T03 — Evidence Store [P0] · ADR 0002, 0003, 0007

- **Goal:** the deep module from design §1–2, with the cutoff applied by construction.
- **Scope:**
  - The Observation, Coverage, Link and ActivityEvent types.
  - Indexes by identifier, resource and time.
  - `as_of(cutoff)`, which filters files by manifest `captured_at <= cutoff` and activity by `event_time <= cutoff`.
  - Latest-observation selection, and `proves_absent` via Coverage.
- **Acceptance:** the `test_store*` unit tests pass. They cover the post-cutoff invisibility, inclusive-boundary and latest-wins cases above.
- **Depends:** T02.

### T04 — Loaders: handover txt, service-export JSON, readback logs [P0] · ADR 0002, 0005, 0009

- **Goal:** the first three content-signature adapters, which cover sample case_11, 13, 14 and 21–30 and case_03, 18, 20.
- **Scope:**
  - The signature sniffer, which hard-errors on unknown shapes.
  - The handover adapter (CATEGORY/STATE columns).
  - The `service_exports` adapter.
  - The readback-log adapter with the `trace_id` join.
- **Acceptance:** `loaders --files evidence_03,evidence_92,evidence_94` finds every sample-cited pair with the right state and grounding.
- **Depends:** T03.

### T05 — Loaders: inventory SQL + replica SQL [P0] · ADR 0002, 0010

- **Goal:** SQL snapshots loaded into in-memory SQLite (the stdlib `sqlite3` module), with coverage only from proven-exhaustive tables (`snapshot_scope`, full table dumps). This is mitigation 1 in design §11.
- **Acceptance:**
  - all 24 SQL files load;
  - the 11 replica-only resources (data notes §5.2) are detected;
  - the 8 DELETION_PENDING accounts are found.
- **Depends:** T03.

### T06 — Loaders: bundles, registers, ledger, record_lookup logs [P1] · ADR 0002 (file-level cutoff, even for sub-snapshots)

- **Acceptance:** tombstone_440 is REDACTED and tombstone_9178 EXPOSED; `records: []` produces coverage; all JSON files load.
- **Depends:** T03.

### T07 — Loaders: observability logs (all dialects) [P1] · ADR 0002, 0005

- **Scope:** logfmt, bracket, pipe, JSON-line, syslog and cloud-runtime dialects; the trace join; PII-scan lines; heartbeat and noise filtering; restore candidates.
- **Acceptance:** all 26 logs load; the analytics_9914 hash link; the `.jr` decoy is rejected.
- **Depends:** T03, T04.

### T08 — State reconstruction + policy [P0] · ADR 0006, 0009, 0010, 0011, 0012

- **Scope:**
  - The latest observation at or before the cutoff, across every covering table; any replica presence counts as present.
  - EXPOSED vs PRESENT.
  - UNPROVEN.
  - Category precedence: tag > content > activity claim > system default.
  - Rule-row mapping (the design §3 table).
  - DELETION_PENDING = present; legal hold = retain; unobservable categories are logged.
- **Acceptance:** `states --split dev` agrees with the gold-implied state at ≥ 0.95.
- **Depends:** T04, T05.

### T09 — Verdict + planner [P0] · ADR 0001, 0004, 0006, 0007

- **Scope:**
  - The verdict rules, including the ADR 0006 edge case.
  - Step generation per the design table.
  - Evidence choice: the latest usable file naming the resource, or the covering file for absence.
  - Sort key `(op_rank, system_id, resource_id)` and step numbering.
- **Acceptance:** contract OK; sort key holds 32/32; dev scored; 0 activity or audit citations.
- **Depends:** T08.

### T10 — Linking [P1] · ADR 0003, 0004, 0005

- **Scope:**
  - The unique activity account candidate (window, then result↔status, then pre-audit identity filter, then global one-to-one elimination).
  - Catalog links checked against their artifact (CONTRADICTED / UNCONFIRMED).
  - Ties are logged as `UNRESOLVED_LINK`.
- **Acceptance:** 19/32 sample account hits, 0 wrong; 136 eval ties logged; case_63's link is rejected.
- **Depends:** T09, T12.

### T11 — Intent via cached OpenAI + usage tracker [P1] · ADR 0008, 0013

- **Scope:**
  - Pinned `gpt-5.4-mini-2026-03-17`, with the prompt in `code/prompts/intent.md`.
  - Cache in the generated `code/llm_cache.py`.
  - A ledger of model, tokens and cost.
  - The key comes only from `OPENAI_API_KEY`.
- **Acceptance:** with no key, 518 rows; with a key, a second run makes 0 calls and the ledger is populated.
- **Depends:** T02.

### T12 — PDFs + screenshot facts [P1; live vision P2] · ADR 0002, 0005, 0008

- **Scope:**
  - The pdftotext adapter.
  - Committed screen transcriptions (from `docs/02b`) as the no-key adapter.
  - Optional live vision with pinned `gpt-5.4-2026-03-05`, cached.
- **Acceptance:** the facts match `docs/02b` for all 4 PDFs and 11 PNGs.
- **Depends:** T03.

### T13 — Custom cases + report generator [P1] · ADR 0005, 0010, 0011

- **Scope:** ≥ 6 overlay fixtures with expected rows, and the `evaluation_report.md` generator. The report covers status, step, field and sequence metrics (dev and holdout), the custom cases, failures and improvements, the assumptions list, and the ADR 0006 measurement.
- **Acceptance:** 6/6 fixtures pass; the report contains every required section.
- **Depends:** T09, T15.

### T14 — Usage report, README, packaging, final validation [P0] · ADR 0008

- **Scope:**
  - `usage_report.md` generated from the final-run ledger. With no live calls, it states so with zero counts.
  - The README with setup, run, `--explain` and key variables (names only).
  - `code/package.py` builds `code.zip` with README.md + code/. It excludes `dataset/`, `.env`, nested archives and caches of dependencies.
  - The final gates.
- **Acceptance:** `package.py` lists the zip contents with no forbidden paths, and `final` is green.
- **Depends:** T09, T11, T13, T16.

### T15 — Metamorphic suite [P0] · ADR 0001, 0002, 0004, 0005

- **Scope:** an overlay helper (a copy-on-write dataset in a temp dir) and the relations in design §7.
- **Acceptance:** all relations hold.
- **Depends:** T02 for the helper, T09 for the relations.

### T16 — Invariants, silver audit, loss ledger [P1] · ADR 0002, 0004, 0006, 0012

- **Scope:**
  - The invariants on all 518 rows.
  - A blind silver-label audit: hand-review a random, seeded sample of about 20 eval cases with `--explain`, recording agree or disagree in Markdown.
  - The per-case loss ledger.
  - A score band, i.e. the expected range given the accepted losses in design §10.
- **Acceptance:** invariants 518/518; the ledger and band are written.
- **Depends:** T09, T10.

### T17 — TypeSafe Jev judge [P2] · ADR 0013

- **Scope:** the spike first, with gold labels on samples measuring AUROC and repeat stability. Only if both thresholds pass, an advisory judge is wired in, disk-cached, with the key only from `TYPESAFE_API_KEY`. It is never used to edit `output.csv`.
- **Acceptance:** spike metrics are reported; the output hash is identical with the judge on and off.
- **Depends:** T01, T11.
