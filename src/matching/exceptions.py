# Exception generation logic.
# After matching is complete, this runs over all unmatched items
# and assigns each one an exception type and severity.

import os
import uuid
from dotenv import load_dotenv

load_dotenv()

HIGH_VALUE_THRESHOLD = float(os.getenv("HIGH_VALUE_THRESHOLD", "5000"))


def generate_exceptions(bank_transactions, ledger_entries, matches):
    # Looks at all unmatched bank transactions and ledger entries and creates exception records.
    # Also flags any matched pair with confidence below 0.75 as LOW_CONFIDENCE.

    exceptions = []

    # Build sets of matched IDs for quick lookup
    matched_bank_ids = {m["bank_txn_id"] for m in matches}
    matched_ledger_ids = {m["ledger_entry_id"] for m in matches}

    # Bank transactions with no matching ledger entry
    for txn in bank_transactions:
        if txn["id"] in matched_bank_ids:
            continue

        exception_type = "BANK_ONLY"
        severity = determine_severity(txn["amount"], exception_type)

        # High value unmatched items get their own type for visibility
        if abs(txn["amount"]) >= HIGH_VALUE_THRESHOLD:
            exception_type = "HIGH_VALUE"
            severity = "High"

        exceptions.append(build_exception(
            exception_type=exception_type,
            item_id=txn["id"],
            item_source="bank",
            amount=txn["amount"],
            description=txn["description"],
            severity=severity,
        ))

    # Ledger entries with no matching bank transaction
    for entry in ledger_entries:
        if entry["id"] in matched_ledger_ids:
            continue

        exception_type = "LEDGER_ONLY"
        severity = determine_severity(entry["amount"], exception_type)

        if abs(entry["amount"]) >= HIGH_VALUE_THRESHOLD:
            exception_type = "HIGH_VALUE"
            severity = "High"

        exceptions.append(build_exception(
            exception_type=exception_type,
            item_id=entry["id"],
            item_source="ledger",
            amount=entry["amount"],
            description=entry["description"],
            severity=severity,
        ))

    # Matched pairs with low confidence
    for match in matches:
        if match["confidence"] < 0.75:
            exceptions.append(build_exception(
                exception_type="LOW_CONFIDENCE",
                item_id=match["bank_txn_id"],
                item_source="bank",
                amount=0.0,
                description=f"Low confidence match: {match['reasoning']}",
                severity="Medium",
            ))

    return exceptions


def build_exception(exception_type, item_id, item_source, amount, description, severity):
    # Builds a single exception dict with a unique ID.
    return {
        "exception_id": uuid.uuid4().hex[:12],
        "type": exception_type,
        "item_id": item_id,
        "item_source": item_source,
        "amount": amount,
        "description": description,
        "investigation": None,
        "resolution": None,
        "severity": severity,
    }


def determine_severity(amount, exception_type):
    # Basic severity rules before DeepSeek investigation.
    # Agent 4 will refine these based on reasoning.
    abs_amount = abs(amount)

    if abs_amount >= HIGH_VALUE_THRESHOLD:
        return "High"
    elif abs_amount >= 1000:
        return "Medium"
    else:
        return "Low"
