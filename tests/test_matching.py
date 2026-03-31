# Tests for all matching strategies and exception generation.
# Run with: pytest tests/test_matching.py

import pytest

from src.matching.exact_match import (
    is_exact_match,
    is_amount_date_match,
    is_amount_reference_match,
    is_amount_only_match,
    same_amount,
    date_within_days,
)
from src.matching.fuzzy_match import fuzzy_score, is_fuzzy_match
from src.matching.exceptions import generate_exceptions
from src.agents.reconciliation_engine import reconciliation_engine_agent, run_matching


# --- Helper builders ---

def make_txn(id="t1", date="2026-03-10", description="GRAB PAYMENT", reference="GRB001", amount=45.60):
    return {
        "id": id,
        "date": date,
        "description": description,
        "reference": reference,
        "debit": amount if amount > 0 else 0.0,
        "credit": 0.0,
        "amount": amount,
        "matched": False,
        "match_id": None,
        "confidence": None,
    }


def make_entry(id="e1", date="2026-03-10", description="Grab ride payment", reference="GRB001", amount=45.60, entry_type="debit"):
    return {
        "id": id,
        "date": date,
        "description": description,
        "reference": reference,
        "amount": amount,
        "entry_type": entry_type,
        "matched": False,
        "match_id": None,
    }


# --- same_amount ---

def test_same_amount_exact():
    txn = make_txn(amount=45.60)
    entry = make_entry(amount=45.60)
    assert same_amount(txn, entry) is True


def test_same_amount_within_tolerance():
    txn = make_txn(amount=45.60)
    entry = make_entry(amount=45.605)
    assert same_amount(txn, entry) is True


def test_same_amount_fails_when_different():
    txn = make_txn(amount=45.60)
    entry = make_entry(amount=50.00)
    assert same_amount(txn, entry) is False


# --- date_within_days ---

def test_date_within_days_same_day():
    txn = make_txn(date="2026-03-10")
    entry = make_entry(date="2026-03-10")
    assert date_within_days(txn, entry, 1) is True


def test_date_within_days_one_day_apart():
    txn = make_txn(date="2026-03-10")
    entry = make_entry(date="2026-03-11")
    assert date_within_days(txn, entry, 1) is True


def test_date_within_days_too_far():
    txn = make_txn(date="2026-03-10")
    entry = make_entry(date="2026-03-15")
    assert date_within_days(txn, entry, 1) is False


# --- is_exact_match ---

def test_exact_match_succeeds():
    txn = make_txn(date="2026-03-10", amount=45.60, reference="GRB001")
    entry = make_entry(date="2026-03-10", amount=45.60, reference="GRB001")
    assert is_exact_match(txn, entry) is True


def test_exact_match_fails_without_reference():
    txn = make_txn(date="2026-03-10", amount=45.60, reference=None)
    entry = make_entry(date="2026-03-10", amount=45.60, reference=None)
    assert is_exact_match(txn, entry) is False


def test_exact_match_fails_wrong_date():
    txn = make_txn(date="2026-03-10", amount=45.60, reference="GRB001")
    entry = make_entry(date="2026-03-12", amount=45.60, reference="GRB001")
    assert is_exact_match(txn, entry) is False


# --- is_amount_date_match ---

def test_amount_date_match_same_day():
    txn = make_txn(date="2026-03-10", amount=45.60)
    entry = make_entry(date="2026-03-10", amount=45.60)
    assert is_amount_date_match(txn, entry) is True


def test_amount_date_match_one_day_apart():
    txn = make_txn(date="2026-03-10", amount=45.60)
    entry = make_entry(date="2026-03-11", amount=45.60)
    assert is_amount_date_match(txn, entry) is True


def test_amount_date_match_fails_two_days():
    txn = make_txn(date="2026-03-10", amount=45.60)
    entry = make_entry(date="2026-03-12", amount=45.60)
    assert is_amount_date_match(txn, entry) is False


# --- is_amount_reference_match ---

def test_amount_reference_match_succeeds():
    txn = make_txn(amount=45.60, reference="GRB001")
    entry = make_entry(amount=45.60, reference="GRB001")
    assert is_amount_reference_match(txn, entry) is True


def test_amount_reference_match_partial_reference():
    txn = make_txn(amount=45.60, reference="GRB001")
    entry = make_entry(amount=45.60, reference="REF-GRB001-MARCH")
    assert is_amount_reference_match(txn, entry) is True


def test_amount_reference_match_fails_no_reference():
    txn = make_txn(amount=45.60, reference=None)
    entry = make_entry(amount=45.60, reference=None)
    assert is_amount_reference_match(txn, entry) is False


# --- fuzzy matching ---

def test_fuzzy_score_identical():
    assert fuzzy_score("GRAB PAYMENT", "GRAB PAYMENT") == 1.0


def test_fuzzy_score_word_order():
    # Token sort ratio should handle reordered words
    score = fuzzy_score("GRAB PAYMENT MARCH", "MARCH GRAB PAYMENT")
    assert score >= 0.95


def test_fuzzy_score_dissimilar():
    score = fuzzy_score("GRAB PAYMENT", "TNB ELECTRICITY BILL")
    assert score < 0.5


def test_is_fuzzy_match_above_threshold():
    txn = make_txn(amount=45.60, description="GRAB PAYMENT")
    entry = make_entry(amount=45.60, description="Grab ride payment")
    matched, score = is_fuzzy_match(txn, entry, threshold=0.50)
    assert matched is True
    assert score >= 0.50


