from pathlib import Path
from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool
from ..tools import bigquery_agent, find_customer_by_name
from .tools import initiate_complaint_by_name, update_complaint

# Read the system prompt from the PROMPT.md file
prompt_file = Path(__file__).parent / "PROMPT.md"
with open(prompt_file, "r") as f:
    SYSTEM_PROMPT = f.read()

complaints_agent = Agent(
    model="gemini-2.5-flash",
    name="complaints_handler",
    description="A complaints handler, dedicated to creating, updating, resolving, and handling customer complaint cases",
    instruction=SYSTEM_PROMPT,
    tools=[
        AgentTool(agent=bigquery_agent),
        initiate_complaint_by_name,
        update_complaint,
        find_customer_by_name
    ],
)
