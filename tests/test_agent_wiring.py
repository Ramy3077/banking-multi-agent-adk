import os

from customer_relationship_agent.agent import root_agent


def test_root_delegates_to_two_sub_agents():
    assert [a.name for a in root_agent.sub_agents] == ["complaints_handler", "navigator_agent"]


def test_prompts_only_name_tools_the_agents_have():
    by_name = {a.name: a for a in root_agent.sub_agents}
    complaints = by_name["complaints_handler"]
    tool_names = {getattr(t, "name", getattr(t, "__name__", None)) for t in complaints.tools}
    prompt = complaints.instruction
    for name in ("initiate_complaint_by_name", "update_complaint", "find_customer_by_name", "bq_agent"):
        assert name in tool_names
    for name in ("initiate_complaint_by_name", "find_customer_by_name", "bq_agent"):
        assert name in prompt
    assert "create_complaint" not in prompt


def test_default_backend_is_bigquery_on_gemini_2_5_flash():
    from customer_relationship_agent import backend, tools

    if "BANK_BACKEND" not in os.environ:
        assert backend.USE_SQLITE is False
        assert root_agent.tools[0].agent is tools.bigquery_agent
    if "BANK_MODEL" not in os.environ:
        assert {root_agent.model, *(a.model for a in root_agent.sub_agents)} == {"gemini-2.5-flash"}
