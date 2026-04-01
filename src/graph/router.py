# Routing logic for the LangGraph pipeline.
# After each agent runs, the router checks the state and decides whether
# to continue to the next node or jump to the end because of a failure.

def should_continue_after_ingestion(state: dict) -> str:
    # After document ingestion, only continue if we got bank transactions.
    if state.get("status") == "FAILED" or not state.get("bank_transactions"):
        return "end"
    return "ledger_sync"


def should_continue_after_ledger(state: dict) -> str:
    # After ledger sync, only continue if we got ledger entries.
    if state.get("status") == "FAILED" or not state.get("ledger_entries"):
        return "end"
    return "reconciliation_engine"


def should_continue_after_reconciliation(state: dict) -> str:
    # After reconciliation, always continue even if there are no exceptions.
    # Exceptions being empty is a valid outcome (perfect reconciliation).
    if state.get("status") == "FAILED":
        return "end"
    return "exception_investigator"


def should_continue_after_investigation(state: dict) -> str:
    # After exception investigation, always continue to the report writer.
    if state.get("status") == "FAILED":
        return "end"
    return "report_writer"
