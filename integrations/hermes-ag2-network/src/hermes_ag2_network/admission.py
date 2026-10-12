"""Shared same-host authority for controlled bridges, not a memory backend.

SQLite transactions serialize admission across processes. Leases never expire:
a deadline or crashed bridge cannot prove the external Run has terminated.
"""
from pathlib import Path
import sqlite3
import time
import uuid

from .types import ExecutionUncertain, NetworkBudgetExceeded


class Admission:
    def __init__(self, path: Path, capacity: int, pending_capacity: int):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        path.chmod(0o600)
        self.db.execute("CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY, capacity INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS interactions (id TEXT PRIMARY KEY, remaining INTEGER NOT NULL, deadline REAL NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS leases (profile TEXT PRIMARY KEY, context_id TEXT UNIQUE NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS transport_policy (id INTEGER PRIMARY KEY, capacity INTEGER NOT NULL)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS transports (
            context_id TEXT PRIMARY KEY, transport_id TEXT UNIQUE NOT NULL, payload_hash TEXT NOT NULL)""")
        try:
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO policy VALUES (1,?)", (capacity,))
                actual = self.db.execute("SELECT capacity FROM policy WHERE id=1").fetchone()[0]
                if actual != capacity:
                    raise ValueError("all controlled participants must use the same global capacity")
                if self.db.execute("SELECT COUNT(*) FROM transports").fetchone()[0] > pending_capacity:
                    raise ValueError("settle pending transports before enrolling a stricter pending capacity")
                self.db.execute("INSERT OR IGNORE INTO transport_policy VALUES (1,?)", (pending_capacity,))
                # Existing per-profile queue limits may differ. Shared pending policy uses
                # the strictest enrolled limit and never silently expands on disconnect.
                self.db.execute("UPDATE transport_policy SET capacity=MIN(capacity,?) WHERE id=1", (pending_capacity,))
        except BaseException:
            self.db.close()
            raise
        self.capacity = capacity

    def _occupied(self) -> int:
        # A submitted request becomes an execution without taking a second slot.
        return self.db.execute("SELECT COUNT(*) FROM (SELECT context_id FROM leases "
                               "UNION SELECT context_id FROM transports)").fetchone()[0]

    def reserve_transport(self, context_id: str, transport_id: str, payload_hash: str,
                          interaction: tuple[str, int, float] | None = None):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            previous = self.db.execute("SELECT payload_hash FROM transports WHERE context_id=?", (context_id,)).fetchone()
            if previous is not None:
                if previous[0] != payload_hash:
                    raise ValueError("operation_id reused with different input in this project channel")
                raise ExecutionUncertain("prior transport submission is pending or uncertain; inspect history; explicit operator reconciliation required, do not resend")
            if self._occupied() >= self.capacity:
                raise NetworkBudgetExceeded(code="global_capacity")
            pending_capacity = self.db.execute("SELECT capacity FROM transport_policy WHERE id=1").fetchone()[0]
            if self.db.execute("SELECT COUNT(*) FROM transports").fetchone()[0] >= pending_capacity:
                raise NetworkBudgetExceeded(code="pending_capacity")
            if interaction is not None:
                self.db.execute("INSERT INTO interactions VALUES (?,?,?)", interaction)
            self.db.execute("INSERT INTO transports VALUES (?,?,?)", (context_id, transport_id, payload_hash))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def release_transport(self, transport_id: str):
        with self.db:
            self.db.execute("DELETE FROM transports WHERE transport_id=?", (transport_id,))

    def reconcile_transport(self, context_id: str):
        # Only authenticated terminal Run readback, never a deadline/ACK/disconnect.
        with self.db:
            self.db.execute("DELETE FROM transports WHERE context_id=?", (context_id,))

    def interaction(self, turns: int, deadline: float) -> str:
        identity = uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO interactions VALUES (?,?,?)", (identity, turns, deadline))
        return identity

    def remaining(self, identity: str) -> int:
        row = self.db.execute("SELECT remaining,deadline FROM interactions WHERE id=?", (identity,)).fetchone()
        if row is None or row[1] <= time.time() or row[0] < 1:
            raise NetworkBudgetExceeded(code="interaction_budget")
        return row[0]

    def acquire(self, profile: str, context_id: str, interaction_id: str):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self.remaining(interaction_id)
            if self.db.execute("SELECT 1 FROM leases WHERE profile=?", (profile,)).fetchone():
                raise NetworkBudgetExceeded(code="profile_held")
            reserved = self.db.execute("SELECT 1 FROM transports WHERE context_id=?", (context_id,)).fetchone()
            if reserved is None and self._occupied() >= self.capacity:
                raise NetworkBudgetExceeded(code="global_capacity")
            self.db.execute("INSERT INTO leases VALUES (?,?)", (profile, context_id))
            self.db.execute("UPDATE interactions SET remaining=remaining-1 WHERE id=?", (interaction_id,))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def restore(self, profile: str, context_id: str):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute("SELECT context_id FROM leases WHERE profile=?", (profile,)).fetchone()
            if existing is not None:
                if existing[0] != context_id:
                    raise NetworkBudgetExceeded(code="profile_held")
            else:
                reserved = self.db.execute("SELECT 1 FROM transports WHERE context_id=?", (context_id,)).fetchone()
                if reserved is None and self._occupied() >= self.capacity:
                    raise NetworkBudgetExceeded(code="global_capacity")
                self.db.execute("INSERT INTO leases VALUES (?,?)", (profile, context_id))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def release(self, profile: str, context_id: str):
        with self.db:
            self.db.execute("DELETE FROM leases WHERE profile=? AND context_id=?", (profile, context_id))

    def close(self):
        self.db.close()
