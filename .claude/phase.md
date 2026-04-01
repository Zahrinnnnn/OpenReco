# phase.md — OpenReco Build Phases

---

## Phase 1 — Project Foundation
**Target:** Week 1
**Status: DONE**

Set up everything before any agent logic is written. This phase is about structure, not features.

### Tasks
- [x] Initialise git repo, push to https://github.com/Zahrinnnnn/OpenReco.git
- [x] Create full folder structure as defined in CLAUDE.md
- [x] Write `requirements.txt` with all dependencies
- [x] Write `.env.example` with all required variables (no real keys)
- [x] Add `.gitignore` (exclude `.env`, `data/`, `__pycache__`, `.venv`)
- [x] Create SQLite schema in `src/database/connection.py` — tables: `recon_sessions`, `matches`, `exceptions`, `audit_log`
- [x] Write `src/database/queries.py` with basic insert and select functions for each table
- [x] Define `RecoState`, `Transaction`, `LedgerEntry`, `Match`, `Exception` TypedDicts in `src/graph/state.py`

### Done when
- Folder structure exists and is pushed
- SQLite database initialises cleanly when `connection.py` runs
- All TypedDicts are importable with no errors

---

## Phase 2 — Agent 1: Document Ingestion
**Target:** Week 1
**Status: DONE**

### Tasks
- [x] Write `src/agents/document_ingestion.py`
- [x] Load bank statement CSV using pandas
- [x] Auto-detect columns: date, description, debit, credit, reference
  - Try to parse date-like columns using `python-dateutil`
  - Detect numeric columns for amounts
  - Use longest text column as description
  - If ambiguous, call DeepSeek to infer from first 5 rows
- [x] Normalise dates to `YYYY-MM-DD`
- [x] Clean amount strings (strip commas, currency symbols)
- [x] Handle single-amount-column banks with Dr/Cr suffixes
- [x] Generate a unique ID per transaction (hash of date + amount + description)
- [x] Filter transactions to `period_start` / `period_end`
- [x] Deduplicate by hash
- [x] Write `src/utils/normaliser.py` — shared date and amount cleaning functions
- [x] Write `src/utils/validators.py` — validate that required state fields are present before agent runs
- [x] Add error handling: file not found, missing columns, unparseable rows
- [x] Write fixture `tests/fixtures/sample_bank.csv` with 20+ test transactions
- [x] Write basic tests in `tests/test_agents.py` for this agent

### Done when
- Agent parses sample_bank.csv and returns a clean list of Transaction dicts in state
- Invalid rows are skipped and logged, not crashing
- Tests pass

---

## Phase 3 — Agent 2: Ledger Sync
**Target:** Week 1
**Status: DONE**

### Tasks
- [x] Write `src/agents/ledger_sync.py`
- [x] Load ledger CSV using pandas
- [x] Normalise to `LedgerEntry` schema (date, description, reference, amount, entry_type)
- [x] Filter to reconciliation period
- [x] Generate unique ID per entry
- [x] If columns don't match expected headers, call DeepSeek to map them
- [x] Add error handling: empty file, missing amount column
- [x] Write fixture `tests/fixtures/sample_ledger.csv` aligned to sample_bank.csv
- [x] Add tests for this agent

### Done when
- Agent parses sample_ledger.csv and returns a clean list of LedgerEntry dicts in state
- Column mapping via DeepSeek works on a misnamed-column test file
- Tests pass

---

## Phase 4 — Agent 3: Reconciliation Engine
**Target:** Week 2
**Status: DONE**

### Tasks
- [x] Write `src/matching/exact_match.py` — exact match strategy
- [x] Write `src/matching/fuzzy_match.py` — fuzzy match using `rapidfuzz.fuzz.token_sort_ratio`
- [x] Write `src/matching/exceptions.py` — exception generation logic
- [x] Write `src/agents/reconciliation_engine.py` combining all strategies
- [x] Implement the 5 matching strategies in priority order:
  1. EXACT: amount + date + reference
  2. AMOUNT_DATE: amount + date within 1 day
  3. AMOUNT_REFERENCE: amount + reference substring
  4. AMOUNT_FUZZY: amount + description fuzzy above 80%
  5. AMOUNT_ONLY: amount + date within 3 days
- [x] Mark matched transactions and entries in state (set `matched=True`, `match_id`)
- [x] After matching, generate exceptions for all unmatched items:
  - BANK_ONLY, LEDGER_ONLY, LOW_CONFIDENCE, HIGH_VALUE (above RM5,000)
- [x] Update stats in state: `matched_count`, `unmatched_count`
- [x] Write matching tests in `tests/test_matching.py`
  - Exact match on identical records
  - Fuzzy match above threshold
  - Fuzzy match below threshold
  - High value unmatched detection
  - Duplicate detection

### Done when
- Engine correctly matches all matchable pairs in sample data
- Exceptions list is accurate
- Tests pass with no false matches

---

## Phase 5 — Agent 4: Exception Investigator
**Target:** Week 2
**Status: DONE**

### Tasks
- [x] Write `src/agents/exception_investigator.py`
- [x] Set up DeepSeek client using `openai` library with `base_url=https://api.deepseek.com`
- [x] Build the investigation prompt from `INVESTIGATION_PROMPT` template (see PRD section 4.4)
- [x] Call DeepSeek per exception with `response_format={"type": "json_object"}` and `temperature=0.1`
- [x] Parse JSON response and populate `investigation` and `resolution` fields on each exception
- [x] Set severity based on DeepSeek `risk_level` response
- [x] Add context to each call: other unmatched items on the same date
- [x] Add fallback: if DeepSeek call fails, log error and continue with empty investigation field
- [x] Add test: mock DeepSeek response and verify exception fields are populated

