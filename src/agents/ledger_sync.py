# Agent 2 — Ledger Sync
# Reads the internal ledger CSV, normalises it to the LedgerEntry schema,
# and returns a list of entries in state.
# If column names don't match expected headers, DeepSeek is asked to map them.

import os
import hashlib
import json
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

from src.utils.normaliser import clean_amount, parse_date, looks_like_amount_column
from src.utils.validators import check_fields_present, check_file_path

load_dotenv()

deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Expected columns in a standard ledger CSV
EXPECTED_COLUMNS = ["date", "description", "reference", "amount", "type", "account_code", "counterparty"]


def ledger_sync_agent(state: dict) -> dict:
    # Validate required state fields before doing any work
    errors = check_fields_present(state, ["ledger_file_path", "period_start", "period_end"], "ledger_sync")
    file_error = check_file_path(state.get("ledger_file_path"), "ledger_sync")
    if file_error:
        errors.append(file_error)

    if errors:
        return {**state, "errors": state.get("errors", []) + errors, "status": "FAILED"}

    ledger_file = state["ledger_file_path"]

    if not os.path.exists(ledger_file):
        return {
            **state,
            "errors": state.get("errors", []) + [f"ledger_sync: file not found: {ledger_file}"],
            "status": "FAILED",
        }

    try:
        df = pd.read_csv(ledger_file)
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"ledger_sync: could not read CSV: {e}"],
            "status": "FAILED",
        }

    if df.empty:
        return {
            **state,
            "errors": state.get("errors", []) + ["ledger_sync: ledger CSV is empty"],
            "status": "FAILED",
        }

    # Try to map columns to expected roles
    column_map = detect_ledger_columns(df)

    # If amount column is still missing, ask DeepSeek
    if not column_map.get("amount") and not (column_map.get("debit") or column_map.get("credit")):
        column_map = ask_deepseek_for_column_map(df)

    if not column_map.get("date"):
        return {
            **state,
            "errors": state.get("errors", []) + ["ledger_sync: could not identify a date column"],
            "status": "FAILED",
        }

    if not column_map.get("amount") and not (column_map.get("debit") or column_map.get("credit")):
        return {
            **state,
            "errors": state.get("errors", []) + ["ledger_sync: could not identify an amount column"],
            "status": "FAILED",
        }

    entries = build_ledger_entries(df, column_map, state["period_start"], state["period_end"])

    return {
        **state,
        "ledger_entries": entries,
        "total_ledger": len(entries),
    }


def detect_ledger_columns(df):
    # Maps CSV column names to known ledger roles based on common naming patterns.
    column_map = {}
    columns = df.columns.tolist()

    for col in columns:
        col_lower = col.lower().strip()

        if not column_map.get("date"):
            if any(keyword in col_lower for keyword in ["date", "txn date", "transaction date", "posting date", "gl date"]):
                column_map["date"] = col

        if not column_map.get("description"):
            if any(keyword in col_lower for keyword in ["description", "narration", "particulars", "details", "memo"]):
                column_map["description"] = col

        if not column_map.get("reference"):
            if any(keyword in col_lower for keyword in ["ref", "reference", "document", "doc no", "voucher"]):
                column_map["reference"] = col

        if not column_map.get("amount"):
            if any(keyword in col_lower for keyword in ["amount", "amt", "value"]):
                if looks_like_amount_column(df[col]):
                    column_map["amount"] = col

        # Some ledgers have separate debit and credit columns
        if not column_map.get("debit"):
            if any(keyword in col_lower for keyword in ["debit", "dr"]):
                if looks_like_amount_column(df[col]):
                    column_map["debit"] = col

        if not column_map.get("credit"):
            if any(keyword in col_lower for keyword in ["credit", "cr"]):
                if looks_like_amount_column(df[col]):
                    column_map["credit"] = col

        if not column_map.get("entry_type"):
            if any(keyword in col_lower for keyword in ["type", "entry type", "dr/cr", "dc"]):
                column_map["entry_type"] = col

        if not column_map.get("account_code"):
            if any(keyword in col_lower for keyword in ["account", "acc", "account code", "gl code"]):
                column_map["account_code"] = col

        if not column_map.get("counterparty"):
            if any(keyword in col_lower for keyword in ["counterparty", "vendor", "customer", "payee", "party"]):
                column_map["counterparty"] = col

    # Fall back to longest text column for description if not found
    if not column_map.get("description"):
        text_cols = [c for c in columns if c not in column_map.values() and df[c].dtype == object]
        if text_cols:
            avg_lengths = {c: df[c].dropna().astype(str).str.len().mean() for c in text_cols}
            column_map["description"] = max(avg_lengths, key=avg_lengths.get)

    return column_map


