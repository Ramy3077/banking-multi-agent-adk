import os
from pathlib import Path
from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool import McpTool, StreamableHTTPConnectionParams
from ..tools import bigquery_agent

# Read the system prompt from the PROMPT.md file
prompt_file = Path(__file__).parent / "PROMPT.md"
with open(prompt_file, "r") as f:
    SYSTEM_PROMPT = f.read()

# Configure the Maps MCP tool
maps_tool_params = StreamableHTTPConnectionParams(
    host="mapstools.googleapis.com",
    headers={"X-Goog-Api-Key": os.environ.get("GOOGLE_MAPS_API_KEY", "")}
)
maps_mcp_tool = McpTool(
    connection_params=maps_tool_params,
    filter_tool_names=["search_places"]
)

navigator_agent = Agent(
    model="gemini-2.5-flash",
    name="navigator_agent",
    description="Helps users find their nearest Cymbal Bank branch or Pop-Up Advisor.",
    instruction=SYSTEM_PROMPT,
    tools=[
        AgentTool(agent=bigquery_agent),
        maps_mcp_tool,
    ],
)
