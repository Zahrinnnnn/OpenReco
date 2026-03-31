# Tests for all agents.
# Run with: pytest tests/test_agents.py

import os
import pytest
import pandas as pd

from src.agents.document_ingestion import document_ingestion_agent, detect_columns, build_transactions

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
