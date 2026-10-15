import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from customer_relationship_agent.demo_backend import tools as st

REPO = Path(__file__).resolve().parents[1]
INJECTION = "x'; DROP TABLE customers; --"


@pytest.fixture(autouse=True)
def demo_db(tmp_path, monkeypatch):
    """Point the demo backend at a fresh seeded database for every test."""
    monkeypatch.setenv("BANK_SQLITE_PATH", str(tmp_path / "bank.db"))
    return st.reset_db()


def query(sql, *params):
    conn = sqlite3.connect(st.db_path())
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def table_count(name):
    return query(f"SELECT COUNT(*) FROM {name}")[0][0]


# --- customer tools ---


def test_find_customer_returns_id():
    assert st.find_customer_by_name("Alex Example") == "CUST-1001"


def test_find_customer_not_found():
    assert "not found" in st.find_customer_by_name("Nobody")


def test_find_customer_ambiguous():
    assert "Multiple customers" in st.find_customer_by_name("Chris Duplicate")


def test_find_customer_name_is_parameterised_not_interpolated():
    assert "not found" in st.find_customer_by_name(INJECTION)
    assert table_count("customers") == 7


def test_update_phone_by_id():
    out = st.bq_update_customer_phone_number("CUST-1002", INJECTION)
    assert out.startswith("Success")
    assert query("SELECT phone FROM customers WHERE customer_id = ?", "CUST-1002") == [(INJECTION,)]
    assert table_count("customers") == 7


def test_update_phone_unknown_customer():
    assert "not found" in st.bq_update_customer_phone_number("CUST-404", "123")


def test_update_by_name_looks_up_then_updates():
    out = st.update_customer_phone_by_name("Sam Sample", "01632 960 999")
    assert out.startswith("Success") and "CUST-1002" in out
    assert query("SELECT phone FROM customers WHERE name = ?", "Sam Sample") == [("01632 960 999",)]


def test_update_by_name_does_not_update_when_ambiguous():
    out = st.update_customer_phone_by_name("Chris Duplicate", "555")
    assert "Multiple customers" in out
    assert query("SELECT COUNT(*) FROM customers WHERE phone = '555'") == [(0,)]


def test_update_by_name_not_found():
    assert "not found" in st.update_customer_phone_by_name("Nobody", "555")


# --- complaint tools ---


def test_create_complaint_inserts_open_complaint():
    out = st.create_complaint("CUST-1001", "Dispute", INJECTION, "TXN-3005")
    assert out.startswith("Success: Complaint created with ID: ")
    cid = out.rsplit(" ", 1)[1]
    assert query("SELECT customer_id, transaction_id, category, description, status FROM complaints WHERE complaint_id = ?", cid) == [
        ("CUST-1001", "TXN-3005", "Dispute", INJECTION, "Open")
    ]


def test_create_complaint_without_transaction_id():
    cid = st.create_complaint("CUST-1001", "Service", "slow").rsplit(" ", 1)[1]
    assert query("SELECT transaction_id FROM complaints WHERE complaint_id = ?", cid) == [(None,)]


def test_update_complaint_requires_a_field():
    assert st.update_complaint("CMP-0001").startswith("Error")


def test_update_complaint_status_only():
    assert st.update_complaint("CMP-0001", status="Pending").startswith("Success")
    assert query("SELECT status, resolution_notes FROM complaints WHERE complaint_id = 'CMP-0001'") == [("Pending", None)]


def test_update_complaint_both_fields():
    st.update_complaint("CMP-0001", status="Resolved", resolution_notes=INJECTION)
    assert query("SELECT status, resolution_notes FROM complaints WHERE complaint_id = 'CMP-0001'") == [("Resolved", INJECTION)]


def test_update_complaint_reports_missing_id():
    assert "not found" in st.update_complaint("CMP-404", status="Pending")


def test_initiate_by_name_creates_complaint_for_unique_customer():
    before = table_count("complaints")
    assert st.initiate_complaint_by_name("Alex Example", "Service", "late card").startswith("Success")
    assert table_count("complaints") == before + 1


