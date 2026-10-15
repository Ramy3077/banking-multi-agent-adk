"""Run the real agent on the SQLite demo backend and save each conversation's ADK event stream as JSON.

    BANK_BACKEND=sqlite GOOGLE_GENAI_USE_VERTEXAI=FALSE GOOGLE_API_KEY=... uv run python scripts/record_sessions.py

Each scenario starts from a freshly seeded database. A plugin records every event the runner emits, including
the events of bq_agent, which runs inside an AgentTool with the parent's plugins. The files in demo/sessions/
are what the static replay viewer in demo/ plays back.
"""

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

if os.environ.get("BANK_BACKEND") != "sqlite":
    sys.exit("Set BANK_BACKEND=sqlite; this script only records against the fictional demo data.")

from google.adk.plugins.base_plugin import BasePlugin  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from customer_relationship_agent.agent import root_agent  # noqa: E402
from customer_relationship_agent.demo_backend import tools as demo  # noqa: E402

OUT_DIR = REPO / "demo" / "sessions"
MODEL = root_agent.model

SCENARIOS = [
    {
        "id": "customer-lookup",
        "title": "Customer lookup",
        "summary": "A free-form question about one customer's spending, answered through bq_agent.",
        "turns": ["Show me Alex Example's transactions from October 2026."],
        "after": [("Alex Example's October transactions in the database", "SELECT t.transaction_id, t.transaction_date, t.merchant, t.amount FROM transactions t JOIN accounts a USING (account_id) JOIN customers c USING (customer_id) WHERE c.name = 'Alex Example' AND t.transaction_date >= '2026-10-01' ORDER BY t.transaction_date")],
    },
    {
        "id": "update-phone",
        "title": "Update a phone number",
        "summary": "A write through the root agent's update_customer_phone_by_name tool.",
        "turns": ["Sam Sample has a new phone number: 01632 960 999. Please update it."],
        "after": [("Sam Sample's phone number after the run", "SELECT customer_id, name, phone FROM customers WHERE name = 'Sam Sample'")],
    },
    {
        "id": "ambiguous-name",
        "title": "Two customers, one name",
        "summary": "The phone update refuses to guess when a name matches two customers.",
        "turns": ["Change Chris Duplicate's phone number to 01632 960 555."],
        "after": [("Both Chris Duplicate records after the run", "SELECT customer_id, name, phone FROM customers WHERE name = 'Chris Duplicate'")],
    },
    {
        "id": "raise-complaint",
        "title": "Raise a complaint",
        "summary": "Handoff to complaints_handler, which checks for open complaints, finds the transaction and asks before writing.",
        "turns": [
            "I'm Alex Example. I was charged twice at Gadget Barn on 3 October, 89.99 each time. I want to raise a complaint.",
            "Yes, that's correct. Please create the complaint.",
        ],
        "after": [("Alex Example's complaints after the run", "SELECT complaint_id, transaction_id, category, status, description FROM complaints WHERE customer_id = 'CUST-1001'")],
    },
    {
        "id": "nearest-advisor",
        "title": "Find the nearest advisor",
        "summary": "Handoff to navigator_agent, which looks up the customer's address and searches for nearby Pop-Up Advisors.",
        "turns": ["I'm Priya Testwell. Where is the nearest Cymbal Bank advisor to my home?"],
        "after": [],
    },
    {
        "id": "out-of-scope",
        "title": "Out-of-scope request",
        "summary": "Investment advice and an off-topic request, which the root prompt says to decline.",
        "turns": ["Which shares should I buy with my savings to double them by Christmas?"],
        "after": [],
    },
]


def _jsonable(value):
    return json.loads(json.dumps(value, default=str))


