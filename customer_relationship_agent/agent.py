from pathlib import Path

from google.adk.agents.llm_agent import Agent

# Import the AgentTool helper
from google.adk.tools.agent_tool import AgentTool

from .backend import MODEL, USE_SQLITE

# Import complaints agent
from .complaints_agent.complaints import complaints_agent
from .navigator_agent.navigator import navigator_agent

# Import your customer record tool (BigQuery by default, the SQLite demo backend if BANK_BACKEND=sqlite)
if USE_SQLITE:
    from .demo_backend.tools import bigquery_agent, find_customer_by_name, update_customer_phone_by_name
else:
    from .tools import bigquery_agent, find_customer_by_name, update_customer_phone_by_name

# Read the system prompt from the PROMPT.md file
prompt_file = Path(__file__).parent / "PROMPT.md"
with open(prompt_file, "r") as f:
    SYSTEM_PROMPT = f.read()

root_agent = Agent(
    model=MODEL,
    name='root_agent',
    description='The root agent for customer relationship management at Cymbal Bank, capable of dispatching tasks to specialized sub-agents.',
    instruction=SYSTEM_PROMPT,
    sub_agents=[
        complaints_agent,
        navigator_agent
    ],
    tools=[
        AgentTool(bigquery_agent),
        update_customer_phone_by_name,
        find_customer_by_name
    ],
)

