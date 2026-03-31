# Fuzzy description matching using rapidfuzz.
# Strategy 4 — AMOUNT_FUZZY: same amount + description similarity above threshold.
# Token sort ratio is used so word order differences don't cause false misses.
# Example: "GRAB PAYMENT MAR" vs "MAR GRAB PAYMENT" still scores ~100.

import os
from rapidfuzz import fuzz
from dotenv import load_dotenv

load_dotenv()

# Threshold is configurable via .env, defaults to 0.80 (80%)
FUZZY_THRESHOLD = float(os.getenv("FUZZY_THRESHOLD", "0.80"))


def fuzzy_score(text_a, text_b):
    # Returns a similarity score between 0.0 and 1.0 for two strings.
    # Uses token_sort_ratio so word order does not matter.
    if not text_a or not text_b:
        return 0.0

    score = fuzz.token_sort_ratio(text_a.lower().strip(), text_b.lower().strip())
    return score / 100.0


def is_fuzzy_match(txn, entry, threshold=None):
    # Strategy 4 — AMOUNT_FUZZY: same amount + description similarity above threshold.
    # Returns (is_match, score) tuple so the caller can store the confidence level.
    from src.matching.exact_match import same_amount

    if threshold is None:
        threshold = FUZZY_THRESHOLD

    if not same_amount(txn, entry):
        return False, 0.0

    score = fuzzy_score(txn.get("description", ""), entry.get("description", ""))
    return score >= threshold, score
