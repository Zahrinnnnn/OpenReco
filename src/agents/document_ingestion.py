# Agent 1 — Document Ingestion
# Reads a bank statement CSV, figures out which columns are dates/amounts/descriptions,
# cleans and normalises everything, then returns a list of Transaction dicts in state.
# If column detection is ambiguous, it asks DeepSeek to infer the mapping.

import os
import hashlib
import json
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

from src.utils.normaliser import (
    clean_amount,
    parse_date,
    looks_like_date_column,
    looks_like_amount_column,
    handle_dr_cr_suffix,
)
from src.utils.validators import check_fields_present, check_file_path

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def document_ingestion_agent(state: dict) -> dict:
    # Validate required state fields before doing any work
    errors = check_fields_present(state, ["bank_file_path", "period_start", "period_end"], "document_ingestion")
    file_error = check_file_path(state.get("bank_file_path"), "document_ingestion")
    if file_error:
        errors.append(file_error)

    if errors:
        return {**state, "errors": state.get("errors", []) + errors, "status": "FAILED"}

    bank_file = state["bank_file_path"]

    # Check the file actually exists on disk
    if not os.path.exists(bank_file):
        return {
            **state,
            "errors": state.get("errors", []) + [f"document_ingestion: file not found: {bank_file}"],
            "status": "FAILED",
        }

    try:
        df = pd.read_csv(bank_file)
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"document_ingestion: could not read CSV: {e}"],
            "status": "FAILED",
        }

    if df.empty:
        return {
            **state,
            "errors": state.get("errors", []) + ["document_ingestion: bank statement CSV is empty"],
            "status": "FAILED",
        }

    # Try to detect column mapping automatically
    column_map = detect_columns(df)

    # If auto-detection failed for required columns, ask DeepSeek
    if not column_map.get("date") or not column_map.get("amount") and not (column_map.get("debit") or column_map.get("credit")):
        column_map = ask_deepseek_for_column_map(df)

    # If still missing required columns, fail
    if not column_map.get("date"):
        return {
            **state,
            "errors": state.get("errors", []) + ["document_ingestion: could not identify a date column"],
            "status": "FAILED",
        }

    transactions = build_transactions(df, column_map, state["period_start"], state["period_end"])

    return {
        **state,
        "bank_transactions": transactions,
        "total_bank": len(transactions),
    }


def detect_columns(df):
    # Goes through each column and tries to classify it by its contents.
    # Returns a dict like: {"date": "Txn Date", "description": "Narration", "debit": "Debit", ...}
    column_map = {}
    columns = df.columns.tolist()

    for col in columns:
        col_lower = col.lower().strip()

        # Date column detection
        if not column_map.get("date"):
            if any(keyword in col_lower for keyword in ["date", "txn date", "transaction date", "value date", "posting date"]):
                column_map["date"] = col
            elif looks_like_date_column(df[col]):
                column_map["date"] = col

        # Reference column detection
        if not column_map.get("reference"):
            if any(keyword in col_lower for keyword in ["ref", "reference", "cheque", "chq", "transaction id", "txn id"]):
                column_map["reference"] = col

        # Debit column detection
        if not column_map.get("debit"):
            if any(keyword in col_lower for keyword in ["debit", "dr", "withdrawal", "out"]):
                if looks_like_amount_column(df[col]):
                    column_map["debit"] = col

        # Credit column detection
        if not column_map.get("credit"):
            if any(keyword in col_lower for keyword in ["credit", "cr", "deposit", "in"]):
                if looks_like_amount_column(df[col]):
                    column_map["credit"] = col

        # Single amount column detection
        if not column_map.get("amount"):
            if any(keyword in col_lower for keyword in ["amount", "amt"]):
                if looks_like_amount_column(df[col]):
                    column_map["amount"] = col

    # Description: pick the longest text column if not already found
    if not column_map.get("description"):
        text_columns = [
            col for col in columns
            if col not in column_map.values() and df[col].dtype == object
        ]
        if text_columns:
            # The column with the highest average string length is most likely the description
            avg_lengths = {col: df[col].dropna().astype(str).str.len().mean() for col in text_columns}
            column_map["description"] = max(avg_lengths, key=avg_lengths.get)

    return column_map


def ask_deepseek_for_column_map(df):
    # Sends the first 5 rows and column names to DeepSeek and asks it to identify the columns.
    # Falls back to an empty dict if the call fails or no API key is set.
    if not DEEPSEEK_API_KEY:
        return {}

    preview = df.head(5).to_csv(index=False)
    columns = df.columns.tolist()

    prompt = f"""You are helping parse a bank statement CSV file.

Here are the column headers and the first 5 rows:

{preview}

Map each column to one of these roles: date, description, reference, debit, credit, amount.
Not all roles need to be filled. Only include roles you are confident about.

Respond in this exact JSON format:
{{
    "date": "column name or null",
    "description": "column name or null",
    "reference": "column name or null",
    "debit": "column name or null",
    "credit": "column name or null",
    "amount": "column name or null"
}}

Only use column names from this list: {columns}
"""

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        result = json.loads(response.choices[0].message.content)

        # Filter out null values so the map only has real column names
        return {role: col for role, col in result.items() if col and col in df.columns.tolist()}
    except Exception:
        return {}


def build_transactions(df, column_map, period_start, period_end):
    # Iterates through rows and builds a clean list of Transaction dicts.
    # Skips rows with unparseable dates. Deduplicates by content hash.
    transactions = []
    seen_hashes = set()

    date_col = column_map.get("date")
    desc_col = column_map.get("description")
    ref_col = column_map.get("reference")
    debit_col = column_map.get("debit")
    credit_col = column_map.get("credit")
    amount_col = column_map.get("amount")

    for _, row in df.iterrows():
        # Parse date and skip unparseable rows
        raw_date = row.get(date_col) if date_col else None
        date_str = parse_date(raw_date)
        if date_str is None:
            continue

        # Filter to reconciliation period
        if date_str < period_start or date_str > period_end:
            continue

        description = str(row.get(desc_col, "")).strip() if desc_col else ""
        reference = str(row.get(ref_col, "")).strip() if ref_col else None

        # Work out debit and credit amounts
        if debit_col and credit_col:
            # Bank has separate debit and credit columns
            debit = clean_amount(row.get(debit_col, 0))
            credit = clean_amount(row.get(credit_col, 0))
            amount = credit - debit if credit > 0 else -debit
        elif amount_col:
            # Single amount column, possibly with Dr/Cr suffix
            raw_amount = str(row.get(amount_col, "0"))
            if any(suffix in raw_amount.upper() for suffix in ["DR", "CR", " D", " C"]):
                amount_val, is_credit = handle_dr_cr_suffix(raw_amount)
                debit = 0.0 if is_credit else amount_val
                credit = amount_val if is_credit else 0.0
                amount = credit - debit
            else:
                amount = clean_amount(raw_amount)
                debit = abs(amount) if amount < 0 else 0.0
                credit = amount if amount > 0 else 0.0
        else:
            debit = 0.0
            credit = 0.0
            amount = 0.0

        # Generate a unique ID by hashing date + amount + description
        hash_input = f"{date_str}|{amount}|{description}".encode()
        txn_id = hashlib.md5(hash_input).hexdigest()[:12]

        # Skip duplicates
        if txn_id in seen_hashes:
            continue
        seen_hashes.add(txn_id)

        transactions.append({
            "id": txn_id,
            "date": date_str,
            "description": description,
            "reference": reference if reference else None,
            "debit": debit,
            "credit": credit,
            "amount": amount,
            "matched": False,
            "match_id": None,
            "confidence": None,
        })

    return transactions
