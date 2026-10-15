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
