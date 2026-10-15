from types import SimpleNamespace

from conftest import params_of, sql_of

from customer_relationship_agent import tools

INJECTION = "x'; DROP TABLE customers; --"


def rows(*ids):
    return [SimpleNamespace(customer_id=i) for i in ids]


def test_find_customer_returns_id(bq_client):
    bq_client.query.return_value.result.return_value = rows("C1")
    assert tools.find_customer_by_name("Ceri Jonas") == "C1"
    assert "WHERE name = @name" in sql_of(bq_client)
    assert params_of(bq_client) == {"name": "Ceri Jonas"}


def test_find_customer_not_found(bq_client):
    bq_client.query.return_value.result.return_value = []
    assert "not found" in tools.find_customer_by_name("Nobody")


def test_find_customer_ambiguous(bq_client):
    bq_client.query.return_value.result.return_value = rows("C1", "C2")
    assert "Multiple customers" in tools.find_customer_by_name("Sam Lee")


def test_find_customer_name_is_parameterised_not_interpolated(bq_client):
    bq_client.query.return_value.result.return_value = []
    tools.find_customer_by_name(INJECTION)
    assert "DROP TABLE" not in sql_of(bq_client)
    assert params_of(bq_client)["name"] == INJECTION


def test_find_customer_error_is_returned_as_text(bq_client):
    bq_client.query.side_effect = RuntimeError("boom")
    assert tools.find_customer_by_name("A B") == "Error finding customer: boom"


def test_update_phone_builds_parameterised_update(bq_client):
    bq_client.query.return_value.num_dml_affected_rows = 1
    out = tools.bq_update_customer_phone_number("C1", INJECTION)
    assert out.startswith("Success")
    sql = sql_of(bq_client)
    assert "SET phone = @new_phone" in sql and "WHERE customer_id = @cid" in sql
    assert "DROP TABLE" not in sql
    assert params_of(bq_client) == {"new_phone": INJECTION, "cid": "C1"}


def test_update_phone_waits_for_job_before_reading_row_count(bq_client):
    bq_client.query.return_value.num_dml_affected_rows = 1
    tools.bq_update_customer_phone_number("C1", "123")
    bq_client.query.return_value.result.assert_called_once()


def test_update_phone_unknown_customer(bq_client):
    bq_client.query.return_value.num_dml_affected_rows = 0
    assert "not found" in tools.bq_update_customer_phone_number("C404", "123")


def test_update_phone_error_is_returned_as_text(bq_client):
    bq_client.query.side_effect = RuntimeError("denied")
    assert tools.bq_update_customer_phone_number("C1", "123") == "Error updating record: denied"


def test_update_by_name_looks_up_then_updates(bq_client):
    lookup = bq_client.query.return_value
    lookup.result.return_value = rows("C9")
    lookup.num_dml_affected_rows = 1
    out = tools.update_customer_phone_by_name("Ceri Jonas", "555")
    assert out.startswith("Success") and "C9" in out
    assert bq_client.query.call_count == 2


def test_update_by_name_does_not_update_when_ambiguous(bq_client):
    bq_client.query.return_value.result.return_value = rows("C1", "C2")
    out = tools.update_customer_phone_by_name("Sam Lee", "555")
    assert "Multiple customers" in out
    assert bq_client.query.call_count == 1


def test_update_by_name_not_found(bq_client):
    bq_client.query.return_value.result.return_value = []
    assert "not found" in tools.update_customer_phone_by_name("Nobody", "555")
    assert bq_client.query.call_count == 1


def test_bigquery_toolset_is_read_only():
    from google.adk.tools.bigquery.config import WriteMode

    assert tools.tool_config.write_mode == WriteMode.BLOCKED
