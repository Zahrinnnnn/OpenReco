# Home page — file uploaders for bank and ledger CSVs, period picker, run button.
# When the user clicks Run, the pipeline is launched and the page switches to Progress.

import os
import streamlit as st
from datetime import date, timedelta

from src.database.connection import init_db
from src.database.queries import create_session

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "data/uploads")


def render():
    st.title("New Reconciliation")
    st.write("Upload your bank statement and ledger CSV, set the period, then click Run.")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Bank Statement")
        bank_file = st.file_uploader(
            "Upload bank statement CSV",
            type=["csv"],
            key="bank_upload",
            help="CSV exported from your bank. Columns will be detected automatically.",
        )

    with col_right:
        st.subheader("Ledger")
        ledger_file = st.file_uploader(
            "Upload ledger CSV",
            type=["csv"],
            key="ledger_upload",
            help="CSV exported from your accounting system.",
        )

    st.divider()

    st.subheader("Reconciliation Period")
    col_start, col_end = st.columns(2)

    with col_start:
        # Default to the first day of last month
        first_of_this_month = date.today().replace(day=1)
        default_start = (first_of_this_month - timedelta(days=1)).replace(day=1)
        period_start = st.date_input("Period Start", value=default_start, key="period_start")

    with col_end:
        # Default to the last day of last month
        default_end = first_of_this_month - timedelta(days=1)
        period_end = st.date_input("Period End", value=default_end, key="period_end")

    st.divider()

    run_clicked = st.button("Run Reconciliation", type="primary", use_container_width=True)

    if run_clicked:
        if not bank_file:
            st.error("Please upload a bank statement CSV.")
            return
        if not ledger_file:
            st.error("Please upload a ledger CSV.")
            return
        if period_start > period_end:
            st.error("Period start must be before period end.")
            return

        # Save uploaded files to disk
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        bank_path = os.path.join(UPLOAD_DIR, f"bank_{bank_file.name}")
        ledger_path = os.path.join(UPLOAD_DIR, f"ledger_{ledger_file.name}")

        with open(bank_path, "wb") as f:
            f.write(bank_file.getbuffer())
        with open(ledger_path, "wb") as f:
            f.write(ledger_file.getbuffer())

        # Create the session record in SQLite
        session_id = create_session(
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            bank_file=bank_path,
            ledger_file=ledger_path,
        )

        # Store everything in session state for the progress page to pick up
        st.session_state["run_config"] = {
            "bank_file_path": bank_path,
            "ledger_file_path": ledger_path,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "session_id": session_id,
        }
        st.session_state["pipeline_state"] = None
        st.session_state["page"] = "progress"
        st.rerun()
