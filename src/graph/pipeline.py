# LangGraph pipeline definition.
# Wires the 5 agents as nodes in a StateGraph and connects them with
# conditional edges so a failure in one agent skips the rest cleanly.
# Agent 4 (exception_investigator) runs in a simple sequential pass here;
# parallel execution per exception is handled inside the agent itself.

from langgraph.graph import StateGraph, END

from src.graph.state import RecoState
from src.graph.router import (
    should_continue_after_ingestion,
    should_continue_after_ledger,
    should_continue_after_reconciliation,
    should_continue_after_investigation,
)
from src.agents.document_ingestion import document_ingestion_agent
from src.agents.ledger_sync import ledger_sync_agent
from src.agents.reconciliation_engine import reconciliation_engine_agent
from src.agents.exception_investigator import exception_investigator_agent
from src.agents.report_writer import report_writer_agent


def build_pipeline():
    # Creates and compiles the LangGraph StateGraph.
    # Returns a compiled runnable that accepts a RecoState dict.

    graph = StateGraph(RecoState)

    # Register each agent as a named node
    graph.add_node("document_ingestion", document_ingestion_agent)
    graph.add_node("ledger_sync", ledger_sync_agent)
    graph.add_node("reconciliation_engine", reconciliation_engine_agent)
    graph.add_node("exception_investigator", exception_investigator_agent)
    graph.add_node("report_writer", report_writer_agent)

    # The pipeline always starts with document ingestion
    graph.set_entry_point("document_ingestion")

    # Conditional edges check state after each agent and route accordingly
    graph.add_conditional_edges(
        "document_ingestion",
        should_continue_after_ingestion,
        {
            "ledger_sync": "ledger_sync",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "ledger_sync",
        should_continue_after_ledger,
        {
            "reconciliation_engine": "reconciliation_engine",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "reconciliation_engine",
        should_continue_after_reconciliation,
        {
            "exception_investigator": "exception_investigator",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "exception_investigator",
        should_continue_after_investigation,
        {
            "report_writer": "report_writer",
            "end": END,
        },
    )

    # Report writer always ends the pipeline
    graph.add_edge("report_writer", END)

    return graph.compile()


def run_pipeline(
    bank_file_path: str,
    ledger_file_path: str,
    period_start: str,
    period_end: str,
    session_id: int = None,
) -> dict:
    # Builds the pipeline, sets up the initial state, and runs it end to end.
    # Returns the final state dict after all agents have completed.

    pipeline = build_pipeline()

    initial_state = {
        "bank_file_path": bank_file_path,
        "ledger_file_path": ledger_file_path,
        "period_start": period_start,
        "period_end": period_end,
        "session_id": session_id,
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

    final_state = pipeline.invoke(initial_state)
    return final_state
