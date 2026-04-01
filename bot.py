# Telegram bot entry point for OpenReco.
# Users interact through commands and file uploads. The bot guides them through
# the reconciliation flow: upload bank CSV, upload ledger CSV, pick a period,
# then the pipeline runs and the bot sends back the Excel report with a summary.
#
# Run with: python bot.py

import os
import logging
import asyncio
from datetime import datetime

from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

from src.database.connection import init_db
from src.database.queries import create_session, get_recent_sessions, get_session
from src.graph.pipeline import run_pipeline
from src.utils.logger import setup_logger

load_dotenv()
setup_logger()

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "data/uploads")

# Conversation states for the /reconcile flow
WAITING_FOR_BANK = 1
WAITING_FOR_LEDGER = 2
WAITING_FOR_PERIOD = 3


# --- Command handlers ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Sent when a user first opens the bot or types /start.
    await update.message.reply_text(
        "Welcome to OpenReco.\n\n"
        "I can reconcile your bank statement against your ledger automatically.\n\n"
        "Commands:\n"
        "/reconcile - start a new reconciliation\n"
        "/status    - check the current session\n"
        "/history   - view your last 5 sessions\n"
        "/report    - download a past report\n"
        "/help      - show this message"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Reports on the currently active session stored in user_data.
    session_id = context.user_data.get("session_id")
    if not session_id:
        await update.message.reply_text("No active session. Use /reconcile to start one.")
        return

    session = get_session(session_id)
    if not session:
        await update.message.reply_text("Session not found in database.")
        return

    status = session.get("status", "UNKNOWN")
    matched = session.get("matched_count", 0)
    total = session.get("total_bank", 0)
    exceptions = session.get("exception_count", 0)

    await update.message.reply_text(
        f"Session #{session_id}\n"
        f"Status: {status}\n"
        f"Matched: {matched} / {total}\n"
        f"Exceptions: {exceptions}"
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Shows the last 5 reconciliation sessions from SQLite.
    sessions = get_recent_sessions(limit=5)

    if not sessions:
        await update.message.reply_text("No past sessions found.")
        return

    lines = ["Your last reconciliation sessions:\n"]
    for s in sessions:
        match_rate = 0
        if s.get("total_bank"):
            match_rate = round((s.get("matched_count", 0) / s["total_bank"]) * 100, 1)
        lines.append(
            f"#{s['id']} | {s['period_start']} to {s['period_end']} | "
            f"{match_rate}% matched | {s['status']}"
        )

    await update.message.reply_text("\n".join(lines))


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Downloads the Excel report for a given session ID.
    # Usage: /report 42
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /report <session_id>  e.g. /report 42")
        return

    try:
        session_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Session ID must be a number.")
        return

    session = get_session(session_id)
    if not session:
        await update.message.reply_text(f"Session #{session_id} not found.")
        return

    report_path = session.get("report_path", "")
    if not report_path or not os.path.exists(report_path):
        await update.message.reply_text(
            f"Report file not found for session #{session_id}. "
            "It may still be generating or the file was deleted."
        )
        return

    await update.message.reply_text(f"Sending report for session #{session_id}...")
    with open(report_path, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=os.path.basename(report_path),
            caption=session.get("summary", ""),
        )


# --- /reconcile conversation flow ---

async def cmd_reconcile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Starts the reconciliation conversation and asks for the bank CSV.
    context.user_data.clear()
    await update.message.reply_text(
        "Starting a new reconciliation.\n\n"
        "Step 1 of 3: Please upload your bank statement CSV file."
    )
    return WAITING_FOR_BANK


async def receive_bank_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Receives the bank CSV, saves it to uploads/, moves to ledger step.
    document = update.message.document

    if not document or not document.file_name.endswith(".csv"):
        await update.message.reply_text("Please upload a CSV file.")
        return WAITING_FOR_BANK

    bank_path = await save_uploaded_file(document, context, prefix="bank")
    context.user_data["bank_file_path"] = bank_path

    await update.message.reply_text(
        f"Bank file received: {document.file_name}\n\n"
        "Step 2 of 3: Now upload your ledger CSV file."
    )
    return WAITING_FOR_LEDGER


async def receive_ledger_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Receives the ledger CSV, then asks for the reconciliation period.
    document = update.message.document

    if not document or not document.file_name.endswith(".csv"):
        await update.message.reply_text("Please upload a CSV file.")
        return WAITING_FOR_LEDGER

    ledger_path = await save_uploaded_file(document, context, prefix="ledger")
    context.user_data["ledger_file_path"] = ledger_path

    await update.message.reply_text(
        f"Ledger file received: {document.file_name}\n\n"
        "Step 3 of 3: Enter the reconciliation period.\n"
        "Format: YYYY-MM-DD YYYY-MM-DD\n"
        "Example: 2026-03-01 2026-03-31"
    )
    return WAITING_FOR_PERIOD


async def receive_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Parses the period input and runs the full pipeline.
    text = update.message.text.strip()
    parts = text.split()

    if len(parts) != 2:
        await update.message.reply_text(
            "Please enter two dates separated by a space.\n"
            "Example: 2026-03-01 2026-03-31"
        )
        return WAITING_FOR_PERIOD

    period_start, period_end = parts[0], parts[1]

    # Basic format validation
    try:
        datetime.strptime(period_start, "%Y-%m-%d")
        datetime.strptime(period_end, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text(
            "Invalid date format. Use YYYY-MM-DD.\n"
            "Example: 2026-03-01 2026-03-31"
        )
        return WAITING_FOR_PERIOD

    bank_file_path = context.user_data["bank_file_path"]
    ledger_file_path = context.user_data["ledger_file_path"]

    # Create a session record in SQLite before running the pipeline
    session_id = create_session(period_start, period_end, bank_file_path, ledger_file_path)
    context.user_data["session_id"] = session_id

    await update.message.reply_text(
        f"Running reconciliation for {period_start} to {period_end}...\n"
        "This may take 30 to 60 seconds."
    )

    # Send progress updates as each agent completes
    progress_msg = await update.message.reply_text("Agent 1/5: Parsing bank statement...")

    try:
        # Run the pipeline in a thread so it doesn't block the event loop
        final_state = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: run_pipeline(
                bank_file_path=bank_file_path,
                ledger_file_path=ledger_file_path,
                period_start=period_start,
                period_end=period_end,
                session_id=session_id,
            )
        )

        await progress_msg.edit_text("Agent 5/5: Report generated.")
        await send_results(update, context, final_state)

    except Exception as error:
        logger.error("bot: pipeline failed for session %s — %s", session_id, str(error))
        await update.message.reply_text(
            "Something went wrong during reconciliation. "
            f"Error: {str(error)}\n\n"
            "Please try again with /reconcile."
        )

    return ConversationHandler.END


async def cancel_reconcile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # User typed /cancel during the conversation flow.
    context.user_data.clear()
    await update.message.reply_text("Reconciliation cancelled. Use /reconcile to start again.")
    return ConversationHandler.END


# --- Helpers ---

async def save_uploaded_file(document: Document, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> str:
    # Downloads the uploaded file from Telegram and saves it to data/uploads/.
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file = await context.bot.get_file(document.file_id)
    filename = f"{prefix}_{document.file_name}"
    save_path = os.path.join(UPLOAD_DIR, filename)
    await file.download_to_drive(save_path)
    return save_path


async def send_results(update: Update, context: ContextTypes.DEFAULT_TYPE, state: dict) -> None:
    # Sends the reconciliation summary message and then the Excel report file.
    total = state.get("total_bank", 0)
    matched = state.get("matched_count", 0)
    exceptions = state.get("exceptions", [])
    exception_count = len(exceptions)
    high_risk = sum(1 for e in exceptions if e.get("severity") == "High")
    match_rate = round((matched / total * 100), 1) if total > 0 else 0.0

    unmatched_bank = [t for t in state.get("bank_transactions", []) if not t.get("matched")]
    unmatched_amount = sum(abs(t.get("amount", 0)) for t in unmatched_bank)

    summary_message = (
        f"Reconciliation complete.\n\n"
        f"Period: {state.get('period_start')} to {state.get('period_end')}\n"
        f"Matched: {matched}/{total} ({match_rate}%)\n"
        f"Exceptions: {exception_count} items flagged\n"
        f"High Risk: {high_risk} item(s) (RM {unmatched_amount:,.2f} unmatched)\n\n"
    )

    if state.get("summary"):
        summary_message += f"Summary:\n{state['summary']}"

    await update.message.reply_text(summary_message)

    # Send the Excel file if it was generated successfully
    report_path = state.get("report_path")
    if report_path and os.path.exists(report_path):
        with open(report_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(report_path),
                caption="Full reconciliation report",
            )
    else:
        await update.message.reply_text("Note: Excel report could not be generated.")


# --- App setup ---

def build_application() -> Application:
    # Wires all handlers and returns the configured Application.
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Simple command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("report", cmd_report))

    # Multi-step /reconcile conversation
    reconcile_handler = ConversationHandler(
        entry_points=[CommandHandler("reconcile", cmd_reconcile)],
        states={
            WAITING_FOR_BANK: [MessageHandler(filters.Document.ALL, receive_bank_file)],
            WAITING_FOR_LEDGER: [MessageHandler(filters.Document.ALL, receive_ledger_file)],
            WAITING_FOR_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_period)],
        },
        fallbacks=[CommandHandler("cancel", cancel_reconcile)],
    )
    app.add_handler(reconcile_handler)

    return app


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

    init_db()
    logger.info("starting OpenReco Telegram bot")

    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
