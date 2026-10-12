"""Minimal inbound admission record, not a Hermes memory backend."""
import json
from dataclasses import asdict
from pathlib import Path
import sqlite3
import uuid

from .artifacts import ArtifactRef
from .types import (ExecutionBudget, ExecutionRequest, ExecutionResult, ExecutionTaskContext,
                    ExecutionUncertain, RequestNotAdmitted, network_execution_context_id)


def _request_payload(request: ExecutionRequest) -> str:
    fields = {
        "profile": request.profile, "project_id": request.project_id,
        "channel_id": request.channel_id, "operation_id": request.operation_id,
        "text": request.text,
        "artifact_refs": [ref.to_wire() for ref in request.artifact_refs],
    }
    return json.dumps(fields, sort_keys=True)


def _canonical_payload(payload: str) -> str:
    data = json.loads(payload)
    data.setdefault("artifact_refs", [])
    return json.dumps(data, sort_keys=True)


def _restore_artifact_refs(data: dict) -> dict:
    data["artifact_refs"] = tuple(ArtifactRef.from_wire(ref)
                                  for ref in data.get("artifact_refs", []))
    return data


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
        self.db.execute("CREATE TABLE IF NOT EXISTS held_execution (profile TEXT PRIMARY KEY, request TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS terminated_operations (context_id TEXT PRIMARY KEY)")
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

    def cached(self, request: ExecutionRequest) -> ExecutionResult | None:
        payload = _request_payload(request)
        scope = (request.profile, request.project_id, request.channel_id, request.operation_id)
        row = self.db.execute(
            "SELECT payload,result FROM scoped_operations "
            "WHERE profile=? AND project_id=? AND channel_id=? AND operation_id=?", scope,
        ).fetchone()
        if not row:
            return None
        if _canonical_payload(row[0]) != payload:
            raise RequestNotAdmitted("operation_id reused with different input in this project channel")
        if row[1] is None:
            raise ExecutionUncertain("prior execution unsettled; explicit operator reconciliation required")
        return ExecutionResult(**_restore_artifact_refs(json.loads(row[1])))

    def admit(self, request: ExecutionRequest) -> ExecutionResult | None:
        # Session IDs are derived from the durable channel lineage, not from
        # the operation payload. Exclude them so replaying an already-finished
        # operation after rotation remains an idempotent read of its result.
        cached = self.cached(request)
        if cached is not None:
            return cached
        payload = _request_payload(request)
        scope = (request.profile, request.project_id, request.channel_id, request.operation_id)
        with self.db:
            row = self.db.execute(
                "SELECT payload,result FROM scoped_operations "
                "WHERE profile=? AND project_id=? AND channel_id=? AND operation_id=?", scope).fetchone()
            if row:
                if _canonical_payload(row[0]) != payload:
                    raise RequestNotAdmitted("operation_id reused with different input in this project channel")
                if row[1] is None:
                    raise ExecutionUncertain("prior execution unsettled; explicit operator reconciliation required")
                return ExecutionResult(**_restore_artifact_refs(json.loads(row[1])))
            self.db.execute("INSERT INTO scoped_operations VALUES (?,?,?,?,?,NULL)", (*scope, payload))
        return None

    def finish(self, request: ExecutionRequest, result: ExecutionResult):
        with self.db:
            self.db.execute(
                "UPDATE scoped_operations SET result=? WHERE profile=? AND project_id=? AND channel_id=? AND operation_id=?",
                (json.dumps(asdict(result)), request.profile, request.project_id,
                 request.channel_id, request.operation_id))

    def hold(self, request: ExecutionRequest):
        with self.db:
            self.db.execute("INSERT INTO held_execution VALUES (?,?) ON CONFLICT(profile) "
                            "DO UPDATE SET request=excluded.request",
                            (request.profile, json.dumps(asdict(request))))

    def held(self, profile: str) -> ExecutionRequest | None:
        row = self.db.execute("SELECT request FROM held_execution WHERE profile=?", (profile,)).fetchone()
        if row is None:
            rows = self.db.execute("SELECT payload FROM scoped_operations WHERE profile=? AND result IS NULL "
                                   "ORDER BY rowid", (profile,)).fetchall()
            terminal = {row[0] for row in self.db.execute("SELECT context_id FROM terminated_operations")}
            data = next((payload for payload in (json.loads(row[0]) for row in rows)
                         if network_execution_context_id(profile, payload["project_id"], payload["channel_id"],
                                                         payload["operation_id"]) not in terminal), None)
            if data is None:
                return None
            origin, current = self.session(profile, data["project_id"], data["channel_id"])
            context = ExecutionTaskContext(
                network_execution_context_id(profile, data["project_id"], data["channel_id"], data["operation_id"]),
                (profile,), ExecutionBudget(0.0, 0, 0))
            request = ExecutionRequest(**_restore_artifact_refs(data), session_origin_id=origin,
                                       session_current_id=current, _task_context=context)
            self.hold(request)
            return request
        data = json.loads(row[0])
        context = data.pop("_task_context")
        data["_task_context"] = ExecutionTaskContext(
            context["network_context_id"], tuple(context["trace"]),
            ExecutionBudget(**context["budget"]), context.get("run_id", ""))
        return ExecutionRequest(**_restore_artifact_refs(data))

    def is_terminated(self, context_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM terminated_operations WHERE context_id=?", (context_id,)).fetchone() is not None

    def terminate(self, context_id: str):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO terminated_operations VALUES (?)", (context_id,))

    def release(self, profile: str):
        with self.db:
            self.db.execute("DELETE FROM held_execution WHERE profile=?", (profile,))

    def close(self):
        self.db.close()
