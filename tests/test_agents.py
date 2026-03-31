# Tests for all agents.
# Run with: pytest tests/test_agents.py

import os
import pytest
import pandas as pd

from src.agents.document_ingestion import document_ingestion_agent, detect_columns, build_transactions
from src.agents.ledger_sync import ledger_sync_agent, detect_ledger_columns, build_ledger_entries

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_BANK = os.path.join(FIXTURES_DIR, "sample_bank.csv")


# --- document_ingestion_agent ---

def test_parses_sample_bank_csv():
    # Agent should parse sample_bank.csv and return a non-empty list of transactions
    state = {
        "bank_file_path": SAMPLE_BANK,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = document_ingestion_agent(state)

    assert result["status"] != "FAILED", f"Agent failed with errors: {result['errors']}"
    assert len(result["bank_transactions"]) > 0


def test_transaction_has_required_fields():
    # Each transaction dict should have all required keys
    state = {
        "bank_file_path": SAMPLE_BANK,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = document_ingestion_agent(state)
    required_keys = ["id", "date", "description", "reference", "debit", "credit", "amount", "matched", "match_id", "confidence"]

    for txn in result["bank_transactions"]:
        for key in required_keys:
            assert key in txn, f"Transaction missing key: {key}"


def test_dates_are_normalised():
    # All dates in returned transactions should be in YYYY-MM-DD format
    state = {
        "bank_file_path": SAMPLE_BANK,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = document_ingestion_agent(state)

    for txn in result["bank_transactions"]:
        date = txn["date"]
        assert len(date) == 10, f"Date not in YYYY-MM-DD format: {date}"
        assert date[4] == "-" and date[7] == "-"


def test_filters_to_period():
    # Transactions outside the period should not appear
    state = {
        "bank_file_path": SAMPLE_BANK,
        "period_start": "2026-03-10",
        "period_end": "2026-03-15",
        "errors": [],
        "status": "RUNNING",
    }
    result = document_ingestion_agent(state)

    for txn in result["bank_transactions"]:
        assert txn["date"] >= "2026-03-10"
        assert txn["date"] <= "2026-03-15"


def test_fails_gracefully_on_missing_file():
    # Agent should set status FAILED and add an error, not raise an exception
    state = {
        "bank_file_path": "data/uploads/does_not_exist.csv",
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = document_ingestion_agent(state)

    assert result["status"] == "FAILED"
    assert len(result["errors"]) > 0


def test_fails_gracefully_on_missing_state_fields():
    # Agent should fail if bank_file_path is not in state
    state = {
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = document_ingestion_agent(state)

    assert result["status"] == "FAILED"
    assert any("bank_file_path" in err for err in result["errors"])


def test_deduplication():
    # If the CSV has duplicate rows, only one should appear in output
    duplicate_csv = os.path.join(FIXTURES_DIR, "duplicate_bank.csv")
    pd.DataFrame([
        {"Date": "2026-03-01", "Description": "GRAB PAYMENT", "Reference": "GRB001", "Debit": 45.60, "Credit": 0.00},
        {"Date": "2026-03-01", "Description": "GRAB PAYMENT", "Reference": "GRB001", "Debit": 45.60, "Credit": 0.00},
    ]).to_csv(duplicate_csv, index=False)

    state = {
        "bank_file_path": duplicate_csv,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = document_ingestion_agent(state)

    assert len(result["bank_transactions"]) == 1


# --- detect_columns ---

def test_detects_standard_columns():
    # Standard column names should be detected without needing DeepSeek
    df = pd.DataFrame({
        "Date": ["2026-03-01"],
        "Description": ["GRAB PAYMENT"],
        "Reference": ["GRB001"],
        "Debit": [45.60],
        "Credit": [0.00],
    })
    column_map = detect_columns(df)

    assert column_map.get("date") == "Date"
    assert column_map.get("description") == "Description"
    assert column_map.get("debit") == "Debit"
    assert column_map.get("credit") == "Credit"


# --- build_transactions ---

def test_skips_rows_with_bad_dates():
    # Rows where the date cannot be parsed should be silently skipped
    df = pd.DataFrame({
        "Date": ["2026-03-01", "not-a-date", "2026-03-03"],
        "Description": ["A", "B", "C"],
        "Reference": ["R1", "R2", "R3"],
        "Debit": [10.0, 20.0, 30.0],
        "Credit": [0.0, 0.0, 0.0],
    })
    column_map = {"date": "Date", "description": "Description", "reference": "Reference", "debit": "Debit", "credit": "Credit"}
    transactions = build_transactions(df, column_map, "2026-03-01", "2026-03-31")

    assert len(transactions) == 2
    dates = [t["date"] for t in transactions]
    assert "2026-03-01" in dates
    assert "2026-03-03" in dates


# --- ledger_sync_agent ---

SAMPLE_LEDGER = os.path.join(FIXTURES_DIR, "sample_ledger.csv")


def test_parses_sample_ledger_csv():
    # Agent should parse sample_ledger.csv and return a non-empty list of entries
    state = {
        "ledger_file_path": SAMPLE_LEDGER,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = ledger_sync_agent(state)

    assert result["status"] != "FAILED", f"Agent failed with errors: {result['errors']}"
    assert len(result["ledger_entries"]) > 0


def test_ledger_entry_has_required_fields():
    # Each ledger entry dict should have all required keys
    state = {
        "ledger_file_path": SAMPLE_LEDGER,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = ledger_sync_agent(state)
    required_keys = ["id", "date", "description", "reference", "amount", "entry_type", "matched", "match_id"]

    for entry in result["ledger_entries"]:
        for key in required_keys:
            assert key in entry, f"Ledger entry missing key: {key}"


def test_ledger_entry_type_is_valid():
    # entry_type should be either debit or credit
    state = {
        "ledger_file_path": SAMPLE_LEDGER,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = ledger_sync_agent(state)

    for entry in result["ledger_entries"]:
        assert entry["entry_type"] in ("debit", "credit"), f"Unexpected entry_type: {entry['entry_type']}"


def test_ledger_filters_to_period():
    # Entries outside the period should not appear
    state = {
        "ledger_file_path": SAMPLE_LEDGER,
        "period_start": "2026-03-10",
        "period_end": "2026-03-15",
        "errors": [],
        "status": "RUNNING",
    }
    result = ledger_sync_agent(state)

    for entry in result["ledger_entries"]:
        assert entry["date"] >= "2026-03-10"
        assert entry["date"] <= "2026-03-15"


def test_ledger_fails_gracefully_on_missing_file():
    # Agent should set status FAILED and add an error, not raise an exception
    state = {
        "ledger_file_path": "data/uploads/does_not_exist.csv",
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = ledger_sync_agent(state)

    assert result["status"] == "FAILED"
    assert len(result["errors"]) > 0


def test_ledger_fails_gracefully_on_missing_state_fields():
    # Agent should fail if ledger_file_path is not in state
    state = {
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = ledger_sync_agent(state)

    assert result["status"] == "FAILED"
    assert any("ledger_file_path" in err for err in result["errors"])


def test_ledger_deduplication():
    # Duplicate rows in the ledger CSV should only appear once
    duplicate_csv = os.path.join(FIXTURES_DIR, "duplicate_ledger.csv")
    pd.DataFrame([
        {"Date": "2026-03-01", "Description": "GRAB PAYMENT", "Reference": "GRB001", "Amount": 45.60, "Type": "debit"},
        {"Date": "2026-03-01", "Description": "GRAB PAYMENT", "Reference": "GRB001", "Amount": 45.60, "Type": "debit"},
    ]).to_csv(duplicate_csv, index=False)

    state = {
        "ledger_file_path": duplicate_csv,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "errors": [],
        "status": "RUNNING",
    }
    result = ledger_sync_agent(state)

    assert len(result["ledger_entries"]) == 1


# --- detect_ledger_columns ---

def test_detects_standard_ledger_columns():
    # Standard ledger column names should be detected without needing DeepSeek
    df = pd.DataFrame({
        "Date": ["2026-03-01"],
        "Description": ["GRAB PAYMENT"],
        "Reference": ["GRB001"],
        "Amount": [45.60],
        "Type": ["debit"],
    })
    column_map = detect_ledger_columns(df)

    assert column_map.get("date") == "Date"
    assert column_map.get("description") == "Description"
    assert column_map.get("amount") == "Amount"


# --- build_ledger_entries ---

def test_ledger_skips_rows_with_bad_dates():
    # Rows where the date cannot be parsed should be silently skipped
    df = pd.DataFrame({
        "Date": ["2026-03-01", "not-a-date", "2026-03-03"],
        "Description": ["A", "B", "C"],
        "Amount": [100.0, 200.0, 300.0],
        "Type": ["debit", "credit", "debit"],
    })
    column_map = {"date": "Date", "description": "Description", "amount": "Amount", "entry_type": "Type"}
    entries = build_ledger_entries(df, column_map, "2026-03-01", "2026-03-31")

    assert len(entries) == 2
    dates = [e["date"] for e in entries]
    assert "2026-03-01" in dates
    assert "2026-03-03" in dates
