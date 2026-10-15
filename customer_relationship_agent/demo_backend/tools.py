"""SQLite versions of the agents' tools, used when BANK_BACKEND=sqlite.

Each write tool keeps the name, signature, docstring and return messages of its BigQuery counterpart in
tools.py or complaints_agent/tools.py, so the model sees the same tool declarations. Values always go in as
SQLite query parameters (?), never spliced into SQL.

bq_agent keeps its name so the agent graph is unchanged, but here it wraps three read-only SQL tools over the
SQLite file instead of ADK's BigQueryToolset. search_places is a stand-in for the Google Maps MCP tool that
returns fictional locations from the demo database.
"""

import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from google.adk.agents import Agent

from ..backend import MODEL

SEED_FILE = Path(__file__).parent / "seed.sql"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / ".demo" / "bank.db"
MAX_ROWS = 50  # same default cap as ADK's BigQuery execute_sql


def db_path() -> Path:
    return Path(os.environ.get("BANK_SQLITE_PATH", DEFAULT_DB_PATH))


def reset_db() -> Path:
    """Delete the demo database and recreate it from seed.sql."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SEED_FILE.read_text())
    finally:
        conn.close()
    return path


def _connect(read_only: bool = False) -> sqlite3.Connection:
    path = db_path()
    if not path.exists():
        reset_db()
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _db(read_only: bool = False):
    """Open a connection, commit on success and always close it."""
    conn = _connect(read_only)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _customer_ids(conn: sqlite3.Connection, name: str) -> list[str]:
    return [r["customer_id"] for r in conn.execute("SELECT customer_id FROM customers WHERE name = ?", (name,))]


# --- customer tools (root agent) ---------------------------------------------------------------------------


def bq_update_customer_phone_number(customer_id: str, new_phone_number: str):
    """
    Updates a customer's phone number
    Args:
        customer_id (str): The ID of the customer.
        new_phone_number (str): The new phone number for this customer
    Output: A confirmation message
    """
    try:
        with _db() as conn:
            cur = conn.execute("UPDATE customers SET phone = ? WHERE customer_id = ?", (new_phone_number, customer_id))
        if cur.rowcount == 0:
            return f"Error: Customer ID {customer_id} not found. No update performed."
        return f"Success: Phone number for Customer {customer_id} updated to {new_phone_number}."
    except Exception as e:
        return f"Error updating record: {str(e)}"


def update_customer_phone_by_name(customer_name: str, new_phone_number: str):
    """
    Updates a customer's phone number by looking up their name.
    Args:
        customer_name (str): The full name of the customer.
        new_phone_number (str): The new phone number for this customer.
    Output: A confirmation or error message.
    """
    try:
        with _db() as conn:
            ids = _customer_ids(conn, customer_name)
        if len(ids) == 0:
            return f"Error: Customer '{customer_name}' not found."
        if len(ids) > 1:
            return f"Error: Multiple customers found with the name '{customer_name}'. Please provide a unique customer ID."
        return bq_update_customer_phone_number(ids[0], new_phone_number)
    except Exception as e:
        return f"Error looking up customer: {str(e)}"


def find_customer_by_name(customer_name: str):
    """
    Finds a customer's ID by their full name.
    Args:
        customer_name (str): The full name of the customer to find.
    Output: The customer's ID as a string or an error message if not found.
    """
    try:
        with _db() as conn:
            ids = _customer_ids(conn, customer_name)
        if len(ids) == 0:
            return f"Error: Customer '{customer_name}' not found."
        if len(ids) > 1:
            return f"Error: Multiple customers found with the name '{customer_name}'. Please use a unique customer ID."
        return ids[0]
    except Exception as e:
        return f"Error finding customer: {str(e)}"


# --- complaint tools (complaints agent) --------------------------------------------------------------------


def create_complaint(customer_id: str, category: str, description: str, transaction_id: str = None):
    """
    Creates a new customer complaint.
    Args:
        customer_id (str): The ID of the customer.
        category (str): The type of issue (e.g., 'Dispute', 'Service', 'Fraud').
        description (str): The user's original complaint text.
        transaction_id (str, optional): The transaction ID if the complaint is about a specific charge.
    Output: The new complaint ID.
    """
    complaint_id = str(uuid.uuid4())
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO complaints (complaint_id, customer_id, transaction_id, complaint_date, category,"
                " description, status) VALUES (?, ?, ?, ?, ?, ?, 'Open')",
                (complaint_id, customer_id, transaction_id, date.today().isoformat(), category, description),
            )
        return f"Success: Complaint created with ID: {complaint_id}"
    except Exception as e:
        return f"Error creating complaint: {str(e)}"


def update_complaint(complaint_id: str, status: str = None, resolution_notes: str = None):
    """
    Updates an existing complaint's status or adds resolution notes.
    Args:
        complaint_id (str): The ID of the complaint to update.
        status (str, optional): The new status of the complaint (e.g., 'Pending', 'Resolved').
        resolution_notes (str, optional): Notes to add to the complaint's resolution.
    Output: A confirmation message.
    """
    if not status and not resolution_notes:
        return "Error: You must provide either a new status or resolution notes to update the complaint."

    set_clauses, params = [], []
    if status:
        set_clauses.append("status = ?")
        params.append(status)
    if resolution_notes:
        set_clauses.append("resolution_notes = ?")
        params.append(resolution_notes)
    params.append(complaint_id)

    try:
        with _db() as conn:
            cur = conn.execute(f"UPDATE complaints SET {', '.join(set_clauses)} WHERE complaint_id = ?", params)
        if cur.rowcount == 0:
            return f"Error: Complaint ID {complaint_id} not found. No update performed."
        return f"Success: Complaint {complaint_id} updated."
    except Exception as e:
        return f"Error updating complaint: {str(e)}"


def initiate_complaint_by_name(customer_name: str, category: str, description: str, transaction_id: str = None):
    """
    Initiates a new customer complaint by looking up the customer's name.
    Args:
        customer_name (str): The full name of the customer.
        category (str): The type of issue (e.g., 'Dispute', 'Service', 'Fraud').
        description (str): The user's original complaint text.
        transaction_id (str, optional): The transaction ID for 'Dispute' category complaints.
    Output: A confirmation message with the new complaint ID or an error message.
    """
    try:
        with _db() as conn:
            ids = _customer_ids(conn, customer_name)
        if len(ids) == 0:
            return f"Error: Customer '{customer_name}' not found."
        if len(ids) > 1:
            return f"Error: Multiple customers found with the name '{customer_name}'. Please provide a unique customer ID."
        return create_complaint(ids[0], category, description, transaction_id)
    except Exception as e:
        return f"Error looking up customer: {str(e)}"


# --- read-only SQL tools (bq_agent) ------------------------------------------------------------------------

_READ_ONLY_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


def list_table_ids() -> dict:
    """
    Lists the tables in the bank database.
    Output: A dict with the table names.
    """
    with _db(read_only=True) as conn:
        names = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    return {"status": "SUCCESS", "tables": names}


def get_table_info(table_id: str) -> dict:
    """
    Gets the columns of one table in the bank database.
    Args:
        table_id (str): The table name, for example 'customers'.
    Output: A dict with the column names and types.
    """
    with _db(read_only=True) as conn:
        known = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if table_id not in known:
            return {"status": "ERROR", "error_details": f"Table {table_id!r} not found."}
        # PRAGMA cannot take a bound parameter; table_id was checked against the real table names above.
        cols = [{"name": r["name"], "type": r["type"]} for r in conn.execute(f"PRAGMA table_info({table_id})")]
    return {"status": "SUCCESS", "table": table_id, "columns": cols}


def execute_sql(query: str) -> dict:
    """
    Runs a read-only SQL query (SQLite dialect) against the bank database.
    Args:
        query (str): A single SELECT statement.
    Output: A dict with the result rows, or an error.
    """
    if not _READ_ONLY_START.match(query):
        return {"status": "ERROR", "error_details": "Read-only mode only supports SELECT statements."}
    try:
        with _db(read_only=True) as conn:
            rows = [dict(r) for r in conn.execute(query).fetchmany(MAX_ROWS + 1)]
    except Exception as e:
        return {"status": "ERROR", "error_details": str(e)}
    result = {"status": "SUCCESS", "rows": rows[:MAX_ROWS]}
    if len(rows) > MAX_ROWS:
        result["result_is_likely_truncated"] = True
    return result


bigquery_agent = Agent(
    model=MODEL,
    name="bq_agent",
    description=(
        "A read-only agent to answer questions about customer records, accounts, and transactions"
    ),
    instruction="""
        You are a data science agent with access to read-only SQL tools to query customer accounts and transactions.

        Make use of those tools to answer the user's questions. The database is SQLite, so write SQLite SQL.

        You may query the following tables:
            - accounts
            - customers
            - transactions
            - complaints
            - advisor_locations
    """,
    tools=[list_table_ids, get_table_info, execute_sql],
)


# --- branch finder stand-in (navigator agent) --------------------------------------------------------------


def search_places(text_query: str) -> dict:
    """
    Searches for places matching a text query. Demo stand-in for the Google Maps search_places tool: it only
    knows the fictional Cymbal Bank Pop-Up Advisor locations in the demo database.
    Args:
        text_query (str): What to search for and where, for example 'Starbucks near 12 Sample Lane, Exampleton'.
    Output: A dict with matching places, nearest town first.
    """
    with _db(read_only=True) as conn:
        rows = [dict(r) for r in conn.execute("SELECT name, address, town, opening_hours FROM advisor_locations")]
    query = text_query.lower()
    in_town = [r for r in rows if r["town"].lower() in query]
    return {"places": in_town or rows}
