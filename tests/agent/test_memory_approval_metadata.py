"""Tool -> durable pending proposal -> user approval preserves typed metadata."""
import json
from contextlib import closing

import pytest

from agent.memory_store_v2 import MemoryStoreV2
from tools.memory_tool import memory_tool


@pytest.mark.parametrize("gate", ["approval", "background"])
@pytest.mark.parametrize("action", ["supersede", "replace"])
def test_approval_preserves_requested_metadata(tmp_path, monkeypatch, gate, action):
    from hermes_cli.write_approval_commands import handle_pending_subcommand
    from tools import write_approval as wa
    from tools.skill_provenance import set_current_write_origin, reset_current_write_origin

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: false\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        first = store.add("memory", "quartz original staged")
        immediate = store.add("memory", "quartz original immediate")
        metadata = dict(entry_type="constraint", importance=0.93, written_by="review:quartz", reason="updated")
        assert json.loads(memory_tool(action, old_id=immediate["id"], old_text="quartz original immediate", content="quartz immediate", store=store, **metadata))["success"]
        if gate == "approval":
            (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
            monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
        token = set_current_write_origin("background_review" if gate == "background" else "test")
        try:
            staged = json.loads(memory_tool(action, old_id=first["id"], old_text="quartz original staged", content="quartz staged", store=store, **metadata))
        finally:
            reset_current_write_origin(token)
        assert staged["staged"]
        assert "quartz staged" not in [r["content"] for r in store.recall("quartz")["results"]]
        out = handle_pending_subcommand(wa.MEMORY, ["approve", staged["pending_id"]], memory_store=store)
        assert "Approved 1" in out, out
        assert wa.get_pending(wa.MEMORY, staged["pending_id"]) is None
        rows = {r["content"]: r for r in store.recall("quartz")["results"]}
        for key, requested in [("type", "constraint"), ("importance", 0.93)]:
            assert rows["quartz staged"][key] == requested
            assert rows["quartz immediate"][key] == requested
        reverted = store.rollback_consumer("review:quartz", target="memory")
        assert reverted["success"]
        if action == "supersede":
            assert reverted["deprecated"] == 2
            assert store.recall("quartz")["count"] == 0
        else:
            # Replace keeps original provenance, identically on both paths.
            assert reverted["deprecated"] == 0
