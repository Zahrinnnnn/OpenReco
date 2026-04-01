# Exceptions page — detailed table of all exceptions with DeepSeek investigation notes.
# Severity is shown as a colour-coded badge. Users can filter by severity and type.

import streamlit as st
import pandas as pd


SEVERITY_COLOURS = {
    "High": "red",
    "Medium": "orange",
    "Low": "green",
}

TYPE_LABELS = {
    "BANK_ONLY": "Bank Only",
    "LEDGER_ONLY": "Ledger Only",
    "LOW_CONFIDENCE": "Low Confidence",
    "HIGH_VALUE": "High Value",
}


def render():
    st.title("Exceptions")

    state = st.session_state.get("pipeline_state")
    if not state:
        st.info("No results yet. Run a reconciliation first.")
        if st.button("Go to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        return

    exceptions = state.get("exceptions", [])

    if not exceptions:
        st.success("No exceptions found. All transactions matched successfully.")
        return

    st.write(f"{len(exceptions)} exception(s) identified.")
    st.divider()

    # --- Filter controls ---
    col_filter1, col_filter2 = st.columns(2)

    with col_filter1:
        severity_filter = st.multiselect(
            "Filter by Severity",
            options=["High", "Medium", "Low"],
            default=["High", "Medium", "Low"],
        )
    with col_filter2:
        type_filter = st.multiselect(
            "Filter by Type",
            options=list(TYPE_LABELS.keys()),
            default=list(TYPE_LABELS.keys()),
            format_func=lambda t: TYPE_LABELS.get(t, t),
        )

    # Apply filters
    filtered = [
        e for e in exceptions
        if e.get("severity") in severity_filter and e.get("type") in type_filter
    ]

    if not filtered:
        st.info("No exceptions match the selected filters.")
        return

    st.write(f"Showing {len(filtered)} of {len(exceptions)} exception(s).")
    st.divider()

    # --- Exception cards ---
    for exc in filtered:
        severity = exc.get("severity", "Low")
        colour = SEVERITY_COLOURS.get(severity, "grey")
        exc_type = TYPE_LABELS.get(exc.get("type", ""), exc.get("type", ""))
        amount = abs(exc.get("amount", 0))

        with st.expander(
            f":{colour}[{severity}]  |  {exc_type}  |  "
            f"{exc.get('description', 'No description')}  |  RM {amount:,.2f}",
            expanded=(severity == "High"),
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Exception ID:** {exc.get('exception_id', '')}")
                st.write(f"**Type:** {exc_type}")
                st.write(f"**Source:** {exc.get('item_source', '').title()}")
                st.write(f"**Amount:** RM {amount:,.2f}")
                st.write(f"**Severity:** {severity}")
            with col2:
                st.write(f"**Description:** {exc.get('description', '')}")
                if exc.get("suggested_match"):
                    st.write(f"**Suggested Match:** {exc['suggested_match']}")

            if exc.get("investigation"):
                st.write("**Likely Reason:**")
                st.info(exc["investigation"])

            if exc.get("resolution"):
                st.write("**Recommended Action:**")
                st.warning(exc["resolution"])

            if not exc.get("investigation") and not exc.get("resolution"):
                st.caption("No DeepSeek investigation available for this exception.")

    st.divider()

    # --- Export filtered exceptions as CSV ---
    if st.button("Export Filtered Exceptions as CSV"):
        rows = []
        for exc in filtered:
            rows.append({
                "Exception ID": exc.get("exception_id", ""),
                "Type": exc.get("type", ""),
                "Source": exc.get("item_source", ""),
                "Amount": abs(exc.get("amount", 0)),
                "Description": exc.get("description", ""),
                "Severity": exc.get("severity", ""),
                "Investigation": exc.get("investigation", ""),
                "Recommended Action": exc.get("resolution", ""),
            })
        csv_data = pd.DataFrame(rows).to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name="exceptions.csv",
            mime="text/csv",
        )
