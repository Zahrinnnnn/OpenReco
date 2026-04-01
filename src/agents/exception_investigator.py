# Agent 4 — Exception Investigator
# Takes every unresolved exception from Agent 3 and sends it to DeepSeek
# for analysis. DeepSeek reasons about the likely cause, recommends an action,
# and rates the risk. Results are written back into each exception dict.
# If a DeepSeek call fails for any reason, the exception is kept with an empty
# investigation field so the run can continue and the report still generates.

import os
import json
import logging

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# The prompt sent to DeepSeek for each exception.
# Curly-brace fields are filled in by .format() before the call.
INVESTIGATION_PROMPT = """
You are a senior finance officer performing bank reconciliation.

You have an unmatched item that needs investigation:

EXCEPTION TYPE: {exception_type}
AMOUNT: RM {amount}
DATE: {date}
DESCRIPTION: {description}
REFERENCE: {reference}

CONTEXT - Other unmatched items on the same date:
{context_items}

Based on your accounting knowledge:
1. What is the most likely reason this item is unmatched?
2. What should the finance officer check to resolve this?
3. What is the risk level if this remains unresolved? (Low/Medium/High)

Respond in this exact JSON format:
{{
    "likely_reason": "...",
    "recommended_action": "...",
    "risk_level": "Low|Medium|High",
    "suggested_match": "transaction_id or null"
}}
"""

# Map DeepSeek risk levels to our internal severity labels
RISK_TO_SEVERITY = {
    "Low": "Low",
    "Medium": "Medium",
    "High": "High",
}


def exception_investigator_agent(state: dict) -> dict:
    # Loops over all exceptions and investigates each one with a DeepSeek call.
    # Skips the agent gracefully if there are no exceptions to investigate.

    exceptions = state.get("exceptions", [])

    if not exceptions:
        logger.info("exception_investigator: no exceptions to investigate, skipping")
        return state

    if not DEEPSEEK_API_KEY:
        logger.warning("exception_investigator: DEEPSEEK_API_KEY not set, skipping investigation")
        return state

    client = build_deepseek_client()

    # Build a lookup of all exceptions grouped by date so we can add context
    # to each investigation call (what else was unmatched on the same day)
    exceptions_by_date = build_exceptions_by_date(exceptions)

    investigated = []
    for exception in exceptions:
        enriched = investigate_one_exception(client, exception, exceptions_by_date)
        investigated.append(enriched)

    return {**state, "exceptions": investigated}


def build_deepseek_client():
    # Creates and returns the OpenAI-compatible client pointed at DeepSeek.
    return OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )


def build_exceptions_by_date(exceptions: list) -> dict:
    # Groups exceptions by date so we can include same-day context in the prompt.
    by_date = {}
    for exc in exceptions:
        date = exc.get("date", "unknown")
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(exc)
    return by_date


def build_context_text(exception: dict, exceptions_by_date: dict) -> str:
    # Returns a short text summary of all OTHER unmatched items on the same date.
    # This gives DeepSeek useful context without sending the full exception list.
    date = exception.get("date", "unknown")
    same_day = exceptions_by_date.get(date, [])

    other_items = [
        exc for exc in same_day
        if exc["exception_id"] != exception["exception_id"]
    ]

    if not other_items:
        return "None"

    lines = []
    for item in other_items:
        lines.append(
            f"- {item['type']} | {item['description']} | RM{abs(item['amount']):.2f} | source: {item['item_source']}"
        )

    return "\n".join(lines)


def investigate_one_exception(client: OpenAI, exception: dict, exceptions_by_date: dict) -> dict:
    # Calls DeepSeek for a single exception and writes the results back.
    # Returns the exception unchanged if the call fails for any reason.
    context_text = build_context_text(exception, exceptions_by_date)

    prompt = INVESTIGATION_PROMPT.format(
        exception_type=exception.get("type", "UNKNOWN"),
        amount=f"{abs(exception.get('amount', 0)):.2f}",
        date=exception.get("date", "unknown"),
        description=exception.get("description", "no description"),
        reference=exception.get("reference", "none"),
        context_items=context_text,
    )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        raw_json = response.choices[0].message.content
        result = json.loads(raw_json)

        return enrich_exception(exception, result)

    except json.JSONDecodeError as error:
        logger.error(
            "exception_investigator: could not parse DeepSeek response for %s — %s",
            exception["exception_id"],
            str(error),
        )
        return exception

    except Exception as error:
        logger.error(
            "exception_investigator: DeepSeek call failed for %s — %s",
            exception["exception_id"],
            str(error),
        )
        return exception


def enrich_exception(exception: dict, deepseek_result: dict) -> dict:
    # Writes the DeepSeek findings back into the exception dict.
    # Also updates severity based on the risk level DeepSeek reported.

    likely_reason = deepseek_result.get("likely_reason", "")
    recommended_action = deepseek_result.get("recommended_action", "")
    risk_level = deepseek_result.get("risk_level", "")
    suggested_match = deepseek_result.get("suggested_match", None)

    enriched = dict(exception)
    enriched["investigation"] = likely_reason
    enriched["resolution"] = recommended_action
    enriched["suggested_match"] = suggested_match

    # Only override severity if DeepSeek returned a valid risk level
    if risk_level in RISK_TO_SEVERITY:
        enriched["severity"] = RISK_TO_SEVERITY[risk_level]

    return enriched
