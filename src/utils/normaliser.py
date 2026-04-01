# Shared utility functions for cleaning dates and amounts.
# Used by document_ingestion.py and ledger_sync.py to keep normalisation consistent.

import re
from dateutil import parser as dateutil_parser


def clean_amount(value):
    # Strips currency symbols, commas, and spaces then returns a float.
    # Examples: "RM 1,234.56" -> 1234.56 | "(500.00)" -> -500.00
    if value is None:
        return 0.0

    text = str(value).strip()

    # Parentheses mean negative in accounting notation: (500.00) -> -500.00
    is_negative = text.startswith("(") and text.endswith(")")

    # Remove everything that is not a digit or a decimal point
    cleaned = re.sub(r"[^\d.]", "", text)

    if cleaned == "" or cleaned == ".":
        return 0.0

    amount = float(cleaned)

    return -amount if is_negative else amount


def parse_date(value):
    # Tries to parse a date string into YYYY-MM-DD format.
    # Returns None if the value cannot be parsed.
    # ISO format (YYYY-MM-DD) is tried first so that dateutil's dayfirst flag
    # does not accidentally reorder the parts.
    if value is None:
        return None

    text = str(value).strip()

    if text == "" or text.lower() in ("nan", "none", "null"):
        return None

    # Try strict ISO format first to avoid dayfirst ambiguity on YYYY-MM-DD strings
    try:
        from datetime import datetime
        parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Fall back to dateutil for other formats (DD/MM/YYYY, "01 Mar 2026", etc.)
    try:
        parsed = dateutil_parser.parse(text, dayfirst=True)
        return parsed.strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None


def looks_like_date_column(series):
    # Returns True if more than half the non-null values in the series can be parsed as dates.
    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    parsed_count = sum(1 for val in non_null if parse_date(val) is not None)
    return (parsed_count / len(non_null)) > 0.5


def looks_like_amount_column(series):
    # Returns True if more than half the non-null values look like numeric amounts.
    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    def is_amount(val):
        cleaned = re.sub(r"[^\d.]", "", str(val).strip())
        if cleaned == "" or cleaned == ".":
            return False
        try:
            float(cleaned)
            return True
        except ValueError:
            return False

    valid_count = sum(1 for val in non_null if is_amount(val))
    return (valid_count / len(non_null)) > 0.5


def handle_dr_cr_suffix(value):
    # Some banks write amounts as "1234.56 Dr" or "500.00 Cr".
    # Returns (amount, is_credit) tuple.
    text = str(value).strip()
    is_credit = False

    if text.upper().endswith("CR") or text.upper().endswith("C"):
        is_credit = True
        text = text[:-2].strip() if text.upper().endswith("CR") else text[:-1].strip()
    elif text.upper().endswith("DR") or text.upper().endswith("D"):
        text = text[:-2].strip() if text.upper().endswith("DR") else text[:-1].strip()

    amount = clean_amount(text)
    return amount, is_credit
