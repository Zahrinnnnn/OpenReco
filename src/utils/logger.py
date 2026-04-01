# Centralised logging setup using loguru.
# Every agent imports get_logger() and uses it to log start, finish, and errors.
# Log lines include a timestamp, level, and the agent name for easy filtering.

import sys
from loguru import logger


def setup_logger(log_level: str = "INFO") -> None:
    # Call this once at application start (main.py, bot.py, app.py).
    # Removes the default loguru handler and replaces it with a clean format.
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=log_level,
        colorize=True,
    )
    logger.add(
        "data/openreco.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
    )


def get_logger(name: str):
    # Returns a loguru logger bound with the agent or module name.
    # Usage: logger = get_logger("document_ingestion")
    return logger.bind(agent=name)
