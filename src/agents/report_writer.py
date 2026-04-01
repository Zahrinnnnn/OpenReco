# Agent 5 — Report Writer
# Takes the fully reconciled state and does two things:
# 1. Calls DeepSeek to generate a 3-4 sentence management narrative summary.
# 2. Builds an Excel report with 7 sheets and saves it to data/reports/.
# Also saves the session results to SQLite so the history page can show past runs.

import os
import json
import logging
from datetime import date

from openai import OpenAI
from dotenv import load_dotenv

from src.reports.excel_report import build_excel_report
from src.database.queries import insert_session, insert_matches, insert_exceptions

load_dotenv()

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
REPORT_DIR = os.getenv("REPORT_DIR", "data/reports")

SUMMARY_PROMPT = """
You are a finance reporting assistant. Write a concise reconciliation summary
based on these results:

Period: {period_start} to {period_end}
Total Bank Transactions: {total_bank}
Total Ledger Entries: {total_ledger}
Matched: {matched_count} ({match_rate}%)
Exceptions: {exception_count}
High Risk Exceptions: {high_risk_count}
Total Unmatched Amount: RM {unmatched_amount}

Write 3 to 4 sentences suitable for a management report.
Be factual, professional, and flag any concerns clearly.
"""


def report_writer_agent(state: dict) -> dict:
    # Generates the narrative summary and Excel report, then saves everything to the database.

    exceptions = state.get("exceptions", [])
    total_bank = state.get("total_bank", 0)
    matched_count = state.get("matched_count", 0)

    match_rate = round((matched_count / total_bank * 100), 1) if total_bank > 0 else 0.0
    exception_count = len(exceptions)
    high_risk_count = sum(1 for e in exceptions if e.get("severity") == "High")

    unmatched_bank = [
        t for t in state.get("bank_transactions", [])
        if not t.get("matched")
    ]
    unmatched_amount = sum(abs(t.get("amount", 0)) for t in unmatched_bank)

    summary = generate_summary(
        state=state,
        match_rate=match_rate,
        exception_count=exception_count,
        high_risk_count=high_risk_count,
        unmatched_amount=unmatched_amount,
    )

    session_id = state.get("session_id")
    report_path = build_report_path(session_id)

    try:
        build_excel_report(state, report_path)
        logger.info("report_writer: saved report to %s", report_path)
    except Exception as error:
        logger.error("report_writer: failed to build Excel report — %s", str(error))
        report_path = None

    # Save everything to SQLite
    try:
        save_to_database(state, session_id, report_path, summary, match_rate, exception_count)
    except Exception as error:
        logger.error("report_writer: failed to save to database — %s", str(error))

    return {
        **state,
        "report_path": report_path,
        "summary": summary,
        "status": "DONE",
    }


def generate_summary(state, match_rate, exception_count, high_risk_count, unmatched_amount):
    # Calls DeepSeek to write the narrative summary.
    # Falls back to a plain text summary if the API call fails.

    if not DEEPSEEK_API_KEY:
        logger.warning("report_writer: DEEPSEEK_API_KEY not set, using plain text summary")
        return build_plain_summary(state, match_rate, exception_count, high_risk_count, unmatched_amount)

    prompt = SUMMARY_PROMPT.format(
        period_start=state.get("period_start", ""),
        period_end=state.get("period_end", ""),
        total_bank=state.get("total_bank", 0),
        total_ledger=state.get("total_ledger", 0),
        matched_count=state.get("matched_count", 0),
        match_rate=match_rate,
        exception_count=exception_count,
        high_risk_count=high_risk_count,
        unmatched_amount=f"{unmatched_amount:,.2f}",
    )

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()

    except Exception as error:
        logger.error("report_writer: DeepSeek summary call failed — %s", str(error))
        return build_plain_summary(state, match_rate, exception_count, high_risk_count, unmatched_amount)


def build_plain_summary(state, match_rate, exception_count, high_risk_count, unmatched_amount):
    # A simple fallback summary used when DeepSeek is unavailable.
    period = f"{state.get('period_start', '')} to {state.get('period_end', '')}"
    matched = state.get("matched_count", 0)
    total = state.get("total_bank", 0)

    summary = (
        f"Reconciliation for {period} completed with a {match_rate}% match rate "
        f"({matched} of {total} bank transactions matched). "
        f"{exception_count} exception(s) were identified, "
        f"of which {high_risk_count} are high risk. "
        f"Total unmatched amount is RM {unmatched_amount:,.2f}."
    )
    return summary


def build_report_path(session_id) -> str:
    # Builds the file path for the Excel report using session ID and today's date.
    today = date.today().strftime("%Y%m%d")
    filename = f"recon_{session_id}_{today}.xlsx" if session_id else f"recon_{today}.xlsx"
    return os.path.join(REPORT_DIR, filename)


def save_to_database(state, session_id, report_path, summary, match_rate, exception_count):
    # Writes the session record, matches, and exceptions to SQLite.
    if session_id is None:
        return

    insert_session(
        session_id=session_id,
        period_start=state.get("period_start", ""),
        period_end=state.get("period_end", ""),
        bank_file=state.get("bank_file_path", ""),
        ledger_file=state.get("ledger_file_path", ""),
        status="DONE",
        total_bank=state.get("total_bank", 0),
        total_ledger=state.get("total_ledger", 0),
        matched_count=state.get("matched_count", 0),
        exception_count=exception_count,
        report_path=report_path or "",
        summary=summary,
    )

    insert_matches(session_id, state.get("matches", []))
    insert_exceptions(session_id, state.get("exceptions", []))
