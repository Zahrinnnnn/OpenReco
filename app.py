# Streamlit entry point for OpenReco.
# Handles page routing via st.session_state["page"].
# All pages share the same session state so data flows between them.
#
# Run with: streamlit run app.py

import streamlit as st

from src.database.connection import init_db
from ui.pages import home, progress, results, exceptions, report, history

# Initialise the database tables on first run
init_db()

st.set_page_config(
    page_title="OpenReco",
    page_icon="bank",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Set the default page if not already set
if "page" not in st.session_state:
    st.session_state["page"] = "home"

# --- Sidebar navigation ---

with st.sidebar:
    st.title("OpenReco")
    st.caption("Bank Reconciliation Assistant")
    st.divider()

    nav_options = {
        "home": "New Reconciliation",
        "progress": "Progress",
        "results": "Results",
        "exceptions": "Exceptions",
        "report": "Report",
        "history": "History",
    }

    for page_key, label in nav_options.items():
        if st.button(label, use_container_width=True, key=f"nav_{page_key}"):
            st.session_state["page"] = page_key
            st.rerun()

    st.divider()
    st.caption("Powered by DeepSeek + LangGraph")

# --- Page routing ---

current_page = st.session_state.get("page", "home")

if current_page == "home":
    home.render()
elif current_page == "progress":
    progress.render()
elif current_page == "results":
    results.render()
elif current_page == "exceptions":
    exceptions.render()
elif current_page == "report":
    report.render()
elif current_page == "history":
    history.render()
