"""Minimal inbound admission record, not a Hermes memory backend."""
import json
from dataclasses import asdict
from pathlib import Path
import sqlite3
import uuid

from .types import ExecutionRequest, ExecutionResult, ExecutionUncertain


class Ledger:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        path.chmod(0o600)
        self.db.execute("CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT)")
        # CREATE TABLE and schema migration share SQLite's transaction boundary.
        self.db.execute("""CREATE TABLE IF NOT EXISTS hermes_sessions (
            profile TEXT NOT NULL, project_id TEXT NOT NULL, channel_id TEXT NOT NULL,
            origin_id TEXT NOT NULL, current_id TEXT NOT NULL,
            PRIMARY KEY (profile, project_id, channel_id))""")
        self.db.commit()

    def session(self, profile: str, project_id: str, channel_id: str) -> tuple[str, str]:
        """Return stable origin/current IDs, creating the durable lineage once."""
        identity = json.dumps([profile, project_id, channel_id], separators=(",", ":"))
        origin = "ag2-" + uuid.uuid5(uuid.NAMESPACE_URL, identity).hex
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO hermes_sessions VALUES (?,?,?,?,?)",
                            (profile, project_id, channel_id, origin, origin))
            row = self.db.execute("SELECT origin_id,current_id FROM hermes_sessions WHERE profile=? AND project_id=? AND channel_id=?",
                                  (profile, project_id, channel_id)).fetchone()
        return row[0], row[1]

    def advance_session(self, profile: str, project_id: str, channel_id: str, current_id: str):
        with self.db:
            self.db.execute("UPDATE hermes_sessions SET current_id=? WHERE profile=? AND project_id=? AND channel_id=?",
                            (current_id, profile, project_id, channel_id))

    def admit(self, request: ExecutionRequest) -> ExecutionResult | None:
        # Session IDs are derived from the durable channel lineage, not from
        # the operation payload. Exclude them so replaying an already-finished
        # operation after rotation remains an idempotent read of its result.
        payload = json.dumps({key: getattr(request, key) for key in (
            "profile", "project_id", "channel_id", "operation_id", "text",
        )}, sort_keys=True)
        with self.db:
            row = self.db.execute("SELECT payload,result FROM operations WHERE id=?", (request.operation_id,)).fetchone()
            if row:
                if row[0] != payload:
                    raise ValueError("operation_id reused with different input")
                if row[1] is None:
                    raise ExecutionUncertain("prior execution unsettled; explicit operator reconciliation required")
                return ExecutionResult(**json.loads(row[1]))
            self.db.execute("INSERT INTO operations VALUES (?,?,NULL)", (request.operation_id, payload))
        return None

    def finish(self, operation_id: str, result: ExecutionResult):
        with self.db:
            self.db.execute("UPDATE operations SET result=? WHERE id=?", (json.dumps(asdict(result)), operation_id))

    def close(self):
        self.db.close()
