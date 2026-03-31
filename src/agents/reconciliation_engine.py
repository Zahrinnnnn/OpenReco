# Agent 3 — Reconciliation Engine
# Takes the parsed bank transactions and ledger entries from state,
# runs 5 matching strategies in priority order, marks matched items,
# then generates exceptions for everything that didn't match.

import uuid

from src.matching.exact_match import (
    is_exact_match,
    is_amount_date_match,
    is_amount_reference_match,
    is_amount_only_match,
)
from src.matching.fuzzy_match import is_fuzzy_match
from src.matching.exceptions import generate_exceptions
from src.utils.validators import check_fields_present

# Each strategy is tried in order. The first one that matches wins.
# Confidence scores come from the PRD spec.
STRATEGIES = [
    {
        "name": "EXACT",
        "confidence": 1.0,
        "check": lambda txn, entry: (is_exact_match(txn, entry), 1.0),
    },
    {
        "name": "AMOUNT_DATE",
        "confidence": 0.95,
        "check": lambda txn, entry: (is_amount_date_match(txn, entry), 0.95),
    },
    {
        "name": "AMOUNT_REFERENCE",
        "confidence": 0.90,
        "check": lambda txn, entry: (is_amount_reference_match(txn, entry), 0.90),
    },
    {
        "name": "AMOUNT_FUZZY",
        "confidence": 0.75,
        "check": lambda txn, entry: is_fuzzy_match(txn, entry),
    },
    {
        "name": "AMOUNT_ONLY",
        "confidence": 0.60,
        "check": lambda txn, entry: (is_amount_only_match(txn, entry), 0.60),
    },
]


def reconciliation_engine_agent(state: dict) -> dict:
    # Validate that agents 1 and 2 produced data before running
    errors = check_fields_present(state, ["bank_transactions", "ledger_entries"], "reconciliation_engine")
    if errors:
        return {**state, "errors": state.get("errors", []) + errors, "status": "FAILED"}

    bank_transactions = state["bank_transactions"]
    ledger_entries = state["ledger_entries"]

    if not bank_transactions:
        return {
            **state,
            "errors": state.get("errors", []) + ["reconciliation_engine: no bank transactions to match"],
            "status": "FAILED",
        }

    # Run the matching pass
    matches, updated_bank, updated_ledger = run_matching(bank_transactions, ledger_entries)

    # Generate exceptions for everything left unmatched
    exceptions = generate_exceptions(updated_bank, updated_ledger, matches)

    matched_count = len(matches)
    unmatched_count = len(updated_bank) + len(updated_ledger) - (matched_count * 2)
    # More precise: count items that are still unmatched
    unmatched_bank = sum(1 for t in updated_bank if not t["matched"])
    unmatched_ledger = sum(1 for e in updated_ledger if not e["matched"])

    return {
        **state,
        "bank_transactions": updated_bank,
        "ledger_entries": updated_ledger,
        "matches": matches,
        "exceptions": exceptions,
        "matched_count": matched_count,
        "unmatched_count": unmatched_bank + unmatched_ledger,
        "total_bank": len(updated_bank),
        "total_ledger": len(updated_ledger),
    }


def run_matching(bank_transactions, ledger_entries):
    # Makes copies so we don't mutate the original state lists.
    # Works through each strategy in order and stops trying a pair once it's matched.

    bank = [dict(txn) for txn in bank_transactions]
    ledger = [dict(entry) for entry in ledger_entries]
    matches = []

    # Build an index of unmatched ledger entries for faster lookup
    unmatched_ledger = {entry["id"]: entry for entry in ledger if not entry["matched"]}

    for txn in bank:
        if txn["matched"]:
            continue

        best_match = find_best_match(txn, list(unmatched_ledger.values()))

        if best_match is None:
            continue

        matched_entry, strategy_name, confidence = best_match
        match_id = uuid.uuid4().hex[:12]

        # Mark both items as matched
        txn["matched"] = True
        txn["match_id"] = match_id
        txn["confidence"] = confidence

        matched_entry["matched"] = True
        matched_entry["match_id"] = match_id

        # Remove from unmatched pool so it cannot be matched again
        unmatched_ledger.pop(matched_entry["id"])

        matches.append({
            "match_id": match_id,
            "bank_txn_id": txn["id"],
            "ledger_entry_id": matched_entry["id"],
            "match_type": strategy_name,
            "confidence": confidence,
            "reasoning": build_reasoning(txn, matched_entry, strategy_name, confidence),
        })

    return matches, bank, ledger


def find_best_match(txn, unmatched_entries):
    # Tries each strategy against all unmatched ledger entries.
    # Returns the first (and best, given priority order) match found.
    for strategy in STRATEGIES:
        for entry in unmatched_entries:
            matched, confidence = strategy["check"](txn, entry)
            if matched:
                return entry, strategy["name"], confidence

    return None


def build_reasoning(txn, entry, strategy_name, confidence):
    # Builds a short human-readable string explaining why two items were matched.
    return (
        f"Matched via {strategy_name} strategy with {confidence:.0%} confidence. "
        f"Bank: '{txn['description']}' {txn['date']} RM{abs(txn['amount']):.2f} | "
        f"Ledger: '{entry['description']}' {entry['date']} RM{abs(entry['amount']):.2f}"
    )