def test_is_fuzzy_match_below_threshold():
    txn = make_txn(amount=45.60, description="GRAB PAYMENT")
    entry = make_entry(amount=45.60, description="TNB ELECTRICITY BILL")
    matched, score = is_fuzzy_match(txn, entry, threshold=0.80)
    assert matched is False


def test_is_fuzzy_match_fails_different_amount():
    txn = make_txn(amount=45.60, description="GRAB PAYMENT")
    entry = make_entry(amount=99.00, description="GRAB PAYMENT")
    matched, score = is_fuzzy_match(txn, entry)
    assert matched is False


# --- generate_exceptions ---

def test_unmatched_bank_generates_bank_only_exception():
    txn = make_txn(id="t1", amount=45.60)
    exceptions = generate_exceptions([txn], [], [])
    assert len(exceptions) == 1
    assert exceptions[0]["type"] == "BANK_ONLY"
    assert exceptions[0]["item_id"] == "t1"


def test_unmatched_ledger_generates_ledger_only_exception():
    entry = make_entry(id="e1", amount=45.60)
    exceptions = generate_exceptions([], [entry], [])
    assert len(exceptions) == 1
    assert exceptions[0]["type"] == "LEDGER_ONLY"
    assert exceptions[0]["item_id"] == "e1"


def test_high_value_unmatched_gets_high_value_exception():
    txn = make_txn(id="t1", amount=8500.00)
    exceptions = generate_exceptions([txn], [], [])
    assert exceptions[0]["type"] == "HIGH_VALUE"
    assert exceptions[0]["severity"] == "High"


def test_matched_items_produce_no_exception():
    txn = make_txn(id="t1", amount=45.60)
    entry = make_entry(id="e1", amount=45.60)
    match = {
        "match_id": "m1",
        "bank_txn_id": "t1",
        "ledger_entry_id": "e1",
        "match_type": "EXACT",
        "confidence": 1.0,
        "reasoning": "exact match",
    }
    exceptions = generate_exceptions([txn], [entry], [match])
    # No unmatched items, no low confidence, so no exceptions
    assert len(exceptions) == 0


def test_low_confidence_match_generates_exception():
    txn = make_txn(id="t1", amount=45.60)
    entry = make_entry(id="e1", amount=45.60)
    match = {
        "match_id": "m1",
        "bank_txn_id": "t1",
        "ledger_entry_id": "e1",
        "match_type": "AMOUNT_ONLY",
        "confidence": 0.60,
        "reasoning": "amount only match",
    }
    exceptions = generate_exceptions([txn], [entry], [match])
    low_conf = [e for e in exceptions if e["type"] == "LOW_CONFIDENCE"]
    assert len(low_conf) == 1


# --- reconciliation_engine_agent ---

def test_engine_matches_identical_records():
    # A bank transaction and ledger entry with same amount, date, and reference should match
    txn = make_txn(id="t1", date="2026-03-10", amount=45.60, reference="GRB001")
    entry = make_entry(id="e1", date="2026-03-10", amount=45.60, reference="GRB001")

    state = {
        "bank_transactions": [txn],
        "ledger_entries": [entry],
        "matches": [],
        "exceptions": [],
        "errors": [],
        "status": "RUNNING",
    }
    result = reconciliation_engine_agent(state)

    assert len(result["matches"]) == 1
    assert result["matched_count"] == 1


def test_engine_produces_exception_for_unmatched():
    # A bank transaction with no matching ledger entry should produce an exception
    txn = make_txn(id="t1", date="2026-03-10", amount=45.60, reference="GRB001")

    state = {
        "bank_transactions": [txn],
        "ledger_entries": [],
        "matches": [],
        "exceptions": [],
        "errors": [],
        "status": "RUNNING",
    }
    result = reconciliation_engine_agent(state)

    assert len(result["matches"]) == 0
    assert len(result["exceptions"]) == 1
    assert result["exceptions"][0]["type"] == "BANK_ONLY"


def test_engine_flags_high_value_unmatched():
    # An unmatched transaction above RM5000 should be flagged as HIGH_VALUE
    txn = make_txn(id="t1", amount=8500.00)

    state = {
        "bank_transactions": [txn],
        "ledger_entries": [],
        "matches": [],
        "exceptions": [],
        "errors": [],
        "status": "RUNNING",
    }
    result = reconciliation_engine_agent(state)

    assert result["exceptions"][0]["type"] == "HIGH_VALUE"
    assert result["exceptions"][0]["severity"] == "High"


def test_engine_does_not_match_same_entry_twice():
    # One ledger entry should not be matched to two different bank transactions
    txn1 = make_txn(id="t1", date="2026-03-10", amount=45.60, reference="GRB001")
    txn2 = make_txn(id="t2", date="2026-03-10", amount=45.60, reference="GRB001")
    entry = make_entry(id="e1", date="2026-03-10", amount=45.60, reference="GRB001")

    state = {
        "bank_transactions": [txn1, txn2],
        "ledger_entries": [entry],
        "matches": [],
        "exceptions": [],
        "errors": [],
        "status": "RUNNING",
    }
    result = reconciliation_engine_agent(state)

    assert len(result["matches"]) == 1
    assert result["unmatched_count"] >= 1


def test_engine_fails_without_bank_transactions():
    state = {
        "bank_transactions": [],
        "ledger_entries": [],
        "matches": [],
        "exceptions": [],
        "errors": [],
        "status": "RUNNING",
    }
    result = reconciliation_engine_agent(state)
    assert result["status"] == "FAILED"
