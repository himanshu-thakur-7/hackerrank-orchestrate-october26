# Submission readiness (2026-10-25)

- **Checked against:** `problem_statement.md`, `README.md` (starter text, now replaced by the submission README), `agent_trace_instructions.md` and `AGENTS.md`.
- **Gate result:** `python3 code/evaluation/main.py final --matrix` is GREEN (24/24). `output.csv` sha256 is `eb99c26b7974`.
- **"Needs the owner"** marks anything that cannot be verified or done from this cloud session.

## A. Deliverables checklist

| # | Requirement (source) | Status | Satisfied by / evidence |
| --- | --- | --- | --- |
| 1 | `output.csv` with exactly 518 data rows, sorted by `case_id` (problem_statement "Required Output") | ✅ | `output.csv` at the repo root. It has 518 rows, the same id set as `dataset/deletion_requests.csv`, and is sorted numerically (ADR 0001). |
| 2 | Header `case_id,deletion_status,steps_json` (problem_statement, README) | ✅ | The first line is exactly that header. LF line endings, no BOM. |
| 3 | Quoting and valid JSON arrays; `NOT_APPLICABLE` uses `[]` (README "Output") | ✅ | Standard CSV quoting (`"[{""step_no"":1,…}]"`). The stdlib csv round-trip and the optional pandas round-trip both pass. All 518 values are JSON arrays; the 10 NOT_APPLICABLE rows are `[]`. Statuses: INCOMPLETE 357, COMPLETE 151, NOT_APPLICABLE 10. |
| 4 | Steps: consecutive `step_no`, phase order, evidence rules (problem_statement, README) | ✅ | Contract gate `CONTRACT OK (518 rows)`; invariants 9/9 on 518/518. One warning: `L0.empty_incomplete` on 3 rows (ADR 0015, see risk R1). |
| 5 | `code.zip`: runnable solution, prompts, configuration, README (problem_statement "Submission") | ✅ | `python3 code/package.py` → `code.zip` with 120 files, 841,852 bytes uncompressed, 282,211 bytes zipped. Contents: `README.md` + `code/` (the solver `code/ghostaudit/`, `code/main.py`, prompts in `code/prompts/`, evaluation harness, tests). |
| 6 | No `dataset/`, venvs, `__pycache__`, nested archives, keys (README "Packaging") | ✅ | `code/evaluation/tests/test_package.py` opens the zip and asserts this; the key-pattern scan of the zip and all tracked files finds 0. |
| 7 | Evaluation report with case-level, step-level and field-level accuracy, sequence accuracy, ≥ 3 custom cases, failures and improvements (problem_statement "Evaluation") | ✅ | `code/evaluation/evaluation_report.md` (in the zip), generated from real runs. §3 metrics, §4 has 12 custom cases (all pass), §10 lists failures and fixes. |
| 8 | `usage_report.md` for the final full-dataset run: providers and models, calls, input/output tokens, total and average per request, total and per-request cost, per-model and overall totals (problem_statement "Token Usage") | ✅ | `code/evaluation/usage_report.md` (in the zip), generated from a measured run whose output equals `output.csv`. That run made 0 live calls (12 cache hits). It also gives the cache origin (399 calls, $0.3642) and the evaluation-only Jev usage (11,450 calls, $0.3734). |
| 9 | Report location | ⚠️ needs the owner | `problem_statement.md` says "`code.zip` must include `evaluation/evaluation_report.md`". The starter README says "Place `evaluation_report.md` and `usage_report.md` inside `code/evaluation/`". We follow the README: the zip has `code/evaluation/…`. If a top-level `evaluation/` folder is also wanted, that is a one-line change in `code/package.py`. |
| 10 | `chat_transcript` = root `log.txt` in the AGENTS.md turn format (README "Chat Transcript") | ✅ (upload: owner) | `log.txt` has 49 entries after this turn. Every entry has exactly one `tool=` and one `model=` line, and the key scan finds 0 secrets. The owner uploads it to the `chat_transcript` slot. |
| 11 | Agent trace ZIP (`agent_trace_instructions.md`) | ❌ needs the owner | See section B. |
| 12 | AI interview (problem_statement "Submission") | needs the owner | Material: `README.md` (architecture), `docs/03_DESIGN.md`, `docs/adr/`, `code/evaluation/evaluation_report.md`. |
| 13 | Upload | needs the owner | Challenge and submission link: https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists. The challenge end time is not configured in this repository. |

## B. Agent trace: what is required and what is still to do by hand

The instructions require (quoted):

- "Please submit the complete agent trace for the work you did on this challenge as a **ZIP file**."
- "Include every session you used for this challenge, including sessions in which you planned, coded, debugged, or reviewed the solution. If you used more than one agent harness, include traces from each one. Keep the original files and folder structure where practical; do not convert JSONL, SQLite, or other structured logs into screenshots or summaries."
- "Finish the session(s) you intend to submit, then quit the app or CLI before copying its files."
- "Create a temporary folder named `agent-trace` … Keep each tool in its own subfolder, for example `agent-trace/claude-code/`."
- Claude Code: "Claude Code stores session transcripts by project under: macOS/Linux: `~/.claude/projects/` … copy the session files you created for this challenge into `agent-trace/claude-code/`."
- "In each Claude Code session, run: `/export` … include the original session JSONL files as well when available."
- "Remove or redact secrets (API keys, tokens, passwords, cookies, private keys), personal information … Do not include authentication files, settings, or credentials."
- "Zip the `agent-trace` folder … Name the result `agent-trace.zip`." … "Open the ZIP once after creating it and confirm it contains the intended traces and no credentials or unrelated files."

What we can and cannot verify:

