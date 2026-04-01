# CLI entry point for OpenReco.
# Run a full reconciliation from the command line by passing the bank and ledger CSV files.
# Example:
#   python main.py --bank data/uploads/bank.csv --ledger data/uploads/ledger.csv \
#                  --start 2026-03-01 --end 2026-03-31

import argparse
import sys

from src.utils.logger import setup_logger, get_logger
from src.graph.pipeline import run_pipeline

logger = get_logger("main")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="OpenReco — bank reconciliation pipeline",
    )
    parser.add_argument(
        "--bank",
        required=True,
        help="Path to the bank statement CSV file",
    )
    parser.add_argument(
        "--ledger",
        required=True,
        help="Path to the ledger CSV file",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Reconciliation period start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="Reconciliation period end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


def print_results(state: dict) -> None:
    # Prints a short summary of the reconciliation results to the terminal.
    total = state.get("total_bank", 0)
    matched = state.get("matched_count", 0)
    exceptions = state.get("exceptions", [])
    exception_count = len(exceptions)
    high_risk = sum(1 for e in exceptions if e.get("severity") == "High")
    match_rate = (matched / total * 100) if total > 0 else 0.0

    print("\n" + "=" * 60)
    print("Reconciliation complete")
    print("=" * 60)
    print(f"Period:      {state.get('period_start')} to {state.get('period_end')}")
    print(f"Matched:     {matched} / {total} ({match_rate:.1f}%)")
    print(f"Exceptions:  {exception_count} total, {high_risk} high risk")
    print(f"Report:      {state.get('report_path', 'not generated')}")
    print()
    if state.get("summary"):
        print("Summary:")
        print(state["summary"])
    print("=" * 60 + "\n")

    if state.get("errors"):
        print("Errors encountered:")
        for error in state["errors"]:
            print(f"  - {error}")


def main():
    args = parse_arguments()
    setup_logger(args.log_level)

    logger.info("starting reconciliation run")
    logger.info("bank file:   {}", args.bank)
    logger.info("ledger file: {}", args.ledger)
    logger.info("period:      {} to {}", args.start, args.end)

    final_state = run_pipeline(
        bank_file_path=args.bank,
        ledger_file_path=args.ledger,
        period_start=args.start,
        period_end=args.end,
    )

    print_results(final_state)

    if final_state.get("status") == "FAILED":
        logger.error("pipeline finished with FAILED status")
        sys.exit(1)

    logger.info("pipeline finished successfully")


if __name__ == "__main__":
    main()
