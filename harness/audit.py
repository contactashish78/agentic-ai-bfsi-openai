"""Append-only JSONL audit log: one line per agent action, PII already masked."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import config


class AuditLog:
    def __init__(self, session_id: str, path: Path | None = None):
        self.session_id = session_id
        self.path = path or config.AUDIT_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: dict) -> dict:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": self.session_id,
            **event,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def read(self, session_only: bool = True, limit: int = 200) -> list[dict]:
        if not self.path.exists():
            return []
        rows = [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if session_only:
            rows = [r for r in rows if r.get("session_id") == self.session_id]
        return rows[-limit:]
