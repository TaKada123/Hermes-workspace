"""Public load must atomically upgrade real old databases, including DDL/FTS."""
import sqlite3

import pytest

from agent.memory_store_v2 import MemoryStoreV2


IDS = ["11111111-1111-4111-8111-111111111111",
       "22222222-2222-4222-8222-222222222222",
       "33333333-3333-4333-8333-333333333333"]
STAMP = "2026-01-01T00:00:00+00:00"


def old_database(path, version):
    # Independent historical fixture: no new-schema initializer/migration calls.
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, target TEXT NOT NULL DEFAULT 'memory',"
                   " type TEXT NOT NULL DEFAULT 'fact', content TEXT NOT NULL,"
                   " importance REAL NOT NULL DEFAULT 0.5, confidence REAL NOT NULL DEFAULT 0.7,"
                   " status TEXT NOT NULL DEFAULT 'active', project TEXT, source_session TEXT,"
                   " deprecate_reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,"
                   " last_accessed_at TEXT, access_count INTEGER NOT NULL DEFAULT 0"
                   + (", written_by TEXT" if version >= 2 else "") + ")")
        db.execute("CREATE TABLE memory_links (source_id TEXT NOT NULL, target_id TEXT NOT NULL,"
                   " relation_type TEXT NOT NULL, created_at TEXT NOT NULL,"
                   " PRIMARY KEY(source_id,target_id,relation_type))")
        db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.executemany("INSERT INTO memories(id,content,created_at,updated_at) VALUES (?,?,?,?)",
                       [(i, c, STAMP, STAMP) for i, c in zip(IDS, ["велотренажёр", "decision", "evidence"])])
        db.executemany("INSERT INTO memory_links VALUES (?,?,?,?)",
                       [(IDS[0][:8], IDS[1][:8], "supersedes", STAMP),
                        (IDS[1], IDS[2], "supports", STAMP)])
        db.executemany("INSERT INTO meta VALUES (?,?)",
                       [("schema_version", str(version)), ("legacy_migrated", STAMP)])
    db.close()


def snapshot(path, connect):
    with connect(path) as db:
        schema = db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        tables = [r[1] for r in schema if r[0] == "table"]
        rows = {t: sorted(db.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr) for t in tables}
    db.close()
    return schema, rows


def inject(monkeypatch, stage, error):
    real_connect = sqlite3.connect
    state = {"armed": True}

    class InterruptedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            result = super().execute(sql, parameters)
            normalized = " ".join(sql.lower().split())
            match = {
                "drop": normalized == "drop table memory_links",
                "reinsert": normalized.startswith("insert into memory_links("),
                "fts": normalized.startswith("insert into memories_fts("),
                "marker": normalized.startswith("insert or replace into meta(key, value) values ('schema_version'"),
            }[stage]
            if state["armed"] and match:
                state["armed"] = False
                raise error("injected SQLite interruption")
            return result

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: real_connect(*a, **{**kw, "factory": InterruptedConnection}))
    return real_connect


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("stage", ["drop", "reinsert"])
@pytest.mark.parametrize("error", [sqlite3.OperationalError, KeyboardInterrupt])
def test_public_load_preserves_old_schema_and_provenance_on_interruption(tmp_path, monkeypatch, version, stage, error):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = tmp_path / "memory.db"
    old_database(path, version)
    real_connect = sqlite3.connect
    before = snapshot(path, real_connect)
    inject(monkeypatch, stage, error)
    store = MemoryStoreV2(db_path=path)
    try:
        with pytest.raises(error, match="injected SQLite interruption"):
            store.load_from_disk()
        assert snapshot(path, real_connect) == before
        store.load_from_disk()  # retry on the same object/connection
        assert {r["id"] for r in store.visible_rows("memory")} == set(IDS)
        with real_connect(path) as db:
            assert db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ("4",)
            assert set(db.execute("SELECT * FROM memory_links")) == {
                (IDS[0], IDS[1], "supersedes", STAMP), (IDS[1], IDS[2], "supports", STAMP)}
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        store.close()


