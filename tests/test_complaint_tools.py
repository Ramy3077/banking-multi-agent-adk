from types import SimpleNamespace

from conftest import params_of, sql_of

from customer_relationship_agent.complaints_agent import tools as ct

INJECTION = "x'; DROP TABLE complaints; --"


def test_create_complaint_inserts_with_parameters(bq_client):
    out = ct.create_complaint("C1", "Dispute", INJECTION, "T7")
    assert out.startswith("Success: Complaint created with ID: ")
    sql = sql_of(bq_client)
    assert sql.strip().startswith("INSERT INTO")
    assert "DROP TABLE" not in sql
    p = params_of(bq_client)
    assert p["customer_id"] == "C1" and p["category"] == "Dispute"
    assert p["description"] == INJECTION and p["transaction_id"] == "T7"
    assert p["complaint_id"] in out


def test_create_complaint_without_transaction_id(bq_client):
    ct.create_complaint("C1", "Service", "slow")
    assert params_of(bq_client)["transaction_id"] is None


def test_create_complaint_error_is_returned_as_text(bq_client):
    bq_client.query.side_effect = RuntimeError("quota")
    assert ct.create_complaint("C1", "Fraud", "x") == "Error creating complaint: quota"


def test_update_complaint_requires_a_field(bq_client):
    assert ct.update_complaint("K1").startswith("Error")
    bq_client.query.assert_not_called()


def test_update_complaint_status_only(bq_client):
    bq_client.query.return_value.num_dml_affected_rows = 1
    assert ct.update_complaint("K1", status="Resolved").startswith("Success")
    sql = sql_of(bq_client)
    assert "status = @status" in sql and "resolution_notes" not in sql
    assert params_of(bq_client) == {"status": "Resolved", "complaint_id": "K1"}


def test_update_complaint_both_fields(bq_client):
    bq_client.query.return_value.num_dml_affected_rows = 1
    ct.update_complaint("K1", status="Resolved", resolution_notes=INJECTION)
    sql = sql_of(bq_client)
    assert "status = @status, resolution_notes = @resolution_notes" in sql
    assert "DROP TABLE" not in sql
    assert params_of(bq_client)["resolution_notes"] == INJECTION


def test_update_complaint_waits_for_job_and_reports_missing_id(bq_client):
    bq_client.query.return_value.num_dml_affected_rows = 0
    assert "not found" in ct.update_complaint("K404", status="Pending")
    bq_client.query.return_value.result.assert_called_once()


def test_update_complaint_error_is_returned_as_text(bq_client):
    bq_client.query.side_effect = RuntimeError("nope")
    assert ct.update_complaint("K1", status="Pending") == "Error updating complaint: nope"


def test_initiate_by_name_creates_complaint_for_unique_customer(bq_client):
    job = bq_client.query.return_value
    job.result.return_value = [SimpleNamespace(customer_id="C5")]
    out = ct.initiate_complaint_by_name("Ceri Jonas", "Service", "late card")
    assert out.startswith("Success")
    assert bq_client.query.call_count == 2
    assert params_of(bq_client)["customer_id"] == "C5"


def test_initiate_by_name_unknown_customer(bq_client):
    bq_client.query.return_value.result.return_value = []
    assert "not found" in ct.initiate_complaint_by_name("Nobody", "Service", "x")
    assert bq_client.query.call_count == 1


def test_initiate_by_name_ambiguous_customer(bq_client):
    bq_client.query.return_value.result.return_value = [
        SimpleNamespace(customer_id="C1"),
        SimpleNamespace(customer_id="C2"),
    ]
    assert "Multiple customers" in ct.initiate_complaint_by_name("Sam Lee", "Service", "x")
    assert bq_client.query.call_count == 1
