# Exact and near-exact matching strategies.
# These run first before fuzzy matching because they are the most reliable.
# Each function takes one bank transaction and one ledger entry and returns
# True if they match under that strategy's rules.

from datetime import date, timedelta


def same_amount(txn, entry):
    # Returns True if the amounts are within 1 cent of each other.
    tolerance = 0.01
    return abs(abs(txn["amount"]) - abs(entry["amount"])) <= tolerance


def same_date(txn, entry):
    # Returns True if both items fall on the exact same date.
    return txn["date"] == entry["date"]


def date_within_days(txn, entry, days):
    # Returns True if the two dates are within N calendar days of each other.
    try:
        txn_date = date.fromisoformat(txn["date"])
        entry_date = date.fromisoformat(entry["date"])
        return abs((txn_date - entry_date).days) <= days
    except (ValueError, TypeError):
        return False


def same_reference(txn, entry):
    # Returns True if both items have a reference and one contains the other as a substring.
    txn_ref = (txn.get("reference") or "").strip().lower()
    entry_ref = (entry.get("reference") or "").strip().lower()

    if not txn_ref or not entry_ref:
        return False

    return txn_ref in entry_ref or entry_ref in txn_ref


def is_exact_match(txn, entry):
    # Strategy 1 — EXACT: same amount + same date + same reference.
    return same_amount(txn, entry) and same_date(txn, entry) and same_reference(txn, entry)


def is_amount_date_match(txn, entry):
    # Strategy 2 — AMOUNT_DATE: same amount + date within 1 day.
    return same_amount(txn, entry) and date_within_days(txn, entry, 1)


def is_amount_reference_match(txn, entry):
    # Strategy 3 — AMOUNT_REFERENCE: same amount + reference substring match.
    return same_amount(txn, entry) and same_reference(txn, entry)


def is_amount_only_match(txn, entry):
    # Strategy 5 — AMOUNT_ONLY: same amount + date within 3 days.
    return same_amount(txn, entry) and date_within_days(txn, entry, 3)
