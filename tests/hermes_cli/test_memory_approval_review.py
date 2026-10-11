"""Approvers see the exact full content/revision their consent binds to."""
import json
from contextlib import closing

import pytest

from agent.memory_store_v2 import MemoryStoreV2
from hermes_cli.write_approval_commands import handle_pending_subcommand
from tools import write_approval as wa
from tools.memory_tool import memory_tool
from tools.terminal_tool import set_approval_callback


@pytest.mark.parametrize("action", ["supersede", "deprecate"])
def test_pending_lists_reviewed_id_content_and_revision(tmp_path, monkeypatch, action):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        body = "quartz first reviewed clause\nquartz second reviewed clause"
        old = store.add("memory", body)
        result = json.loads(memory_tool(action, old_id=old["id"][:8], content="quartz new decision", store=store))
        assert result["staged"]
        payload = wa.get_pending(wa.MEMORY, result["pending_id"])["payload"]
        listing = handle_pending_subcommand(wa.MEMORY, ["pending"], memory_store=store)
        assert body in listing
        assert old["id"] in listing
        assert payload["reviewed_entry"]["revision"] in listing


def test_inline_approval_displays_full_reviewed_content(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_SINGLE_QUERY_SESSION", raising=False)
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: true\n")
    seen = []
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        body = "quartz first reviewed clause\nquartz second reviewed clause"
        old = store.add("memory", body)
        def approve(detail, *args, **kwargs):
            seen.append(detail)
            return "once"
        set_approval_callback(approve)
        try:
            result = json.loads(memory_tool("deprecate", old_id=old["id"][:8], store=store))
        finally:
            set_approval_callback(None)
        assert result["success"] and not result.get("staged"), result
        assert body in seen[0]
        assert old["id"] in seen[0]
