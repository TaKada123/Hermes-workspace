"""Legacy global operation rows migrate into project/channel-scoped identity."""
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from hermes_ag2_network.ledger import Ledger
from hermes_ag2_network.types import ExecutionRequest, ExecutionResult


def test_legacy_operations_migrate_and_operation_ids_are_channel_scoped(tmp_path: Path):
    path = tmp_path / "ledger.sqlite"
    legacy_payload = {
        "profile": "architect", "project_id": "project-one", "channel_id": "channel-one",
        "operation_id": "shared-op", "text": "completed before upgrade",
    }
    legacy_result = ExecutionResult("legacy result", "session-one", "run-one")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE operations (id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT)")
        db.execute("INSERT INTO operations VALUES (?,?,?)", (
            "shared-op", json.dumps(legacy_payload, sort_keys=True), json.dumps(asdict(legacy_result))))

    ledger = Ledger(path)
    old_request = ExecutionRequest("architect", "project-one", "channel-one", "shared-op",
                                   "completed before upgrade", "origin-one", "rotated-one")
    assert ledger.admit(old_request) == legacy_result

    new_request = ExecutionRequest("architect", "project-two", "channel-two", "shared-op",
                                   "independent operation", "origin-two", "origin-two")
    assert ledger.admit(new_request) is None
    new_result = ExecutionResult("separate result", "origin-two", "run-two")
    ledger.finish(new_request, new_result)
    assert ledger.admit(new_request) == new_result
    ledger.close()
