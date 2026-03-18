from pathlib import Path
from google.adk.agents.llm_agent import Agent
# Import the AgentTool helper
from google.adk.tools.agent_tool import AgentTool
# Import your customer record tool
from .tools import bigquery_agent, update_customer_phone_by_name, find_customer_by_name
# Import complaints agent
from .complaints_agent.complaints import complaints_agent
from .navigator_agent.navigator import navigator_agent


# Read the system prompt from the PROMPT.md file
prompt_file = Path(__file__).parent / "PROMPT.md"
with open(prompt_file, "r") as f:
    SYSTEM_PROMPT = f.read()

root_agent = Agent(
    model='gemini-2.5-flash',
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

