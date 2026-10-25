# BOARD — ghost-audit build

- **Board backend:** this file. The `kanban-init` skill needs the `sqlite3` CLI, which is not installed in this cloud container (checked at session start), so the SQLite board was not created and this Markdown board is the source of truth.
- **Update this file whenever a task moves.**
- **Log:** T01 doing → done 2026-10-25 (selftest green, 34 unit tests). T01 fixes: optional pandas + specific check ids (39 tests). T02 doing → done (12 tests; acceptance green). Baseline run exposed 3 T01 bugs, fixed test-first (43 evaluation tests). T03 doing → done (10 store tests). T04 doing → done (loaders, 52/52 gold pairs). T05 doing → done (SQL, 10/10 gold pairs). T06 doing → done (bundles/registers/record_lookup, 42/42; ADR 0014 proposed). T07 doing → done (observability logs, 7 dialects, 15/15; store state check 0 contradictions, 1 pending on T12). T08 doing → done (states --split dev 51/51 on discovered resources; ADR 0014 risk 2 resources / 1 violation in eval). T09 doing → done (dev proxy 0.720, status 0.909; ADR 0015 proposed, then ratified). T12 doing → done (4 PDFs + 11 PNGs, store check 0 pending; empty INCOMPLETE 10 → 3). T10 doing → done (accounts 19/32 exact, 0 wrong; 136 eval ties logged; activity_4008 rejected; dev proxy 0.798). T15 doing → done (13/13 metamorphic relations hold). T16 doing → done (invariants 9/9 on 518/518; ledger unknown 0; silver 6 checked, 0 disagreements). Silver 7–20 blind (1 bug fixed). T11 doing → done (intent rules + cached model, 0 disagreements, 0 calls on rerun). T13 doing → done (12/12 custom cases; evaluation_report.md generated from real runs).
- **Statuses:** `todo` → `doing` → `review` → `done` (plus `blocked`).
- **Priorities:** P0 (must ship), P1 (should ship), P2 (only if time and gates allow).
- **Build slice** refers to `docs/03_DESIGN.md` §9. ADRs are in `docs/adr/`.

## Board

