# Progress page — runs the pipeline and shows live status updates per agent.
# The pipeline is run synchronously inside st.status() blocks so the UI
# updates as each agent completes. When done, switches to the Results page.

import streamlit as st

from src.agents.document_ingestion import document_ingestion_agent
from src.agents.ledger_sync import ledger_sync_agent
from src.agents.reconciliation_engine import reconciliation_engine_agent
from src.agents.exception_investigator import exception_investigator_agent
from src.agents.report_writer import report_writer_agent


def render():
    st.title("Reconciliation in Progress")

    config = st.session_state.get("run_config")
    if not config:
        st.warning("No reconciliation has been started. Go to New Reconciliation first.")
        if st.button("Go to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        return

    # If the pipeline already finished (e.g. user navigated back), skip re-running
    if st.session_state.get("pipeline_state"):
        st.success("Reconciliation already complete.")
        if st.button("View Results"):
            st.session_state["page"] = "results"
            st.rerun()
        return

    # Build the initial state dict the pipeline expects
    initial_state = {
        "bank_file_path": config["bank_file_path"],
        "ledger_file_path": config["ledger_file_path"],
        "period_start": config["period_start"],
        "period_end": config["period_end"],
        "session_id": config.get("session_id"),
        "bank_transactions": [],
        "ledger_entries": [],
        "matches": [],
        "exceptions": [],
        "total_bank": 0,
        "total_ledger": 0,
        "matched_count": 0,
        "unmatched_count": 0,
        "report_path": None,
        "summary": None,
        "errors": [],
        "status": "RUNNING",
    }

    state = initial_state

    # Run each agent in sequence, updating the UI as each completes.
    # st.status() shows a spinner while running and a tick when done.

    with st.status("Agent 1/5: Parsing bank statement...", expanded=True) as agent1_status:
        state = document_ingestion_agent(state)
        if state.get("status") == "FAILED":
            agent1_status.update(label="Agent 1/5: FAILED", state="error")
            show_errors(state)
            return
        count = len(state.get("bank_transactions", []))
        agent1_status.update(
            label=f"Agent 1/5: Bank statement parsed. {count} transactions found.",
            state="complete",
        )

    with st.status("Agent 2/5: Syncing ledger...", expanded=True) as agent2_status:
        state = ledger_sync_agent(state)
        if state.get("status") == "FAILED":
            agent2_status.update(label="Agent 2/5: FAILED", state="error")
            show_errors(state)
            return
        count = len(state.get("ledger_entries", []))
        agent2_status.update(
            label=f"Agent 2/5: Ledger synced. {count} entries loaded.",
            state="complete",
        )

    with st.status("Agent 3/5: Matching transactions...", expanded=True) as agent3_status:
        state = reconciliation_engine_agent(state)
        if state.get("status") == "FAILED":
            agent3_status.update(label="Agent 3/5: FAILED", state="error")
            show_errors(state)
            return
        matched = state.get("matched_count", 0)
        total = state.get("total_bank", 0)
        exceptions = len(state.get("exceptions", []))
        agent3_status.update(
            label=f"Agent 3/5: Matching complete. {matched}/{total} matched, {exceptions} exceptions.",
            state="complete",
        )

    with st.status("Agent 4/5: Investigating exceptions...", expanded=True) as agent4_status:
        exception_count = len(state.get("exceptions", []))
        state = exception_investigator_agent(state)
        agent4_status.update(
            label=f"Agent 4/5: Investigated {exception_count} exception(s).",
            state="complete",
        )

    with st.status("Agent 5/5: Generating report...", expanded=True) as agent5_status:
        state = report_writer_agent(state)
        agent5_status.update(
            label="Agent 5/5: Report generated.",
            state="complete",
        )

    # Store the final state so other pages can read it
    st.session_state["pipeline_state"] = state

    st.success("Reconciliation complete!")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("View Results", type="primary", use_container_width=True):
            st.session_state["page"] = "results"
            st.rerun()
    with col2:
        if st.button("Download Report", use_container_width=True):
            st.session_state["page"] = "report"
            st.rerun()


def show_errors(state: dict) -> None:
    # Displays any pipeline errors in a clean format.
    errors = state.get("errors", [])
    if errors:
        st.error("Pipeline errors:")
        for error in errors:
            st.write(f"- {error}")
    else:
        st.error("An unknown error occurred.")
