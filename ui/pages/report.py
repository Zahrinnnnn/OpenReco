# Report page — download button for the Excel report and the narrative summary.
# Reads report_path and summary from st.session_state["pipeline_state"].

import os
import streamlit as st


def render():
    st.title("Report")

    state = st.session_state.get("pipeline_state")
    if not state:
        st.info("No report available yet. Run a reconciliation first.")
        if st.button("Go to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        return

    report_path = state.get("report_path")
    summary = state.get("summary")

    # --- Narrative summary ---
    st.subheader("Narrative Summary")
    if summary:
        st.info(summary)
    else:
        st.caption("No summary was generated.")

    st.divider()

    # --- Key stats ---
    total = state.get("total_bank", 0)
    matched = state.get("matched_count", 0)
    exceptions = state.get("exceptions", [])
    match_rate = round((matched / total * 100), 1) if total > 0 else 0.0
    high_risk = sum(1 for e in exceptions if e.get("severity") == "High")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Match Rate", f"{match_rate}%")
    with col2:
        st.metric("Total Exceptions", len(exceptions))
    with col3:
        st.metric("High Risk", high_risk)

    st.divider()

    # --- Excel download ---
    st.subheader("Excel Report")

    if report_path and os.path.exists(report_path):
        with open(report_path, "rb") as f:
            report_bytes = f.read()

        st.download_button(
            label="Download Excel Report",
            data=report_bytes,
            file_name=os.path.basename(report_path),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

        st.caption(f"File: {os.path.basename(report_path)}")
        file_size_kb = os.path.getsize(report_path) / 1024
        st.caption(f"Size: {file_size_kb:.1f} KB")

        st.divider()
        st.write("The report contains 7 sheets:")
        sheets = [
            ("Summary", "KPIs, period, match rate, and narrative summary"),
            ("Matched", "All matched pairs with confidence and match type"),
            ("Exceptions", "All exceptions with investigation notes and recommended actions"),
            ("Bank Only", "Unmatched bank transactions"),
            ("Ledger Only", "Unmatched ledger entries"),
            ("All Transactions", "Complete bank transaction list"),
            ("All Ledger", "Complete ledger entry list"),
        ]
        for sheet_name, description in sheets:
            st.write(f"- **{sheet_name}** — {description}")

    else:
        st.error("Excel report file not found. It may have failed to generate.")
        if state.get("errors"):
            st.write("Errors:")
            for error in state["errors"]:
                st.write(f"- {error}")

    st.divider()

    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("Back to Results", use_container_width=True):
            st.session_state["page"] = "results"
            st.rerun()
    with col_nav2:
        if st.button("New Reconciliation", use_container_width=True):
            st.session_state["page"] = "home"
            st.rerun()
