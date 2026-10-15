"""Pick the data backend for the agents.

BANK_BACKEND=bigquery (the default) uses the BigQuery tools in tools.py and complaints_agent/tools.py.
BANK_BACKEND=sqlite swaps in the demo backend in demo_backend/, which serves the same tool names and
signatures from a local SQLite file seeded with fictional data.
"""

import os

BACKEND = os.environ.get("BANK_BACKEND", "bigquery").strip().lower()

if BACKEND not in ("bigquery", "sqlite"):
    raise ValueError(f"BANK_BACKEND must be 'bigquery' or 'sqlite', got {BACKEND!r}")

USE_SQLITE = BACKEND == "sqlite"

# Gemini model for every agent. gemini-2.5-flash is what the project was built on; BANK_MODEL lets you pick
# another one, for example when an API key cannot use 2.5 Flash.
MODEL = os.environ.get("BANK_MODEL", "gemini-2.5-flash")
