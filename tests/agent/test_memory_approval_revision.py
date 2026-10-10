"""Actual tool -> pending store -> user approval must bind a reviewed revision."""
import json
from contextlib import closing

import pytest

from agent.memory_store_v2 import MemoryStoreV2
from hermes_cli.write_approval_commands import handle_pending_subcommand
from tools import write_approval as wa
from tools.memory_tool import memory_tool
from tools.skill_provenance import set_current_write_origin, reset_current_write_origin


@pytest.mark.parametrize("action", ["deprecate", "supersede"])
@pytest.mark.parametrize("gate", ["approval", "background"])
def test_id_approval_refuses_replaced_revision(tmp_path, monkeypatch, action, gate):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        old = store.add("memory", "quartz reviewed decision", entry_type="decision")
        successor = store.add("memory", "quartz existing successor")
        token = set_current_write_origin("background_review" if gate == "background" else "test")
        try:
            staged = json.loads(memory_tool(action, old_id=old["id"][:8], content="quartz proposed successor",
                                           superseded_by_id=successor["id"], store=store))
        finally:
            reset_current_write_origin(token)
        assert staged["staged"], staged
        assert store.replace("memory", "quartz reviewed decision", "quartz unreviewed decision")["success"]
        before = store.visible_rows("memory")
        projection = (tmp_path / "memories" / "MEMORY.md").read_bytes()
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" not in out, out
        assert store.visible_rows("memory") == before
        assert (tmp_path / "memories" / "MEMORY.md").read_bytes() == projection
        assert store.supersedes_neighbors([old["id"], successor["id"]]) == {}
        assert wa.get_pending(wa.MEMORY, staged["pending_id"]) is not None


@pytest.mark.parametrize("action,batch", [("replace", False), ("remove", False), ("deprecate", False),
                                           ("replace", True), ("remove", True)])
@pytest.mark.parametrize("gate", ["approval", "background"])
def test_text_approval_refuses_aba(tmp_path, monkeypatch, action, batch, gate):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        old = store.add("memory", "quartz reviewed text")
        store.add("memory", "untouched companion")
        op = dict(action=action, old_text="quartz reviewed text", content="approved new text")
        token = set_current_write_origin("background_review" if gate == "background" else "test")
        try:
            call = memory_tool(store=store, operations=[op]) if batch else memory_tool(store=store, **op)
            staged = json.loads(call)
        finally:
            reset_current_write_origin(token)
        assert staged["staged"], staged
        assert store.replace("memory", "quartz reviewed text", "quartz intervening text")["success"]
        assert store.replace("memory", "quartz intervening text", "quartz reviewed text")["success"]
        before = store.visible_rows("memory")
        projection = (tmp_path / "memories" / "MEMORY.md").read_bytes()
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" not in out, out
        assert store.visible_rows("memory") == before
        assert (tmp_path / "memories" / "MEMORY.md").read_bytes() == projection
        assert store.supersedes_neighbors([old["id"]]) == {}


@pytest.mark.parametrize("action", ["deprecate", "supersede"])
def test_inline_approval_does_not_repin_after_user_review(tmp_path, monkeypatch, action):
    from tools.terminal_tool import set_approval_callback
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_SINGLE_QUERY_SESSION", raising=False)
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        old = store.add("memory", "quartz reviewed inline")
        def approve(*args, **kwargs):
            assert store.replace("memory", "quartz reviewed inline", "quartz unreviewed inline")["success"]
            return "once"
        set_approval_callback(approve)
        try:
            result = json.loads(memory_tool(action, old_id=old["id"][:8], content="quartz successor", store=store))
        finally:
            set_approval_callback(None)
        assert not result["success"], result
        assert [r["content"] for r in store.visible_rows("memory")] == ["quartz unreviewed inline"]
        assert store.supersedes_neighbors([old["id"]]) == {}


@pytest.mark.parametrize("action", ["deprecate", "supersede"])
def test_unchanged_id_approval_survives_recall_and_keeps_provenance(tmp_path, monkeypatch, action):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        old = store.add("memory", "quartz valid approval")
        successor = store.add("memory", "quartz existing successor")
        staged = json.loads(memory_tool(action, old_id=old["id"][:8], content="quartz approved successor",
                                       superseded_by_id=successor["id"], written_by="review:quartz", store=store))
        assert staged["staged"]
        payload = wa.get_pending(wa.MEMORY, staged["pending_id"])["payload"]
        assert payload["old_id"] == old["id"]
        assert payload["reviewed_entry"]["content"] == "quartz valid approval"
        store.recall("quartz")  # access counters must not invalidate semantic approval
        store.add("memory", "unrelated addition")
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" in out, out
        assert wa.get_pending(wa.MEMORY, staged["pending_id"]) is None
        successors = [r["id"] for r in store.visible_rows("memory")]
        neighbors = store.supersedes_neighbors(successors)
        assert any(n["id"] == old["id"] for ns in neighbors.values() for n in ns)


@pytest.mark.parametrize("action", ["deprecate", "supersede"])
def test_typed_batch_actions_are_refused_without_mutation(tmp_path, monkeypatch, action):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        old = store.add("memory", "quartz batch original")
        before = store.visible_rows("memory")
        result = json.loads(memory_tool(operations=[dict(action=action, old_id=old["id"], content="quartz successor")], store=store))
        assert not result["success"] and "unknown action" in result["error"], result
        assert store.visible_rows("memory") == before