### Done when
- Each exception gets an `investigation` and `resolution` string from DeepSeek
- Agent does not crash if one DeepSeek call fails
- Test passes with mocked DeepSeek response

---

## Phase 6 — Agent 5: Report Writer
**Target:** Week 3

### Tasks
- [ ] Write `src/reports/excel_report.py`
- [ ] Create Excel workbook with 7 sheets:
  - Summary: KPIs, stats, period, bank file name
  - Matched: all matched pairs with confidence and match type
  - Exceptions: all exceptions with investigation and recommended action
  - Bank Only: unmatched bank transactions
  - Ledger Only: unmatched ledger entries
  - All Transactions: full bank transaction list
  - All Ledger: full ledger entry list
- [ ] Write `src/agents/report_writer.py`
- [ ] Call DeepSeek to generate a 3 to 4 sentence narrative summary using `SUMMARY_PROMPT` (see PRD section 4.5)
- [ ] Save Excel report to `data/reports/` with filename `recon_{session_id}_{date}.xlsx`
- [ ] Update state with `report_path` and `summary`
- [ ] Save session results to SQLite `recon_sessions` table
- [ ] Add test: verify Excel file opens and has all 7 sheets populated

### Done when
- Excel report is generated cleanly with all sheets
- Summary is a coherent 3 to 4 sentence paragraph
- File is saved to `data/reports/`

---

## Phase 7 — LangGraph Pipeline Wiring
**Target:** Week 3

### Tasks
- [ ] Write `src/graph/pipeline.py` — define and compile the LangGraph StateGraph
- [ ] Wire nodes in order: document_ingestion, ledger_sync, reconciliation_engine, exception_investigator (parallel), report_writer
- [ ] Write `src/graph/router.py` — conditional edges for error states (if status is FAILED, skip to end)
- [ ] Set up parallel execution for Agent 4 using LangGraph's map-reduce or Send API
- [ ] Write `main.py` as a CLI entry point — accepts `--bank`, `--ledger`, `--start`, `--end` args
- [ ] Write `src/utils/logger.py` using `loguru` — log each agent start, finish, and any errors
- [ ] End-to-end test: run pipeline on sample fixtures, verify report is generated

### Done when
- `python main.py --bank sample_bank.csv --ledger sample_ledger.csv --start 2026-03-01 --end 2026-03-31` runs to completion
- Report is generated in `data/reports/`
- Errors in one agent do not crash the whole pipeline

---

## Phase 8 — Telegram Bot Interface
**Target:** Week 3 to 4

### Tasks
- [ ] Write `bot.py` as the entry point
- [ ] Implement commands: `/start`, `/reconcile`, `/status`, `/history`, `/report [id]`, `/help`
- [ ] Handle `/reconcile` flow:
  - Prompt for bank statement CSV upload
  - Accept file, save to `data/uploads/`
  - Prompt for ledger CSV upload
  - Accept file, save to `data/uploads/`
  - Run LangGraph pipeline
  - Send progress updates per agent (1/5, 2/5, etc.)
  - Send final summary message with match rate and exception count
  - Send Excel report file
- [ ] Implement `/history` — query `recon_sessions` table, return last 5 sessions as a message
- [ ] Implement `/report [id]` — fetch report file from `data/reports/` and send as document
- [ ] Add error messages for bad file uploads (wrong format, empty file)

### Done when
- Full Telegram flow works from `/reconcile` to report delivery
- All commands respond correctly
- Bot handles a bad CSV gracefully without crashing

---

## Phase 9 — Streamlit UI
**Target:** Week 4

### Tasks
- [ ] Write `app.py` as the Streamlit entry point with page routing
- [ ] Write `ui/pages/home.py` — file uploaders for bank and ledger CSV, period selector, run button
- [ ] Write `ui/pages/progress.py` — live agent progress tracker, one status line per agent
- [ ] Write `ui/pages/results.py` — match summary stats, exception count, match rate chart
- [ ] Write `ui/pages/exceptions.py` — table of exceptions with investigation notes, severity badge
- [ ] Write `ui/pages/report.py` — download button for Excel report, display narrative summary
- [ ] Write `ui/pages/history.py` — table of past sessions from SQLite, click to drill into results
- [ ] Connect all pages to the same LangGraph pipeline via `st.session_state`

### Done when
- Full Streamlit flow works from file upload to report download
- Progress page updates as each agent completes
- History page loads past sessions from SQLite

---

## Phase 10 — Testing, Sample Data, README
**Target:** Week 4 to 5

### Tasks
- [ ] Expand `tests/fixtures/sample_bank.csv` to 50 transactions with a mix of matched, unmatched, duplicates, and high-value items
- [ ] Expand `tests/fixtures/sample_ledger.csv` accordingly
- [ ] Write full test coverage in `tests/test_agents.py` and `tests/test_matching.py` covering all cases from PRD section 10
- [ ] Write `README.md` with:
  - Project summary
  - How to install (clone, venv, pip install)
  - How to configure `.env`
  - How to run CLI, Telegram bot, and Streamlit
  - Sample output screenshots
- [ ] Final end-to-end run on sample data, verify all success criteria from PRD section 12
- [ ] Clean up any debug prints, unused imports, and leftover TODO comments

### Done when
- All tests pass
- README lets a new developer run the project with zero questions
- Pipeline meets the success criteria: above 85% exact match rate on clean data, full run under 60 seconds, Excel report clean