# Results page — summary KPIs, match rate chart, and exception overview.
# Reads from st.session_state["pipeline_state"] populated by the progress page.

import streamlit as st
import pandas as pd


def render():
    st.title("Reconciliation Results")

    state = st.session_state.get("pipeline_state")
    if not state:
        st.info("No results yet. Run a reconciliation first.")
        if st.button("Go to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        return

    total_bank = state.get("total_bank", 0)
    total_ledger = state.get("total_ledger", 0)
    matched_count = state.get("matched_count", 0)
    exceptions = state.get("exceptions", [])
    exception_count = len(exceptions)
    high_risk = sum(1 for e in exceptions if e.get("severity") == "High")
    medium_risk = sum(1 for e in exceptions if e.get("severity") == "Medium")
    low_risk = sum(1 for e in exceptions if e.get("severity") == "Low")
    match_rate = round((matched_count / total_bank * 100), 1) if total_bank > 0 else 0.0

    unmatched_bank = [t for t in state.get("bank_transactions", []) if not t.get("matched")]
    unmatched_amount = sum(abs(t.get("amount", 0)) for t in unmatched_bank)

    # --- KPI metrics row ---
    st.subheader(f"Period: {state.get('period_start')} to {state.get('period_end')}")
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Match Rate", f"{match_rate}%")
    with col2:
        st.metric("Matched", f"{matched_count} / {total_bank}")
    with col3:
        st.metric("Exceptions", exception_count)
    with col4:
        st.metric("Unmatched Amount", f"RM {unmatched_amount:,.2f}")

    st.divider()

    # --- Charts row ---
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Match breakdown")
        unmatched_count = total_bank - matched_count
        chart_data = pd.DataFrame({
            "Category": ["Matched", "Unmatched"],
            "Count": [matched_count, unmatched_count],
        })
        st.bar_chart(chart_data.set_index("Category"))

    with col_chart2:
        st.subheader("Exception severity")
        if exception_count > 0:
            severity_data = pd.DataFrame({
                "Severity": ["High", "Medium", "Low"],
                "Count": [high_risk, medium_risk, low_risk],
            })
            st.bar_chart(severity_data.set_index("Severity"))
        else:
            st.success("No exceptions — perfect reconciliation.")

    st.divider()

    # --- Matched pairs table ---
    st.subheader("Matched Pairs")

    matches = state.get("matches", [])
    bank_by_id = {t["id"]: t for t in state.get("bank_transactions", [])}
    ledger_by_id = {e["id"]: e for e in state.get("ledger_entries", [])}

    if matches:
        rows = []
        for match in matches:
            bank_txn = bank_by_id.get(match["bank_txn_id"], {})
            ledger_entry = ledger_by_id.get(match["ledger_entry_id"], {})
            rows.append({
                "Bank Date": bank_txn.get("date", ""),
                "Bank Description": bank_txn.get("description", ""),
                "Bank Amount": f"RM {abs(bank_txn.get('amount', 0)):,.2f}",
                "Ledger Date": ledger_entry.get("date", ""),
                "Ledger Description": ledger_entry.get("description", ""),
                "Match Type": match.get("match_type", ""),
                "Confidence": f"{match.get('confidence', 0):.0%}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("No matches found.")

    st.divider()

    col_nav1, col_nav2, col_nav3 = st.columns(3)
    with col_nav1:
        if st.button("View Exceptions", use_container_width=True):
            st.session_state["page"] = "exceptions"
            st.rerun()
    with col_nav2:
        if st.button("Download Report", use_container_width=True):
            st.session_state["page"] = "report"
            st.rerun()
    with col_nav3:
        if st.button("New Reconciliation", use_container_width=True):
            st.session_state["page"] = "home"
            st.rerun()
