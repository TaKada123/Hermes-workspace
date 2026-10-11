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
        self.db.execute("""CREATE TABLE IF NOT EXISTS scoped_operations (
            profile TEXT NOT NULL, project_id TEXT NOT NULL, channel_id TEXT NOT NULL,
            operation_id TEXT NOT NULL, payload TEXT NOT NULL, result TEXT,
            PRIMARY KEY (profile, project_id, channel_id, operation_id))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS hermes_sessions (
            profile TEXT NOT NULL, project_id TEXT NOT NULL, channel_id TEXT NOT NULL,
            origin_id TEXT NOT NULL, current_id TEXT NOT NULL,
            PRIMARY KEY (profile, project_id, channel_id))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS project_channels (
            profile TEXT NOT NULL, peer TEXT NOT NULL, project_id TEXT NOT NULL,
            channel_id TEXT NOT NULL, PRIMARY KEY (profile, peer, project_id))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS terminal_recovery_notices (
            profile TEXT NOT NULL, project_id TEXT NOT NULL, channel_id TEXT NOT NULL,
            request_id TEXT NOT NULL, operation_id TEXT NOT NULL,
            PRIMARY KEY (profile, project_id, channel_id, request_id))""")
        with self.db:
            legacy_rows = self.db.execute("SELECT payload,result FROM operations").fetchall()
            for payload, result in legacy_rows:
                scope = json.loads(payload)
                self.db.execute(
                    "INSERT OR IGNORE INTO scoped_operations "
                    "(profile,project_id,channel_id,operation_id,payload,result) VALUES (?,?,?,?,?,?)",
                    (scope["profile"], scope["project_id"], scope["channel_id"],
                     scope["operation_id"], payload, result))
        self.db.commit()

    def channel(self, profile: str, peer: str, project_id: str) -> str | None:
        row = self.db.execute("SELECT channel_id FROM project_channels WHERE profile=? AND peer=? AND project_id=?",
                              (profile, peer, project_id)).fetchone()
        return row[0] if row else None

    def remember_channel(self, profile: str, peer: str, project_id: str, channel_id: str):
        with self.db:
            self.db.execute("INSERT INTO project_channels VALUES (?,?,?,?) "
                            "ON CONFLICT(profile,peer,project_id) DO UPDATE SET channel_id=excluded.channel_id",
                            (profile, peer, project_id, channel_id))

    def forget_channel(self, profile: str, peer: str, project_id: str):
        with self.db:
            self.db.execute("DELETE FROM project_channels WHERE profile=? AND peer=? AND project_id=?",
                            (profile, peer, project_id))

    def note_terminal_request(self, profile: str, project_id: str, channel_id: str,
                              request_id: str, operation_id: str):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO terminal_recovery_notices VALUES (?,?,?,?,?)",
                            (profile, project_id, channel_id, request_id, operation_id))

    def terminal_requests(self, profile: str, project_id: str) -> list[tuple[str, str, str]]:
        rows = self.db.execute(
            "SELECT channel_id,request_id,operation_id FROM terminal_recovery_notices "
            "WHERE profile=? AND project_id=? ORDER BY rowid", (profile, project_id)).fetchall()
        return [(row[0], row[1], row[2]) for row in rows]

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
        scope = (request.profile, request.project_id, request.channel_id, request.operation_id)
        with self.db:
            row = self.db.execute(
                "SELECT payload,result FROM scoped_operations "
                "WHERE profile=? AND project_id=? AND channel_id=? AND operation_id=?", scope).fetchone()
            if row:
                if row[0] != payload:
                    raise ValueError("operation_id reused with different input in this project channel")
                if row[1] is None:
                    raise ExecutionUncertain("prior execution unsettled; explicit operator reconciliation required")
                return ExecutionResult(**json.loads(row[1]))
            self.db.execute("INSERT INTO scoped_operations VALUES (?,?,?,?,?,NULL)", (*scope, payload))
        return None

    def finish(self, request: ExecutionRequest, result: ExecutionResult):
        with self.db:
            self.db.execute(
                "UPDATE scoped_operations SET result=? WHERE profile=? AND project_id=? AND channel_id=? AND operation_id=?",
                (json.dumps(asdict(result)), request.profile, request.project_id,
                 request.channel_id, request.operation_id))

    def close(self):
        self.db.close()