- **This session (cloud).** Its JSONL is at `/root/.claude/projects/-home-user-hackerrank-orchestrate-october26/` **inside this ephemeral cloud container**, not on the owner's machine. The container is reclaimed after inactivity, so the file must be retrieved before that.
  - **Needs the owner:** decide how to obtain it, for example `/export` from this session, or ask me to stage a copy in the scratchpad for download.
- **The peer session "Prompt playbook website publishing"** relayed every prompt, so it is part of the trace. **Needs the owner:** export it as well.
- **Any other harness or session used for this challenge.** I cannot see these. **Needs the owner.**
- **Sub-agents.** Their activity (the 4 blind silver auditors) is inside this session's trace. Their log entries are in `log.txt` with `parent_agent=Claude Code (main session)`.
- **Redaction review of the staged files.** **Needs the owner.** API keys were only ever read from the environment and never printed, but the owner must still review the staged files.

## C. AGENTS.md, rule by rule

| Section | Rule | Status | Evidence |
| --- | --- | --- | --- |
| §0, §2, §5 | Append-only `log.txt` beside AGENTS.md; a SESSION START entry; one entry per user turn; UTF-8, `\n` line endings | ✅ | 1 SESSION START plus 48 turn entries; old entries were never rewritten (the one wrong entry got an appended correction). |
| §5 | `tool=` and `model=` exactly once per entry, with authoritative values | ✅ / ⚠️ | All 49 entries have exactly one of each. `tool=Claude Code` everywhere. Session metadata now reports `claude-opus-5-5` (`last_served_model`), which matches the current entries. **The 4 earliest entries record `claude-haiku-5-5`.** I cannot re-verify which model served those turns. They are left as recorded (append-only). |
| §5.3 | Sub-agents log to the same file with `parent_agent` | ✅ | 4 silver-audit entries. |
| §5.4, §4.4 | No secrets or real personal data; keys only from the environment | ✅ | Code checks only whether `OPENAI_API_KEY` / `TYPESAFE_API_KEY` are set (`os.environ.get`), and the SDKs read them. No `.env` loading. The repo key scan finds 0. |
| §3 | Greeting at session start; deadline not invented | ✅ | The greeting is in this session's transcript; the deadline is reported as "not configured". |
| §4.3, §6.7 | Only `dataset/` data; no organizer files, golden labels or case shortcuts | ✅ | The literal audit over `code/` finds 0 hits (`I5`). `sample_output.csv` is read only by the evaluation harness (scoring), never by the solver. |
| §4.1 | Submission link given verbatim when asked | ✅ | Row A13. |
| §6.3–6.6 | Output contract | ✅ | Rows A1–A4. |
| §6.7 | Runnable from the terminal; reads `dataset/`; writes root `output.csv`; deterministic; README with setup | ✅ | `python3 code/main.py`. Determinism: 2 runs identical. Clean room: same sha256 with keys unset. Same output on Python 3.11, 3.12 and 3.13. |
| §6.8 | Evaluation and usage reports in the zip | ✅ | Rows A7–A9. |
| §6.9 | No dataset, venv, caches, nested archives, keys or real personal data in `code.zip` | ✅ / ⚠️ | See risk R3 on derived (fictional) dataset content. |

## D. Security pass

- **Secrets:**
  - The key-shaped pattern scan (`sk-…`, `apikey_…`) finds 0 hits in tracked files and in `code.zip`.
  - A broader scan (private-key headers, GitHub/AWS/Slack token shapes, `password`) finds nothing of ours. The only hit is a third-party skill template, `.claude/skills/kanban-init/templates/.env.example`, with placeholder `user:password@host` (not in the zip).
- **Committed caches:**
  - `llm_cache.py`: 399 entries, keyed by sha256. Values are `answers` (3 booleans plus a model `rationale` of at most 134 characters), `label` and `model`.
    - No identity email appears in any rationale, and none has `@`, a run of 4+ digits or a `user_N` reference.
    - One rationale shares an 8-word generic phrase with a request text: "deletion of the account registered to this email address". It contains no identifier.
  - `jev_cache.py`: 1,145 entries with numbers only (`supports`, `contradicts`, `k`, `model`).
  - ORIGIN records in both caches hold calls and tokens only.
- **Absolute paths:** none in `code/`, `docs/`, `README.md` or the zip. `log.txt` contains `repo_root=/home/user/…` because AGENTS.md §5 requires it.
- **Reads outside the repo:** none. `code/` never uses `~`, `Path.home`, `expanduser` or system paths.
  - The solver reads only `--data` (default `dataset/`) and its own committed modules.
  - Environment variables read: the key presence checks, `GHOSTAUDIT_RUNS_DIR`, `GHOSTAUDIT_REVEAL_LOG`, and `GHOSTAUDIT_BLOCK_MODULES` (test matrix only).

## E. Risks the owner should decide on

- **R1. ADR 0015:** 3 rows are `INCOMPLETE,[]`. The one-line revert is in the README "Known risks".
- **R2. Report path:** see row A9.
- **R3. Derived dataset content in `code.zip` (all fictional):**
  - **What it is:**
    - the PDF text cache (4 PDFs, 5.3 KB);
    - screenshot transcriptions (11 PNGs, 9.7 KB);
    - 19 small evidence excerpts used as test fixtures (80 KB).
  - **Why it is there:** these let the run work with no PDF tool or vision model and keep the tests self-contained.
  - **Rule check:** `dataset/` itself is not included, and the data is fictional (AGENTS §7). If the judges read "no dataset" strictly, these would have to be dropped, which costs the no-tool reproducibility.
- **R4. The 4 earliest log entries name `claude-haiku-5-5`.** This can't be verified now (row C2).
