"""Public approval lifecycle against a real competing SQLite writer."""
import json
import sqlite3
from contextlib import closing

import pytest

from agent.memory_store_v2 import MemoryStoreV2
from hermes_cli.write_approval_commands import handle_pending_subcommand
from tools import write_approval as wa
from tools.memory_tool import memory_tool


@pytest.mark.parametrize("action,batch", [("deprecate", False), ("supersede", False),
                                           ("replace", False), ("remove", False),
                                           ("replace", True), ("remove", True)])
def test_approval_checks_revision_inside_destructive_transaction(tmp_path, monkeypatch, action, batch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    state = {"armed": False}
    real_connect = sqlite3.connect

    class InterleavingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "BEGIN IMMEDIATE" and state["armed"]:
                state["armed"] = False
                # A second real connection commits AFTER any pre-transaction check.
                assert writer.replace("memory", "quartz reviewed", "quartz intervening")["success"]
            return super().execute(sql, parameters)

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: real_connect(*a, **{**kw, "factory": InterleavingConnection}))
    with closing(MemoryStoreV2()) as store, closing(MemoryStoreV2()) as writer:
        store.load_from_disk()
        writer.load_from_disk()
        old = store.add("memory", "quartz reviewed")
        companion = store.add("memory", "quartz companion")
        op = dict(action=action, content="quartz successor")
        if action in ("deprecate", "supersede"):
            op["old_id"] = old["id"]
        else:
            op["old_text"] = "quartz reviewed"
        call = memory_tool(store=store, operations=[op]) if batch else memory_tool(store=store, **op)
        staged = json.loads(call)
        assert staged["staged"], staged
        state["armed"] = True
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert not state["armed"]  # the competing write really happened
        assert "Approved 1" not in out, out
        assert {r["content"] for r in store.visible_rows("memory")} == {"quartz intervening", "quartz companion"}
        assert store.supersedes_neighbors([old["id"], companion["id"]]) == {}
        assert wa.get_pending(wa.MEMORY, staged["pending_id"]) is not None


@pytest.mark.parametrize("status", ["active", "pinned", "dormant", "archived", "deprecated"])
def test_id_approval_refuses_status_aba(tmp_path, monkeypatch, status):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        old = store.add("memory", "quartz status reviewed")
        staged = json.loads(memory_tool("deprecate", old_id=old["id"], store=store))
        # Canonical maintenance writers may update any supported status. The trigger
        # revision covers these too, including same-content/status ABA within a second.
        with sqlite3.connect(store.db_path) as db:
            db.execute("UPDATE memories SET status=? WHERE id=?", (status, old["id"]))
            db.execute("UPDATE memories SET status='active' WHERE id=?", (old["id"],))
        before = store.visible_rows("memory")
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" not in out, out
        assert store.visible_rows("memory") == before


def test_id_approval_refuses_delete_reinsert_aba(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        old = store.add("memory", "quartz identical replacement")
        original = store.visible_rows("memory")[0]
        staged = json.loads(memory_tool("deprecate", old_id=old["id"], store=store))
        assert store.remove("memory", "quartz identical replacement")["success"]
        # Reinsert the same ID, content and timestamps as a canonical maintenance writer.
        with sqlite3.connect(store.db_path) as db:
            columns = ",".join(original)
            placeholders = ",".join("?" for _ in original)
            db.execute(f"INSERT INTO memories({columns}) VALUES ({placeholders})", tuple(original.values()))
        before = store.visible_rows("memory")
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" not in out, out
        assert store.visible_rows("memory") == before


def test_display_prefix_is_not_reresolved_at_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        old = store.add("memory", "quartz prefix reviewed")
        other = store.add("memory", "quartz unrelated")
        staged = json.loads(memory_tool("deprecate", old_id=old["id"][:8], store=store))
        # An unrelated row acquires the same display prefix AFTER staging.
        clone = next(r for r in store.visible_rows("memory") if r["id"] == other["id"])
        clone["id"] = old["id"][:8] + other["id"][8:]
        clone["content"] = "quartz prefix collision"
        with sqlite3.connect(store.db_path) as db:
            columns = ",".join(clone)
            placeholders = ",".join("?" for _ in clone)
            db.execute(f"INSERT INTO memories({columns}) VALUES ({placeholders})", tuple(clone.values()))
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" in out, out
        assert {r["content"] for r in store.visible_rows("memory")} == {"quartz unrelated", "quartz prefix collision"}


def test_valid_sequential_batch_pins_original_ancestors_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        store.add("memory", "quartz original")
        store.add("memory", "quartz companion")
        staged = json.loads(memory_tool(store=store, operations=[
            {"action": "replace", "old_text": "quartz original", "content": "quartz intermediate"},
            {"action": "replace", "old_text": "quartz intermediate", "content": "quartz final"},
            {"action": "add", "content": "quartz added"},
            {"action": "remove", "old_text": "quartz added"},
        ]))
        assert staged["staged"], staged
        store.add("memory", "unrelated addition")
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" in out, out
        assert {r["content"] for r in store.visible_rows("memory")} == {"quartz final", "quartz companion", "unrelated addition"}


def test_batch_duplicate_content_keeps_each_original_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        store.add("memory", "quartz first")
        store.add("memory", "quartz second")
        store.add("memory", "quartz companion")
        staged = json.loads(memory_tool(store=store, operations=[
            {"action": "replace", "old_text": "quartz second", "content": "quartz first"},
            {"action": "remove", "old_text": "quartz first"},
        ]))
        assert staged["staged"], staged
        store.replace("memory", "quartz first", "quartz intervening")
        store.replace("memory", "quartz intervening", "quartz first")
        before = store.visible_rows("memory")
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" not in out, out
        assert store.visible_rows("memory") == before
