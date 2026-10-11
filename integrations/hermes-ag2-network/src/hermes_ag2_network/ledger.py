"""Minimal inbound admission record, not a Hermes memory backend."""
import json
from dataclasses import asdict
from pathlib import Path
import sqlite3

from .types import ExecutionRequest, ExecutionResult, ExecutionUncertain


class Ledger:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        path.chmod(0o600)
        self.db.execute("CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT)")
        self.db.commit()

    def admit(self, request: ExecutionRequest) -> ExecutionResult | None:
        payload = json.dumps(asdict(request), sort_keys=True)
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