| ID | Title | Pri | Slice | Depends on | Acceptance command | Expected result | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | Evaluation core: contract gate, sample scorer (frozen 22/10 split), literal audit, run history + diff gate | P0 | 1 | — | `python3 code/evaluation/main.py selftest` | `CONTRACT OK (sample_output.csv, 32 rows)`; scorer gold-vs-gold = 1.000 on every metric; literal audit `0 hits`; the history line is written | done |
| T02 | CSV loaders, identity resolver, rules-only intent, output writer; baseline run writes 518 valid rows (trivial engine: every row NOT_APPLICABLE) | P0 | 1 | T01 | `python3 code/main.py && python3 code/evaluation/main.py contract && python3 code/main.py --report` | `CONTRACT OK (output.csv, 518 rows)`; numeric order; report shows intent 508 DELETION / 10 NOT_DELETION (exactly case_533–542) and identity resolved 518/518 (engine placeholder emits NOT_APPLICABLE for all, because an empty INCOMPLETE is invalid under the gate) | done |
| T03 | Observation/Coverage/Link models + Evidence Store with identifier/resource/time indexes and the `as_of(cutoff)` view | P0 | 2 | T02 | `python3 -m unittest discover -s code/tests -p 'test_store*.py'` | All pass, including: a later file is invisible through `as_of`; inclusive `<=` boundary (evidence_03 at case_11's audit_at); latest-observation ordering (evidence_30 account_2088 404 → 200), all modelled as synthetic observations until the loaders land in T04–T07 | done |
| T04 | Loaders: handover txt + service-export JSON + readback logs (trace_id join) | P0 | 2/4/5 | T03 | `python3 code/evaluation/main.py loaders --files evidence_03,evidence_92,evidence_94` | Every sample-cited (file, resource) pair in those files is found with the correct state, and the identifier is resolved via trace_id; `0 unknown signatures` | done |
| T05 | Loaders: inventory SQL (snapshot_scope coverage) + replica SQL (primary vs replica drift) | P0 | 3 | T03 | `python3 code/evaluation/main.py loaders --kind sql` | All 24 SQL files load; replica-only resources = the 11 listed in data notes §5.2 (incl. account_005, account_994); 8 DELETION_PENDING rows found (§7.6) | done |
| T06 | Loaders: snapshot bundles, record-list JSON (registers, ledger), notification/record_lookup logs | P1 | 4 | T03 | `python3 code/evaluation/main.py loaders --kind json,register-log` | evidence_51 tombstone_440 is REDACTED and tombstone_9178 EXPOSED; `records: []` produces coverage; all 28 JSON files load; `0 unknown signatures` | done |
| T07 | Loaders: observability logs, all dialects (trace join, PII scans, heartbeats, restore candidates) | P1 | 5 | T03, T04 | `python3 code/evaluation/main.py loaders --kind log` | All 26 logs load; evidence_01 line 92 analytics_9914 is linked by hash to user_12; the `.jr` decoy search_1874 is NOT linked to user_13 | done |
| T08 | State reconstruction (latest ≤ cutoff, coverage absence, replica rule) + policy/category mapping | P0 | 2–7 | T04, T05 | `python3 code/evaluation/main.py states --split dev` | Per-resource state matches gold-implied state on dev ≥ 0.95; category precedence tag > content > activity > system default | done |
| T09 | Verdict + step planner + evidence selection + sort + serialisation | P0 | 2 | T08 | `python3 code/main.py && python3 code/evaluation/main.py score --split dev` | Contract OK; sort key holds 32/32; dev status accuracy reported, with the target ≥ 0.85 once T04–T08 are done; no step cites an activity or audit ID | done |
| T10 | Linking: catalog links + contradiction check, source refs, activity account candidates (unique only, ties omitted and logged) | P1 | 6, 8 | T09, T12 | `python3 code/evaluation/main.py linking` | Samples: 19/32 exact account hits, 0 wrong; eval: 136 tied cases logged as `UNRESOLVED_LINK`; activity_4008 is `CONTRADICTED` and case_63 has no marketing_001 step | done |
| T11 | Intent: cached OpenAI (pinned) over the rules-only path + usage tracker | P1 | 9 | T02 | `python3 code/main.py` (no key), then `OPENAI_API_KEY=… python3 code/main.py` | With no key: 518 rows, intent from rules + committed cache. With a key: cache misses are called, and the ledger shows model, tokens and cost; a second run makes 0 calls | done |
| T12 | PDFs (pdftotext) + screenshot facts: committed transcriptions first, cached live vision second | P1 (vision part P2) | 8 | T03 | `python3 code/evaluation/main.py loaders --kind pdf,png` | 4 PDFs and 11 PNGs give the facts in docs/02b; evidence_60 visible identity = sj.park@naver.com | done |
| T13 | Custom evaluation cases (≥ 6 fixtures) + evaluation_report.md generator | P1 | 10 | T09, T15 | `python3 code/evaluation/main.py custom && python3 code/evaluation/main.py report` | 6/6 fixtures pass (replica-only account, DELETION_PENDING, contradicted screenshot, legal hold, uppercase historical email, post-cutoff resurrection); report written with every required section | done |
| T14 | usage_report.md, README, packaging script, final validation | P0 | 10 | T09, T11, T13, T16 | `python3 code/package.py && python3 code/evaluation/main.py final` | code.zip contains README.md + code/ only (no dataset/, .env, *.zip, __pycache__); final gates green; output.csv 518 rows | todo |
| T15 | Metamorphic suite: dataset overlay helper + relations | P0 | 10 | T02 (helper), T09 (relations) | `python3 code/evaluation/main.py metamorphic` | All relations hold: shuffled rows, renamed case IDs, uppercase emails, injected post-cutoff file, added `.jr` decoy, contradicted screenshot, earlier audit_at | done |
| T16 | Invariants on all 518 + blind silver-label audit + score band with per-case loss ledger | P1 | 10 | T09, T10 | `python3 code/evaluation/main.py invariants && python3 code/evaluation/main.py lossledger` | Invariants 518/518; every cited evidence_id exists and is ≤ audit_at; the loss ledger lists unresolved, not-observable, unproven and unlabeled cases with counts | done |
| T17 | TypeSafe Jev judge (typesafe-sdk, pinned jev-1.14.0, disk-cached, advisory only) behind a spike gate | P2 | 9 | T01, T11 | `python3 code/evaluation/main.py judge-spike` | Spike reports AUROC ≥ 0.90 and repeat-stability ≤ 0.05, otherwise the judge stays disabled; output.csv hash unchanged with the judge on or off | todo (single-call gate failed; mean-of-10 ranker gate passed: ranker-only judge allowed, not built) |

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

## Loader deltas

| Task | Built signatures (files) | Observations | Gold-cited pairs (selected files) | Unattributed / unparsed | Scorer proxy (dev/hold/all) | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| T04 | txt:handover (1), json:service_exports (11), log:readback (11) | 601 | 52/52 ok (evidence_03, 92, 94); 41 owner-linked, 11 records carry no identifier | 101 / 0 | 0.000 / 0.000 / 0.000 (Δ 0) | The sniff collision was caught by the summary: 3 observability logfmt files also use `lookup_key=`, so readback now requires its exact line grammar (test-first). The scorer cannot move until the engine (T08/T09) consumes observations. |
| T05 | + sql (24) | 891 (total 1,492) | 10/10 ok (all sample-cited SQL pairs; 3 absences proven by coverage only); 7 owner-linked | 106 / 0 (all-null analytics blobs, duplicated across primary/replica tables) | 0.000 / 0.000 / 0.000 (Δ 0) | Coverage: 243 entries, from dumped typed tables (per table), generic tables (per origin_system listed) and inventory snapshot_scope. Drift: 13 replica-only resources in 11 files; 8 DELETION_PENDING rows. **Finding for T10:** `ticket_attachments` rows carry `ticket_id` + `uploaded_by`, and `search_documents_primary` carries `source_resource_id`, so these are join keys for linking. |
| T06 | + json:snapshots (12), json:records (5), log:record_lookup (2) | 669 (total 2,161) | 42/42 ok (all json + register-log cited pairs); 30 owner-linked, 11 records carry no identifier. **Whole-store state check: 75 cited gold expectations, 0 contradictions, 7 pending (cited files are observability logs or a PDF, T07/T12)** | 50 / 0 | 0.000 / 0.000 / 0.000 (Δ 0) | **Design assumption broken.** Bundle collections, empty lists and inventory scope are NOT exhaustive (7 gold contradictions). Proposed **ADR 0014** (weak coverage: omission proves ABSENT only if nothing visible shows the resource present), adopted provisionally, enforced in `CaseView.state` (test-first). Register rows (incl. bundle `operational_record_history`) never emit coverage. |
| T07 | + log:observability (13; 7 dialects: logfmt, JSON-after-timestamp, syslog, bracketed, pipe, cloud-runtime, support replica) | 733 (total 2,894) | 15/15 ok (all log-cited pairs, `--kind log`); 14 owner-linked, 1 record carries no identifier. **Whole-store state check: 75 cited gold expectations, 0 contradictions, 1 pending (case_07 cites a PDF, T12), 0 unproven** | 22 / 0 (28 not attributable to a person: 21 analytics reads keyed by resource id, 1 attachment_preview line, 6 look-alike keys) | 0.000 / 0.000 / 0.000 (Δ 0) | Owner = the record line's own identifier fields + the `*_started` keys of the same (service, trace). analytics_9914 → user_12 via sha256 `correlation_key`; search_1874 `match_key` `g.silva76.jr@gmail.com` resolves to nobody (user_13 owns only `g.silva76@gmail.com`). Service aliases: support_replica, attachment_preview → support_platform; profile_service → account_service (table keeps the service name). Restore candidates → RESTORABLE/BLOCKED, `decision=deny` → BLOCKED. The only `_started` lines without a record line are log_router collector headers. No coverage: these are query traces, and the collectors report `dropped_auxiliary`. |

## T08 result

- `python3 code/evaluation/main.py states --split dev`: 77 gold resources on dev; 51 discovered by grounded identifiers (SAME_RECORD / TRACE_JOIN); state agreement **51/51 = 1.000**; end-state operation agreement 51/51. Not discovered: 26 (account_service 14, security_service 6, analytics_platform 5, support_platform 1), all needing T10 linking or T12 images/PDFs. 1 extra resource: case_17 account_6523, a real 404 lookup for the subject's email (evidence_67 line 3) that gold does not list.
- Policy: `deletion_rules.csv` is read as data; category signals are the ordered table `policy.CATEGORY_SIGNALS` (tag > content > activity > system default), unit-tested.
- **ADR 0014 risk** (`states --risk`, all 518 eval requests): 2 of 1,123 non-absent resources are PRESENT only because an older sighting survives a later omission, both in case_34 (support_9538 from evidence_01 line 25, a violation; audit_record_3753 from evidence_01 line 59, compliant). Both are omitted by evidence_02 / evidence_05 / evidence_93. Over-production of INCOMPLETE from ADR 0014 is therefore at most 1 case.

## T09 result

- `python3 code/main.py && python3 code/evaluation/main.py score --split dev` (score now runs the solver on the 32 samples when `--pred` is omitted).
- **Dev (22):** proxy **0.720** (was 0.000); status 0.909; finding P/R 1.000/0.968; evidence 0.769; strict step F1 0.653; unordered 0.884; field acc op/state/evidence 1.000; sequence exact 0.227; LCS 0.677. **Holdout (10, aggregate only):** proxy 0.741, status 0.900.
- Every dev difference is a **missing** resource (primary accounts, audit records and analytics that need T10 linking or T12 PNG/PDF loaders), except one extra grounded 404 (case_17 account_6523). No wrong operation, state or citation on any aligned step.
- Contract OK on 518 rows; sort key holds 32/32; 0 activity or audit citations (1,017 cited steps, all `evidence_N`; 1,645 uncited future steps). Determinism: 2 runs identical (sha256 1de4f1d4a84f).
- 10 eval cases (4 samples) have nothing grounded: **ADR 0015 (proposed)** writes them as INCOMPLETE `[]`; the gate counts them as a warning instead of a violation.

## T12 result

- `python3 code/evaluation/main.py loaders --kind pdf,png`: 4 PDFs (pdftotext, pypdf fallback, hard error without either) and 11 PNGs (committed transcriptions keyed by sha256, re-verified by viewing every image) give the docs/02b facts. evidence_60's visible identity is `sj.park@naver.com` / `+82 10-5837-9451`, which resolves to nobody. Screens and documents without a printed resource id (evidence_18, 27, 42, 46) become units, never invented ids.
- Whole-store state check: 75 cited gold expectations, **0 contradictions, 0 pending** (case_07 support_001 now PRESENT from evidence_58, category SUPPORT_ATTACHMENT from content).
- Score: dev proxy 0.720 → **0.731** (case_07 gains its finding, remediation and verification); holdout aggregate 0.741 (unchanged). `L0.empty_incomplete` on eval: **10 → 3** (case_55 backup without a restore flag is unproven; case_61 and case_63 need T10).

## T10 result

- `python3 code/evaluation/main.py linking`: samples **19/32 exact, 0 wrong**, 5 tied (case_23 triple; case_25/26 and case_28/29 pairs), 8 no candidate (the hand-written regime). Eval: surviving candidates per deletion request {0: 12, 1: 360, 2: 110, 3: 26} → **360 linked, 136 tied** (logged `UNRESOLVED_LINK` with reason and candidates), 12 no candidate (the 42 h family). One named constant `ACCOUNT_DELETE_WINDOW_HOURS = (0.5, 1.5)`; result↔status filter; pre-audit identity filter; global one-to-one over all 550 requests; no tie-break.
- Catalog links checked against their artifact: 8 CONFIRMED, **activity_4008 CONTRADICTED** (evidence_60 shows sj.park@naver.com / +82 10-5837-9451, nobody), 3 UNCONFIRMED (activity_4007 object_19, 4009 export_1842, 4011 tombstone_17: no artifact names the resource). case_63 has no marketing_001 step (generic check: 0 steps on rejected resources).
- Search `source_resource_id` links the source account (case_06 account_006). Citations follow docs/02 §4.3: the latest file **naming** the resource; a covering file only for absence by omission (fixed: case_21/27 now cite evidence_92, not evidence_51).
- case_17 account_6523: a prior-lifecycle 404 (evidence_67, the March readback for the same subject's case_46); the id is deleted again on 09-15 inside case_03's window. **ADR 0016 (proposed):** a resource seen only ABSENT before `requested_at` is dropped (`STALE_LINK`); 1 sample, 0 eval rows affected.
- Score: dev proxy 0.731 → **0.798** (finding F1 1.000, evidence 0.846, strict step F1 0.792, sequence exact 0.364); holdout aggregate 0.741 → **0.805**; status dev 0.909, holdout 0.900. `states --split dev`: 59/59 discovered resources agree, 0 extras. `L0.empty_incomplete` eval: 3 (case_55 unproven backup, case_61 unconfirmed catalog claim, case_63 rejected claim).

## T15 result

`python3 code/evaluation/main.py metamorphic` (overlay = a full temporary copy of dataset/, never edited; the real `code/main.py` runs over it; targets are picked from the baseline at run time). **13/13 hold**, about 63 s:

| Id | Transformation | Predicted effect | Result |
| --- | --- | --- | --- |
| M1 | shuffle rows of every input CSV | identical | holds |
| M2 | rename every evidence file, upper-case extension | identical, evidence_ids included (they are manifest file_ids; dispatch is by content) | holds |
| M3 | upper/lower-case request emails | identical | holds |
| M4 | `.jr` look-alike of a subject's email, pre-audit | identical; no step on the decoy resource | holds |
| M5 | post-audit file naming a subject | identical (ADR 0002) | holds |
| M6 | post-audit file contradicting an absent account | identical | holds |
| M7 | audit_at moved 1 s before the latest cited file | that file no longer cited; all citations ≤ new audit_at; others unchanged | holds |
| M8 | replica-only copy of an account at audit_at | COMPLETE → INCOMPLETE with REPORT_REMAINING_RECORD citing the new snapshot | holds |
| M9 | remove the most-cited file (evidence_08, 10 rows) | only dependent cases change (10/10 within dependents) | holds |
| M10 | duplicate a non-deletion and a deletion text under new ids | identical intent | holds |
| M11 | delete one candidate of a tie whose other candidate is not shared | the other becomes the unique linked account | holds |
| M12 | re-point a confirmed catalog claim to another subject | REJECTED_LINK (the screen shows the real owner), no step, nothing else changes | holds |
| M13 | PYTHONHASHSEED 0 / 4242 / random | byte-identical output | holds |

The first run had M8 failing. The cause was the **relation's target**, not the pipeline: the injected copy (audit − 1 min) was older than an explicit 404 at exactly audit_at, so the latest-observation rule correctly kept the account absent. The target selection now enforces the precondition (the copy is the newest sighting); the prediction is unchanged.

## T16 result

- `python3 code/evaluation/main.py invariants`: **9/9 invariants hold on 518/518 rows.** I1 cited evidence exists and is ≤ audit_at; I2 finding → remediation + verification; I3 COMPLETE = cited verification only; I4 no activity/audit citation; I5 no literals in code/; I6 status matches steps; I7 the cited file names (or covers) the resource; I8 prefix matches system_id; I9 the INCOMPLETE plan is uncited.
- `python3 code/evaluation/main.py lossledger` → `docs/LOSS_LEDGER.md` (every eval case with its reasons and case ids): fully grounded 344, unresolved:tied 136, unresolved:window 12, non-deletion 10, DELETION_PENDING 8, legal hold 6, unproven 4, INCOMPLETE [] 3, unresolved:catalog 3, contradicted 1; **unknown 0**. Step-recall ceiling estimate **~0.89** (2,884 steps emitted, ~350 expected missing).
- Silver audit (`docs/SILVER_AUDIT.md`): 20 cases stratified by reason (seed 20261025); the first 6 were checked by hand from raw file lines: **0 disagreements**; 2 probable misses (anonymized analytics reachable only through activity bursts, the known loss class).

## Silver audit, cases 7–20 (blind)

Four sub-agents audited 14 eval cases from `dataset/` only (no engine output, code or docs); `docs/SILVER_AUDIT.md` compares each with the engine. 9 agree; **1 engine bug** (case_431, case_347: a templated `message_excerpt` outranked the DELETE_RECORD claim, against ADR 0009), fixed with a regression test, which changes 12 eval rows; 5 documented assumptions (unconfirmed catalog claims, backup without a restore flag, COMPLETE vs INCOMPLETE `[]`, timing-only analytics). Samples unchanged (dev proxy 0.798, 59/59 states).

## T11 result

- Prompt `code/prompts/intent_classifier.md`: three atomic yes/no questions (asks_to_delete, asks_to_verify_or_finish_deletion, excludes_deletion) plus a rationale; the message is delimited data and embedded instructions are ignored; five invented few-shot examples (a test checks that no dataset text appears).
- `chat.completions` with the pinned `gpt-5.4-mini-2026-03-17`, strict JSON schema, `seed=20261025`, `reasoning_effort="none"`, `store=False`. The cache module is `code/ghostaudit/llm_cache.py` (398 entries, sha256(model + prompt + text) keys, no request text).
- `python3 code/evaluation/main.py intent`, over 398 unique texts / 550 requests: rules vs model confusion DELETION→DELETION 388, NOT_DELETION→NOT_DELETION 10, **0 disagreements**. Final NOT_DELETION = case_533–542 exactly. 6 texts are decided by the model (both cue kinds fire), 512 rows by clear rules.
- Usage: 398 live calls for the review (363,369 input / 20,163 output tokens, $0.3633), plus 1 synthetic probe call (894 / 48, $0.0009); price $0.75 / $4.50 per 1M (OpenAI model page). Second run with a key: **0 calls**, 12 cache hits. The no-key run and `--intent rules` are byte-identical to the keyed output.

## T13 result

- `python3 code/evaluation/main.py custom`: **12/12** hand-written custom rows pass, from 11 fixtures (`code/evaluation/fixtures/custom_cases.py`): replica-only account, DELETION_PENDING, contradicted catalog link (a log artifact; screens are hash-keyed transcriptions), legal hold, uppercase historical email, post-cutoff resurrection, redacted tombstone, exposed tombstone, marketing-only trap, tied candidates (2 rows, UNRESOLVED_LINK checked in the log), attempted-but-unproven delete. All people and texts are synthetic and dated 2027; the 518 real rows are unchanged (checked). The trap text's model verdict was fetched once and cached (1 new cache entry).
- `python3 code/evaluation/main.py report` writes `code/evaluation/evaluation_report.md` from real runs (~100 s): approach, pipeline layers, sample results (dev, holdout aggregates, run history), custom cases, metamorphic table, invariants, loss ledger and ceiling, silver audit with its limits, unlabeled-rule assumptions (DELETION_PENDING 8, legal hold 6, empty INCOMPLETE 3, stale link 0), failures and improvements, limitations with costs, and reproduction. `render()` is pure and unit-tested; generated reports are exempt from the literal audit by name (test-first).

## T17 spike result (gate)

`docs/JEV_SPIKE.md`. Jev `jev-1.14.0` is reachable from the container. 50 propositions (25 true / 25 false, 5 perturbation kinds): AUROC 0.959 (supports) / 0.945 (supports − contradicts) passes; repeat stability over 20 identical requests: Δp = 0.090 > 0.05 **fails**. No option-order bias (0/18 changes). 88 calls, 60,871 in / 3,614 out tokens, median latency 107 ms, ≈ $0.003. **Gate FAIL: no judge code is built**; the fallback is the blind sub-agent audit.

## Robustness: optional dependencies and API failures (peer-reported bug)

A key set without the `openai` package crashed `main.py` (and the custom run). Fixed test-first (`code/tests/test_degrade.py`, 7 tests): guarded SDK import with one warning; bounded retries (2) with backoff and JSON/schema validation; failures recorded (usage log, `degraded` count) and never cached; an end-of-run decision summary; committed PDF text cache, so no PDF tool is needed. Two whole-pipeline subprocess tests: a fake key with `openai` blocked, and a client that raises on every call (over an overlay with a fresh remainder text); both give output byte-identical to the cache-only / no-key run. Acceptance in both environments (key unset; key set + openai blocked): selftest OK, determinism eb99c26b7974, invariants 9/9, custom 12/12, metamorphic 13/13; outputs byte-identical to each other, to the committed output.csv, and to a run with no `pdftotext` on PATH.

## T17 follow-up spike (mean of k = 10)

Pre-registered rule committed before running. Mean of 10 calls, two independent rounds: AUROC 0.949/0.949, max round difference 0.030 → **PASS** (with code-computed facts in state: 0.962/0.962, 0.037 → PASS). A ranker-only advisory judge is therefore allowed later; not built. Decoy-owner and wrong-operation propositions stay weak (mean score +0.12…+0.20), and the identifier_match fact did not fix decoy owner, so ownership stays deterministic in code. 2,000 calls, 1.47M input tokens, ≈ $0.062, 24 s.

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