def ask_deepseek_for_column_map(df):
    # Sends the first 5 rows to DeepSeek and asks it to map columns to ledger roles.
    preview = df.head(5).to_csv(index=False)
    columns = df.columns.tolist()

    prompt = f"""You are helping parse an accounting ledger CSV file.

Here are the column headers and the first 5 rows:

{preview}

Map each column to one of these roles: date, description, reference, amount, debit, credit, entry_type, account_code, counterparty.
Not all roles need to be filled. Only include roles you are confident about.

Respond in this exact JSON format:
{{
    "date": "column name or null",
    "description": "column name or null",
    "reference": "column name or null",
    "amount": "column name or null",
    "debit": "column name or null",
    "credit": "column name or null",
    "entry_type": "column name or null",
    "account_code": "column name or null",
    "counterparty": "column name or null"
}}

Only use column names from this list: {columns}
"""

    try:
        response = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        result = json.loads(response.choices[0].message.content)
        return {role: col for role, col in result.items() if col and col in df.columns.tolist()}
    except Exception:
        return {}


def build_ledger_entries(df, column_map, period_start, period_end):
    # Iterates through rows and builds a clean list of LedgerEntry dicts.
    # Skips rows with unparseable dates. Deduplicates by content hash.
    entries = []
    seen_hashes = set()

    date_col = column_map.get("date")
    desc_col = column_map.get("description")
    ref_col = column_map.get("reference")
    amount_col = column_map.get("amount")
    debit_col = column_map.get("debit")
    credit_col = column_map.get("credit")
    type_col = column_map.get("entry_type")

    for _, row in df.iterrows():
        raw_date = row.get(date_col) if date_col else None
        date_str = parse_date(raw_date)
        if date_str is None:
            continue

        if date_str < period_start or date_str > period_end:
            continue

        description = str(row.get(desc_col, "")).strip() if desc_col else ""
        reference = str(row.get(ref_col, "")).strip() if ref_col else None

        # Determine amount and entry type
        if debit_col and credit_col:
            debit_val = clean_amount(row.get(debit_col, 0))
            credit_val = clean_amount(row.get(credit_col, 0))
            if credit_val > 0:
                amount = credit_val
                entry_type = "credit"
            else:
                amount = debit_val
                entry_type = "debit"
        elif amount_col:
            amount = clean_amount(row.get(amount_col, 0))
            # Use the type column if available, otherwise infer from sign
            if type_col:
                raw_type = str(row.get(type_col, "")).strip().lower()
                if raw_type in ("cr", "credit", "c"):
                    entry_type = "credit"
                elif raw_type in ("dr", "debit", "d"):
                    entry_type = "debit"
                else:
                    entry_type = "credit" if amount >= 0 else "debit"
            else:
                entry_type = "credit" if amount >= 0 else "debit"
            amount = abs(amount)
        else:
            amount = 0.0
            entry_type = "unknown"

        hash_input = f"{date_str}|{amount}|{description}|{entry_type}".encode()
        entry_id = hashlib.md5(hash_input).hexdigest()[:12]

        if entry_id in seen_hashes:
            continue
        seen_hashes.add(entry_id)

        entries.append({
            "id": entry_id,
            "date": date_str,
            "description": description,
            "reference": reference if reference else None,
            "amount": amount,
            "entry_type": entry_type,
            "matched": False,
            "match_id": None,
        })

    return entries
