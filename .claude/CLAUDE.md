# CLAUDE.md — OpenReco

## Build Status

| Phase | Description | Status |
|---|---|---|
| 1 | Project Foundation | Done |
| 2 | Agent 1: Document Ingestion | Done |
| 3 | Agent 2: Ledger Sync | Done |
| 4 | Agent 3: Reconciliation Engine | Done |
| 5 | Agent 4: Exception Investigator | Done |
| 6 | Agent 5: Report Writer | Not started |
| 7 | LangGraph Pipeline Wiring | Not started |
| 8 | Telegram Bot Interface | Not started |
| 9 | Streamlit UI | Not started |
| 10 | Testing, Sample Data, README | Not started |

**Current phase:** 6

---

## Project Overview

OpenReco is a multi-agent autonomous bank reconciliation assistant. Users upload a bank statement CSV and a ledger CSV via Telegram or a Streamlit web UI. A LangGraph pipeline of 5 agents parses, normalises, matches, investigates exceptions, and returns a complete reconciliation report — all without manual steps.

LLM backbone: DeepSeek (via OpenAI-compatible API). Free tier wherever possible.

---

## Rules

### Code Style
- Write human readable code. Variable names, function names, and comments should be clear enough that a junior developer can follow without explanation.
- Avoid clever one-liners. Prefer explicit, step-by-step logic.
- Add a comment at the top of each agent file describing what that agent does in plain English.
- No em dashes in code comments, docstrings, or any generated text.

### Git and Commits
- Commit and push to https://github.com/Zahrinnnnn/OpenReco.git on behalf of Zahrinnnnn (zahrin16@proton.me).
- Write commit messages like a normal human — short, lowercase, no bullet points, no AI-style summaries. Example: "add fuzzy matching logic" not "feat: implement fuzzy string matching algorithm".
- No "Co-Authored-By" or AI attribution lines in commit messages.

---

## Architecture

### Pipeline (LangGraph)
5 agents run in sequence, with Agent 4 capable of parallel execution:

1. **Document Ingestion** — parse bank statement CSV, normalise to Transaction schema
2. **Ledger Sync** — parse ledger CSV, normalise to LedgerEntry schema
3. **Reconciliation Engine** — match bank transactions to ledger entries using 5 strategies in priority order
4. **Exception Investigator** — DeepSeek reasons about each unmatched item (runs in parallel)
5. **Report Writer** — compile Excel report and plain-language summary via DeepSeek

### State
Defined in `src/graph/state.py` as `RecoState` TypedDict. Key fields: `bank_transactions`, `ledger_entries`, `matches`, `exceptions`, `status`, `errors`.

### Matching Strategies (priority order)
1. EXACT: same amount + same date + same reference (confidence 1.0)
2. AMOUNT_DATE: same amount + date within 1 day (0.95)
3. AMOUNT_REFERENCE: same amount + reference substring match (0.90)
4. AMOUNT_FUZZY: same amount + description fuzzy similarity above 80% (0.75)
5. AMOUNT_ONLY: same amount + date within 3 days (0.60)

Fuzzy matching uses `rapidfuzz.fuzz.token_sort_ratio`.

### Exception Types
- BANK_ONLY: unmatched bank transaction
- LEDGER_ONLY: unmatched ledger entry
- LOW_CONFIDENCE: match confidence below 0.75
- HIGH_VALUE: unmatched amount above RM5,000

---

## Project Structure

```
openreco/
├── main.py
├── bot.py
├── app.py
├── requirements.txt
├── .env
├── data/
│   ├── database.db
│   ├── uploads/
│   └── reports/
├── src/
│   ├── agents/
│   │   ├── document_ingestion.py
│   │   ├── ledger_sync.py
│   │   ├── reconciliation_engine.py
│   │   ├── exception_investigator.py
│   │   └── report_writer.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── pipeline.py
│   │   └── router.py
│   ├── database/
│   │   ├── connection.py
│   │   └── queries.py
│   ├── matching/
│   │   ├── exact_match.py
│   │   ├── fuzzy_match.py
│   │   └── exceptions.py
│   ├── reports/
│   │   └── excel_report.py
│   └── utils/
│       ├── normaliser.py
│       ├── validators.py
│       └── logger.py
├── tests/
│   ├── test_agents.py
│   ├── test_matching.py
│   └── fixtures/
│       ├── sample_bank.csv
│       └── sample_ledger.csv
└── ui/
    └── pages/
        ├── home.py
        ├── progress.py
        ├── results.py
        ├── exceptions.py
        ├── report.py
        └── history.py
```

---

## Key Dependencies

- `langgraph`, `langchain`, `langchain-openai`, `openai` — pipeline and LLM calls
- `pandas`, `rapidfuzz`, `python-dateutil` — data processing and fuzzy matching
- `openpyxl`, `xlsxwriter` — Excel report generation
- `python-telegram-bot` — Telegram interface
- `streamlit` — web UI
- `loguru` — logging
- `python-dotenv` — environment variable loading

---

## Environment Variables

```
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
TELEGRAM_BOT_TOKEN=
DB_PATH=data/database.db
UPLOAD_DIR=data/uploads
REPORT_DIR=data/reports
HIGH_VALUE_THRESHOLD=5000
FUZZY_THRESHOLD=0.80
DATE_TOLERANCE_DAYS=3
AMOUNT_TOLERANCE=0.01
```

Never commit `.env`.

---

## Interfaces

### Telegram
Commands: `/start`, `/reconcile`, `/status`, `/history`, `/report [id]`, `/help`

Flow: user uploads bank CSV, then ledger CSV. Bot runs pipeline, sends progress updates per agent, then delivers the Excel report with a narrative summary.

### Streamlit Pages
Home, Progress, Results, Exceptions, Report, History.

---

## Database (SQLite)

Tables: `recon_sessions`, `matches`, `exceptions`, `audit_log`.

Schema is defined in the PRD section 5. Keep it simple — no ORM, just raw sqlite3 queries in `src/database/queries.py`.

---

## DeepSeek Usage

Agent 4 sends one LLM call per exception. Agent 5 sends one call for the narrative summary. Use `response_format={"type": "json_object"}` for Agent 4. Keep temperature at 0.1 for determinism. Estimated cost per full run is under USD 0.05.

---

## Out of Scope (do not build)

- PDF parsing
- Live bank API connections
- Multi-currency support
- External accounting software integration
- Scheduled auto-runs
- Multi-user authentication
