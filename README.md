# Banking Multi-Agent System (Google ADK)

A multi-agent customer relationship assistant for a retail bank, built on the
[Google Agent Development Kit](https://google.github.io/adk-docs/) with Gemini 2.5 Flash and BigQuery.

A root agent handles the conversation and dispatches to specialised sub-agents rather than trying to do
everything in one prompt. Built to learn how agent delegation, tool calling and evaluation actually work
in practice, using Google's fictional "Cymbal Bank" sample dataset.

## Structure

```
customer_relationship_agent/
├── agent.py              root agent - routing and delegation
├── PROMPT.md             root persona and guardrails
├── tools.py              BigQuery access, customer lookup, record updates
├── complaints_agent/     complaint intake and classification
└── navigator_agent/      product and service navigation
```

Each agent keeps its system prompt in its own `PROMPT.md`, loaded at construction. Keeping prompts out of
the Python made them much easier to iterate on than editing string literals.

## How it works

**Delegation.** The root agent exposes its sub-agents as tools via ADK's `AgentTool`, so routing is a tool
call the model makes rather than branching logic I wrote. Adding a capability means adding an agent, not
extending a router.

**Grounded in data.** `tools.py` wires in BigQuery so the agent answers from transaction records instead
of improvising: lookup by customer name, transaction history, and record updates.

**Guardrails in the prompt.** No financial advice, never request or repeat credentials, keep scope to
banking, and render transaction data as Markdown tables so replies stay scannable.

**Evaluation.** `information_lookup.evalset.json` is an ADK evalset, so prompt changes can be checked
against expected tool-call behaviour rather than judged by eye.

## Running it

```bash
uv sync
uv run adk web          # ADK dev UI
```

Needs Google Cloud credentials with BigQuery access and a Gemini API key in the environment.

## Stack

Python 3.12, Google ADK, Gemini 2.5 Flash, Google Cloud BigQuery, pandas, uv.

---

Built by [Ramy Mekhzer](https://github.com/Ramy3077) - MEng Computer Science & Software Engineering, University of Birmingham.
