# Defines the shared state that flows through the entire LangGraph pipeline.
# Every agent reads from and writes to a RecoState dict.

from typing import TypedDict, List, Optional, Annotated
import operator


class Transaction(TypedDict):
    id: str
    date: str
    description: str
    reference: Optional[str]
    debit: float
    credit: float
    amount: float
    matched: bool
    match_id: Optional[str]
    confidence: Optional[float]


class LedgerEntry(TypedDict):
    id: str
    date: str
    description: str
    reference: Optional[str]
    amount: float
    entry_type: str
    matched: bool
    match_id: Optional[str]


class Match(TypedDict):
    match_id: str
    bank_txn_id: str
    ledger_entry_id: str
    match_type: str
    confidence: float
    reasoning: str


class Exception(TypedDict):
    exception_id: str
    type: str
    item_id: str
    item_source: str
    amount: float
    description: str
    investigation: Optional[str]
    resolution: Optional[str]
    severity: str


class RecoState(TypedDict):
    # Input fields set at the start of each run
    bank_file_path: str
    ledger_file_path: str
    period_start: str
    period_end: str
    session_id: Optional[int]

    # Parsed data produced by agents 1 and 2
    bank_transactions: List[Transaction]
    ledger_entries: List[LedgerEntry]

    # Results produced by agents 3 and 4
    # Annotated with operator.add so parallel nodes can append to these lists safely
    matches: Annotated[List[Match], operator.add]
    exceptions: Annotated[List[Exception], operator.add]

    # Summary stats updated by agent 3
    total_bank: int
    total_ledger: int
    matched_count: int
    unmatched_count: int

    # Output produced by agent 5
    report_path: Optional[str]
    summary: Optional[str]

    # Error tracking and pipeline status
    errors: Annotated[List[str], operator.add]
    status: str  # RUNNING, DONE, FAILED
