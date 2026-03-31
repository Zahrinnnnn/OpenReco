# Handles SQLite connection and table creation.
# Call init_db() once at startup to make sure all tables exist.

import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/database.db")


def get_connection():
    # Returns a sqlite3 connection with row_factory so rows come back as dicts.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # Creates all tables if they don't exist yet.
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS recon_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            period_start    DATE,
            period_end      DATE,
            bank_file       TEXT,
            ledger_file     TEXT,
            status          TEXT,
            total_bank      INTEGER,
            total_ledger    INTEGER,
            matched_count   INTEGER,
            exception_count INTEGER,
            report_path     TEXT,
            summary         TEXT
        );

        CREATE TABLE IF NOT EXISTS matches (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER REFERENCES recon_sessions(id),
            bank_txn_id     TEXT,
            ledger_entry_id TEXT,
            match_type      TEXT,
            confidence      REAL,
            reasoning       TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exceptions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER REFERENCES recon_sessions(id),
            exception_type  TEXT,
            item_id         TEXT,
            item_source     TEXT,
            amount          REAL,
            description     TEXT,
            investigation   TEXT,
            resolution      TEXT,
            severity        TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id  INTEGER,
            agent       TEXT,
            action      TEXT,
            details     TEXT
        );
    """)

    conn.commit()
    conn.close()
