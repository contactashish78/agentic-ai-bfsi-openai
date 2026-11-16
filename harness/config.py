"""Central configuration: model string, paths, limits. Values come from .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

# aisuite model strings are "provider:model", e.g. "openai:gpt-4o-mini"
MODEL = os.getenv("MODEL", "openai:gpt-4o-mini")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "6"))  # max LLM calls per user turn

DATA_FILE = ROOT / "data" / "loans.json"
SKILLS_DIR = Path(__file__).resolve().parent / "skills"
AUDIT_FILE = ROOT / "logs" / "audit.jsonl"


def get_client():
    """Return an aisuite client. Kept in one place so tests can swap in a fake."""
    import aisuite as ai

    return ai.Client()