class Recorder(BasePlugin):
    """Keeps every event the runner emits, from the root runner and from AgentTool sub-runners."""

    def __init__(self):
        super().__init__(name="session_recorder")
        self.events = []
        self.t0 = time.monotonic()
        self.turn = 0

    async def on_event_callback(self, *, invocation_context, event):
        parts = []
        for part in (event.content.parts if event.content and event.content.parts else []):
            if part.thought:
                continue
            if part.function_call:
                parts.append({"type": "function_call", "id": part.function_call.id, "name": part.function_call.name,
                              "args": _jsonable(part.function_call.args or {})})
            elif part.function_response:
                parts.append({"type": "function_response", "id": part.function_response.id,
                              "name": part.function_response.name,
                              "response": _jsonable(part.function_response.response or {})})
            elif part.text:
                parts.append({"type": "text", "text": part.text})
        record = {
            "turn": self.turn,
            "t_ms": round((time.monotonic() - self.t0) * 1000),
            "author": event.author,
            "invocation_id": event.invocation_id,
            "parts": parts,
        }
        if event.actions and event.actions.transfer_to_agent:
            record["transfer_to_agent"] = event.actions.transfer_to_agent
        if event.error_code:
            record["error"] = {"code": event.error_code, "message": event.error_message}
        if parts or "transfer_to_agent" in record or "error" in record:
            self.events.append(record)
        return None


def snapshot(queries):
    out = []
    conn = sqlite3.connect(demo.db_path())
    conn.row_factory = sqlite3.Row
    try:
        for label, sql in queries:
            out.append({"label": label, "sql": sql, "rows": [dict(r) for r in conn.execute(sql)]})
    finally:
        conn.close()
    return out


async def send(runner, session, text):
    message = types.Content(role="user", parts=[types.Part(text=text)])
    async for _ in runner.run_async(user_id=session.user_id, session_id=session.id, new_message=message):
        pass


TRANSIENT = ("429", "500", "503", "504", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED")


async def record_with_retries(scenario, attempts=4):
    """Re-run the whole scenario from a fresh database if the API has a transient failure mid-conversation."""
    for attempt in range(attempts):
        try:
            return await record(scenario)
        except Exception as e:
            daily_quota_gone = "PerDay" in str(e)
            if daily_quota_gone or not any(code in str(e) for code in TRANSIENT) or attempt == attempts - 1:
                raise
            wait = 20 * (attempt + 1)
            print(f"  transient API error ({str(e)[:60]}), restarting scenario in {wait}s", flush=True)
            await asyncio.sleep(wait)


async def record(scenario):
    demo.reset_db()
    recorder = Recorder()
    runner = InMemoryRunner(agent=root_agent, app_name="customer_relationship_agent", plugins=[recorder])
    session = await runner.session_service.create_session(app_name=runner.app_name, user_id="demo-user")
    started = datetime.now(timezone.utc)
    transcript = []
    for i, text in enumerate(scenario["turns"], start=1):
        recorder.turn = i
        recorder.events.append({"turn": i, "t_ms": round((time.monotonic() - recorder.t0) * 1000), "author": "user",
                                "parts": [{"type": "text", "text": text}]})
        await send(runner, session, text)
        transcript.append(text)
    await runner.close()
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "summary": scenario["summary"],
        "model": MODEL,
        "backend": "sqlite (fictional demo data)",
        "recorded_at": started.isoformat(timespec="seconds"),
        "events": recorder.events,
        "database_after": snapshot(scenario["after"]),
    }


async def main(only):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    for scenario in SCENARIOS:
        path = OUT_DIR / f"{scenario['id']}.json"
        if only and scenario["id"] not in only:
            if path.exists():
                index.append(json.loads(path.read_text()))
            continue
        print(f"recording {scenario['id']}", flush=True)
        session = await record_with_retries(scenario)
        path.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n")
        index.append(session)
    manifest = [{"id": s["id"], "title": s["title"], "summary": s["summary"], "recorded_at": s["recorded_at"],
                 "model": s["model"], "file": f"sessions/{s['id']}.json"} for s in index]
    (OUT_DIR / "index.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("only", nargs="*", help="scenario ids to re-record (default: all)")
    asyncio.run(main(set(parser.parse_args().only)))
