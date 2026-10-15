from unittest.mock import MagicMock

import pytest


@pytest.fixture
def bq_client(monkeypatch):
    """Patch bigquery.Client in both tool modules and return the shared mock client."""
    from customer_relationship_agent import tools
    from customer_relationship_agent.complaints_agent import tools as complaint_tools

    client = MagicMock()
    monkeypatch.setattr(tools.bigquery, "Client", MagicMock(return_value=client))
    monkeypatch.setattr(complaint_tools.bigquery, "Client", MagicMock(return_value=client))
    return client


def params_of(client):
    """Return {name: value} for the query parameters of the last client.query call."""
    job_config = client.query.call_args.kwargs["job_config"]
    return {p.name: p.value for p in job_config.query_parameters}


def sql_of(client):
    return client.query.call_args.args[0]