def test_initiate_by_name_unknown_customer():
    before = table_count("complaints")
    assert "not found" in st.initiate_complaint_by_name("Nobody", "Service", "x")
    assert table_count("complaints") == before


def test_initiate_by_name_ambiguous_customer():
    before = table_count("complaints")
    assert "Multiple customers" in st.initiate_complaint_by_name("Chris Duplicate", "Service", "x")
    assert table_count("complaints") == before


# --- read-only SQL tools ---


def test_execute_sql_returns_rows():
    out = st.execute_sql("SELECT name, phone FROM customers WHERE email = 'ceri_jonas@example.org'")
    assert out == {"status": "SUCCESS", "rows": [{"name": "Ceri Jonas", "phone": "01234 567 890"}]}


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "UPDATE customers SET phone = '1'",
        "DROP TABLE customers",
        "INSERT INTO complaints VALUES ('a','b',NULL,'d','e','f','g',NULL)",
    ],
)
def test_execute_sql_rejects_writes(sql):
    assert st.execute_sql(sql)["status"] == "ERROR"
    assert table_count("customers") == 7


def test_execute_sql_connection_is_read_only_even_after_a_select():
    out = st.execute_sql("SELECT 1; DELETE FROM customers")
    assert out["status"] == "ERROR"
    assert table_count("customers") == 7


def test_execute_sql_caps_rows():
    out = st.execute_sql("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 80) SELECT i FROM n")
    assert len(out["rows"]) == st.MAX_ROWS and out["result_is_likely_truncated"]


def test_execute_sql_error_is_returned():
    assert st.execute_sql("SELECT * FROM nope")["status"] == "ERROR"


def test_table_metadata():
    assert "customers" in st.list_table_ids()["tables"]
    cols = [c["name"] for c in st.get_table_info("complaints")["columns"]]
    assert cols == ["complaint_id", "customer_id", "transaction_id", "complaint_date", "category", "description", "status", "resolution_notes"]
    assert st.get_table_info("customers); DROP TABLE customers; --")["status"] == "ERROR"


def test_search_places_filters_by_town():
    towns = {p["town"] for p in st.search_places("Starbucks near 7 Fixture Close, Testbury")["places"]}
    assert towns == {"Testbury"}


# --- wiring under BANK_BACKEND=sqlite (fresh interpreter, so the BigQuery-default imports above are untouched) ---


def test_agents_use_sqlite_tools_when_selected():
    code = """
import json
from customer_relationship_agent.agent import root_agent
def names(agent):
    return sorted(getattr(t, "name", getattr(t, "__name__", type(t).__name__)) for t in agent.tools)
subs = {a.name: a for a in root_agent.sub_agents}
bq = root_agent.tools[0].agent
print(json.dumps({
    "root": names(root_agent),
    "complaints": names(subs["complaints_handler"]),
    "navigator": names(subs["navigator_agent"]),
    "bq": names(bq),
    "bq_module": bq.tools[0].__module__,
}))
"""
    env = {**os.environ, "BANK_BACKEND": "sqlite"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True, cwd=REPO)
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["root"] == ["bq_agent", "find_customer_by_name", "update_customer_phone_by_name"]
    assert got["complaints"] == ["bq_agent", "find_customer_by_name", "initiate_complaint_by_name", "update_complaint"]
    assert got["navigator"] == ["bq_agent", "search_places"]
    assert got["bq"] == ["execute_sql", "get_table_info", "list_table_ids"]
    assert got["bq_module"] == "customer_relationship_agent.demo_backend.tools"


def test_unknown_backend_is_rejected():
    env = {**os.environ, "BANK_BACKEND": "postgres"}
    out = subprocess.run([sys.executable, "-c", "import customer_relationship_agent.agent"], env=env, capture_output=True, text=True, cwd=REPO)
    assert out.returncode != 0 and "BANK_BACKEND" in out.stderr
