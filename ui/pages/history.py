# History page — table of past reconciliation sessions from SQLite.
# Clicking "Load" on any session restores it into session state
# so the user can jump to Results, Exceptions, or Report for that run.

import os
import streamlit as st
import pandas as pd

from src.database.queries import get_recent_sessions, get_session, get_matches_for_session, get_exceptions_for_session


def render():
    st.title("Reconciliation History")

    sessions = get_recent_sessions(limit=20)

    if not sessions:
        st.info("No past reconciliation sessions found.")
        if st.button("Run a Reconciliation"):
            st.session_state["page"] = "home"
            st.rerun()
        return

    st.write(f"{len(sessions)} session(s) found.")
    st.divider()

    # --- Summary table ---
    rows = []
    for s in sessions:
        total = s.get("total_bank", 0)
        matched = s.get("matched_count", 0)
        match_rate = round((matched / total * 100), 1) if total > 0 else 0.0
        rows.append({
            "ID": s["id"],
            "Created": s.get("created_at", ""),
            "Period": f"{s.get('period_start', '')} to {s.get('period_end', '')}",
            "Matched": f"{matched} / {total}",
            "Match Rate": f"{match_rate}%",
            "Exceptions": s.get("exception_count", 0),
            "Status": s.get("status", ""),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()

    # --- Load a past session ---
    st.subheader("Load a Past Session")
    st.write("Enter a session ID from the table above to load its results.")

    session_id_input = st.number_input(
        "Session ID",
        min_value=1,
        step=1,
        key="history_session_id",
    )

    if st.button("Load Session", type="primary"):
        session = get_session(int(session_id_input))
        if not session:
            st.error(f"Session #{session_id_input} not found.")
            return

        # Reconstruct enough of the pipeline state from the database
        # so the Results, Exceptions, and Report pages can work correctly.
        matches = get_matches_for_session(int(session_id_input))
        db_exceptions = get_exceptions_for_session(int(session_id_input))

        # Convert db exception rows to the format the UI pages expect
        exceptions = [
            {
                "exception_id": str(e.get("id", "")),
                "type": e.get("exception_type", ""),
                "item_id": e.get("item_id", ""),
                "item_source": e.get("item_source", ""),
                "amount": e.get("amount", 0),
                "description": e.get("description", ""),
                "investigation": e.get("investigation"),
                "resolution": e.get("resolution"),
                "severity": e.get("severity", "Low"),
                "suggested_match": None,
            }
            for e in db_exceptions
        ]

        # We don't have the full transaction lists from the database,
        # but we can populate enough state for the results summary to render.
        restored_state = {
            "bank_file_path": session.get("bank_file", ""),
            "ledger_file_path": session.get("ledger_file", ""),
            "period_start": session.get("period_start", ""),
            "period_end": session.get("period_end", ""),
            "session_id": session.get("id"),
            "bank_transactions": [],
            "ledger_entries": [],
            "matches": matches,
            "exceptions": exceptions,
            "total_bank": session.get("total_bank", 0),
            "total_ledger": session.get("total_ledger", 0),
            "matched_count": session.get("matched_count", 0),
            "unmatched_count": 0,
            "report_path": session.get("report_path", ""),
            "summary": session.get("summary", ""),
            "errors": [],
            "status": session.get("status", "DONE"),
        }

        st.session_state["pipeline_state"] = restored_state
        st.success(f"Session #{session_id_input} loaded.")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("View Results", use_container_width=True):
                st.session_state["page"] = "results"
                st.rerun()
        with col2:
            if st.button("View Exceptions", use_container_width=True):
                st.session_state["page"] = "exceptions"
                st.rerun()
        with col3:
            if st.button("Download Report", use_container_width=True):
                st.session_state["page"] = "report"
                st.rerun()
