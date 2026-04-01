# All database read and write operations live here.
# Import get_connection from connection.py and use it in each function.

from src.database.connection import get_connection


# recon_sessions

def create_session(period_start, period_end, bank_file, ledger_file):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO recon_sessions (period_start, period_end, bank_file, ledger_file, status)
        VALUES (?, ?, ?, ?, 'RUNNING')
        """,
        (period_start, period_end, bank_file, ledger_file)
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def update_session(session_id, **fields):
    # Pass any column name as a keyword argument to update it.
    # Example: update_session(1, status='DONE', matched_count=80)
    if not fields:
        return

    set_clause = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [session_id]

    conn = get_connection()
    conn.execute(f"UPDATE recon_sessions SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_session(session_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM recon_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_sessions(limit=5):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recon_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# matches

def insert_match(session_id, bank_txn_id, ledger_entry_id, match_type, confidence, reasoning):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO matches (session_id, bank_txn_id, ledger_entry_id, match_type, confidence, reasoning)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, bank_txn_id, ledger_entry_id, match_type, confidence, reasoning)
    )
    conn.commit()
    conn.close()


def get_matches_for_session(session_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM matches WHERE session_id = ?", (session_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# exceptions

def insert_exception(session_id, exception_type, item_id, item_source, amount, description, severity):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO exceptions (session_id, exception_type, item_id, item_source, amount, description, severity)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, exception_type, item_id, item_source, amount, description, severity)
    )
    conn.commit()
    conn.close()


def update_exception_investigation(session_id, item_id, investigation, resolution):
    conn = get_connection()
    conn.execute(
        """
        UPDATE exceptions SET investigation = ?, resolution = ?
        WHERE session_id = ? AND item_id = ?
        """,
        (investigation, resolution, session_id, item_id)
    )
    conn.commit()
    conn.close()


def get_exceptions_for_session(session_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM exceptions WHERE session_id = ?", (session_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# Bulk insert helpers used by report_writer_agent

def insert_session(session_id, period_start, period_end, bank_file, ledger_file,
                   status, total_bank, total_ledger, matched_count, exception_count,
                   report_path, summary):
    # Updates an existing session row with the final results from the pipeline.
    # The session row is created at the start of the run via create_session().
    update_session(
        session_id,
        period_start=period_start,
        period_end=period_end,
        bank_file=bank_file,
        ledger_file=ledger_file,
        status=status,
        total_bank=total_bank,
        total_ledger=total_ledger,
        matched_count=matched_count,
        exception_count=exception_count,
        report_path=report_path,
        summary=summary,
    )


def insert_matches(session_id, matches: list):
    # Inserts all match records for a session in a single transaction.
    if not matches:
        return
    conn = get_connection()
    conn.executemany(
        """
        INSERT INTO matches (session_id, bank_txn_id, ledger_entry_id, match_type, confidence, reasoning)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                session_id,
                m["bank_txn_id"],
                m["ledger_entry_id"],
                m["match_type"],
                m["confidence"],
                m["reasoning"],
            )
            for m in matches
        ],
    )
    conn.commit()
    conn.close()


def insert_exceptions(session_id, exceptions: list):
    # Inserts all exception records for a session in a single transaction.
    if not exceptions:
        return
    conn = get_connection()
    conn.executemany(
        """
        INSERT INTO exceptions (session_id, exception_type, item_id, item_source, amount,
                                description, investigation, resolution, severity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                session_id,
                e["type"],
                e["item_id"],
                e["item_source"],
                e["amount"],
                e["description"],
                e.get("investigation"),
                e.get("resolution"),
                e.get("severity"),
            )
            for e in exceptions
        ],
    )
    conn.commit()
    conn.close()


# audit_log

def log_audit(session_id, agent, action, details=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (session_id, agent, action, details) VALUES (?, ?, ?, ?)",
        (session_id, agent, action, details)
    )
    conn.commit()
    conn.close()