@pytest.mark.parametrize("version", [1, 2])
def test_fts_reindex_fault_is_not_swallowed_and_all_upgrades_roll_back(tmp_path, monkeypatch, version):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = tmp_path / "memory.db"
    old_database(path, version)
    real_connect = sqlite3.connect
    before = snapshot(path, real_connect)
    inject(monkeypatch, "fts", sqlite3.OperationalError)
    store = MemoryStoreV2(db_path=path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="injected SQLite interruption"):
            store.load_from_disk()
        assert snapshot(path, real_connect) == before
        store.load_from_disk()
        assert {r["id"] for r in store.recall("велотренажер")["results"]} == {IDS[0]}
    finally:
        store.close()


def test_fresh_schema_rolls_back_and_retries_after_marker_interruption(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = tmp_path / "memory.db"
    real_connect = sqlite3.connect
    before = snapshot(path, real_connect)
    inject(monkeypatch, "marker", KeyboardInterrupt)
    store = MemoryStoreV2(db_path=path)
    try:
        with pytest.raises(KeyboardInterrupt, match="injected SQLite interruption"):
            store.load_from_disk()
        assert snapshot(path, real_connect) == before
        store.load_from_disk()
        assert store.add("memory", "After clean retry")["success"]
    finally:
        store.close()


@pytest.mark.parametrize("version", [None, 1, 2, 3])
def test_unavailable_fts_still_loads_and_recalls_without_partial_triggers(tmp_path, monkeypatch, version):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = tmp_path / "memory.db"
    if version is not None:
        old_database(path, version)
    real_connect = sqlite3.connect

    class WithoutFTS(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if "create virtual table" in sql.lower():
                raise sqlite3.OperationalError("no such module: fts5")
            return super().execute(sql, parameters)

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: real_connect(*a, **{**kw, "factory": WithoutFTS}))
    store = MemoryStoreV2(db_path=path)
    try:
        store.load_from_disk()
        if version is None:
            assert store.add("memory", "велотренажёр")["success"]
        result = store.recall("велотренажер")
        assert result["count"] == 1
        assert result["results"][0]["content"] == "велотренажёр"
        with real_connect(path) as db:
            assert db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ("4",)
            assert db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall() == []
    finally:
        store.close()


@pytest.mark.parametrize("fault", ["disk I/O error", "interrupted"])
def test_fts_setup_fault_is_not_misreported_as_optional_extension(tmp_path, monkeypatch, fault):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = tmp_path / "memory.db"
    old_database(path, 2)
    real_connect = sqlite3.connect
    before = snapshot(path, real_connect)

    class BrokenFTS(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if "create trigger memories_fts_ad" in sql.lower():
                raise sqlite3.OperationalError(fault)
            return super().execute(sql, parameters)

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: real_connect(*a, **{**kw, "factory": BrokenFTS}))
    store = MemoryStoreV2(db_path=path)
    try:
        with pytest.raises(sqlite3.OperationalError, match=fault):
            store.load_from_disk()
        assert snapshot(path, real_connect) == before
    finally:
        store.close()


@pytest.mark.parametrize("stage", ["drop", "reinsert"])
def test_sqlite_engine_interrupt_restores_old_schema_and_keeps_original_diagnostic(tmp_path, monkeypatch, stage):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = tmp_path / "memory.db"
    old_database(path, 3)
    real_connect = sqlite3.connect
    before = snapshot(path, real_connect)
    armed = True

    class EngineInterrupted(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            nonlocal armed
            result = super().execute(sql, parameters)
            normalized = " ".join(sql.lower().split())
            match = normalized == "drop table memory_links" if stage == "drop" else normalized.startswith("insert into memory_links(")
            if armed and match:
                armed = False
                # A real SQLITE_INTERRUPT during a write can roll back the
                # whole transaction itself, removing the schema savepoint.
                self.set_progress_handler(lambda: 1, 1)
                try:
                    super().execute("INSERT INTO meta VALUES ('interrupt-probe', 'value')")
                finally:
                    self.set_progress_handler(None, 0)
            return result

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: real_connect(*a, **{**kw, "factory": EngineInterrupted}))
    store = MemoryStoreV2(db_path=path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="^interrupted$"):
            store.load_from_disk()
        assert snapshot(path, real_connect) == before
        store.load_from_disk()
        assert {r["id"] for r in store.visible_rows("memory")} == set(IDS)
    finally:
        store.close()
