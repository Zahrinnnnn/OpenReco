# OpenReco

Autonomous bank reconciliation assistant. Upload a bank statement CSV and a ledger CSV — OpenReco matches them, investigates exceptions using DeepSeek, and delivers a full Excel report.

Works as a CLI tool, a Telegram bot, or a Streamlit web app.

---

## How it works

Five agents run in sequence via LangGraph:

1. **Document Ingestion** — parses and normalises the bank statement CSV
2. **Ledger Sync** — parses and normalises the ledger CSV
3. **Reconciliation Engine** — matches transactions using 5 strategies (exact, amount+date, amount+reference, fuzzy, amount-only)
4. **Exception Investigator** — DeepSeek reasons about each unmatched item
5. **Report Writer** — generates a 7-sheet Excel report and a narrative summary

---

## Install

```bash
git clone https://github.com/Zahrinnnnn/OpenReco.git
cd OpenReco

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Configure

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and set:

```env
DEEPSEEK_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_token_here
```

Everything else has sensible defaults and can be left as-is.

Get a free DeepSeek API key at https://platform.deepseek.com

---

## Run

### CLI

```bash
python main.py \
  --bank data/uploads/bank.csv \
  --ledger data/uploads/ledger.csv \
  --start 2026-03-01 \
  --end 2026-03-31
```

The Excel report is saved to `data/reports/`.

### Streamlit

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser. Upload your CSV files, pick a period, and click Run.

### Telegram bot

```bash
python bot.py
```

Then open your bot in Telegram and send `/reconcile`.

---

## CSV format

OpenReco auto-detects column names so your CSV does not need exact headers. It looks for date-like, amount-like, and description-like columns automatically. If it cannot detect them it calls DeepSeek to infer the mapping.

**Bank statement** — needs at minimum a date, a description, and either separate debit/credit columns or a single amount column.

**Ledger** — needs at minimum a date, a description, and an amount.

Sample files are in `tests/fixtures/`.

---

## Matching strategies

Strategies run in priority order. The first match wins.

| Priority | Strategy | Confidence | Rule |
|---|---|---|---|
| 1 | EXACT | 100% | Same amount + same date + reference match |
| 2 | AMOUNT_DATE | 95% | Same amount + date within 1 day |
| 3 | AMOUNT_REFERENCE | 90% | Same amount + reference substring match |
| 4 | AMOUNT_FUZZY | 75% | Same amount + description similarity above 80% |
| 5 | AMOUNT_ONLY | 60% | Same amount + date within 3 days |

---

## Exception types

| Type | Meaning |
|---|---|
| BANK_ONLY | Bank transaction with no matching ledger entry |
| LEDGER_ONLY | Ledger entry with no matching bank transaction |
| LOW_CONFIDENCE | Matched pair with confidence below 75% |
| HIGH_VALUE | Unmatched item above RM 5,000 |

---

## Run tests

```bash
pytest tests/ -v
```

---

## Project structure

```
OpenReco/
├── main.py               # CLI entry point
├── bot.py                # Telegram bot
├── app.py                # Streamlit entry point
├── requirements.txt
├── .env.example
├── src/
│   ├── agents/           # The 5 pipeline agents
│   ├── graph/            # LangGraph pipeline + state
│   ├── matching/         # Matching strategies + exception logic
│   ├── reports/          # Excel report builder
│   ├── database/         # SQLite connection + queries
│   └── utils/            # Logger, normaliser, validators
├── tests/
│   ├── test_agents.py
│   ├── test_matching.py
│   └── fixtures/         # Sample CSV files
└── ui/
    └── pages/            # Streamlit pages
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | Required for exception investigation and report summary |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API endpoint |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Model name |
| `TELEGRAM_BOT_TOKEN` | — | Required only for Telegram bot |
| `DB_PATH` | `data/database.db` | SQLite database file |
| `UPLOAD_DIR` | `data/uploads` | Where uploaded CSVs are saved |
| `REPORT_DIR` | `data/reports` | Where Excel reports are saved |
| `HIGH_VALUE_THRESHOLD` | `5000` | Amount above which unmatched items are HIGH_VALUE |
| `FUZZY_THRESHOLD` | `0.80` | Minimum similarity score for fuzzy matching (0.0 to 1.0) |
| `DATE_TOLERANCE_DAYS` | `3` | Max days apart for AMOUNT_ONLY strategy |
| `AMOUNT_TOLERANCE` | `0.01` | Max amount difference to still count as same (RM) |

---

## Cost estimate

Each full reconciliation run costs under USD 0.05 on DeepSeek's pricing.

- Agent 4 sends one call per exception (~USD 0.001 each)
- Agent 5 sends one call for the narrative summary (~USD 0.002)
