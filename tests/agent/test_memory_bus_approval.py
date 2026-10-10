"""Public bus/approval contracts: issue #2 stories 12/13."""
from unittest.mock import Mock

import pytest

from agent.memory_bus import (
    ConsumerSpec, MemoryBus, READ_MEMORY, WRITE_MEMORY, ROLLBACK_MEMORY,
)
from agent.memory_store_v2 import MemoryStoreV2
from hermes_cli.write_approval_commands import handle_pending_subcommand
from tools import write_approval as wa


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "api_server")
    (tmp_path / "config.yaml").write_text("memory:\n  backend: sqlite_v2\n  write_approval: true\n")
    store = MemoryStoreV2()
    store.load_from_disk()
    manager = Mock()
    bus = MemoryBus(store, manager=manager)
    view = bus.scoped_view(ConsumerSpec(
        "reviewer", frozenset({READ_MEMORY, WRITE_MEMORY, ROLLBACK_MEMORY}), project="hermes",
    ))
    yield store, bus, view, manager
    store.close()


@pytest.mark.parametrize("unattended", [False, True])
def test_scoped_writer_waits_for_actual_approval(environment, unattended):
    store, bus, view, manager = environment
    from tools.skill_provenance import set_current_write_origin, reset_current_write_origin
    token = set_current_write_origin("background_review" if unattended else "foreground")
    try:
        result = view.remember("Approve this decision", entry_type="decision", importance=0.73)
    finally:
        reset_current_write_origin(token)
    assert result.get("staged") is True
    assert view.recall("decision")["entries"] == []
    assert store.recent_entries(limit=20) == []
    manager.on_memory_write.assert_not_called()
    pending = wa.get_pending(wa.MEMORY, result["pending_id"])
    assert pending["payload"]["written_by"] == "reviewer"
    assert pending["payload"]["project"] == "hermes"
    assert pending["origin"] == ("background_review" if unattended else "foreground")
    output = handle_pending_subcommand(wa.MEMORY, ["approve", result["pending_id"]], memory_store=store)
    assert "Approved 1 memory write(s)." in output
    row, = store.recent_entries(limit=20)
    assert (row["content"], row["type"], row["importance"], row["written_by"], row["project"]) == (
        "Approve this decision", "decision", 0.73, "reviewer", "hermes",
    )
    assert wa.get_pending(wa.MEMORY, result["pending_id"]) is None


@pytest.mark.parametrize("approval,unattended", [(True, False), (False, True)])
def test_restricted_rollback_refuses_without_deprecating(environment, tmp_path, approval, unattended):
    store, bus, view, manager = environment
    from tools.skill_provenance import set_current_write_origin, reset_current_write_origin
    (tmp_path / "config.yaml").write_text(f"memory:\n  write_approval: {str(approval).lower()}\n")
    store.add("memory", "Reviewed row", written_by="reviewer", project="hermes")
    store.add("memory", "Foreign row", written_by="other", project="hermes")
    store.add("user", "Other target", written_by="reviewer")
    before = store.recent_entries(limit=20)
    token = set_current_write_origin("background_review" if unattended else "foreground")
    try:
        result = view.rollback(target="memory", reason="consolidation")
    finally:
        reset_current_write_origin(token)
    assert result["success"] is False
    assert "rollback" in result["error"].lower()
    assert "deprecate" in result["error"].lower()
    assert store.recent_entries(limit=20) == before
    assert wa.list_pending(wa.MEMORY) == []
    manager.on_memory_write.assert_not_called()


@pytest.mark.parametrize("unattended", [False, True])
def test_permitted_add_and_foreground_scoped_rollback(environment, tmp_path, unattended):
    store, bus, view, manager = environment
    from tools.skill_provenance import set_current_write_origin, reset_current_write_origin
    (tmp_path / "config.yaml").write_text("memory:\n  write_approval: false\n")
    store.add("memory", "Foreign row", written_by="other")
    store.add("user", "Other target", written_by="reviewer")
    token = set_current_write_origin("background_review" if unattended else "foreground")
    try:
        result = bus.remember("Permitted decision", consumer_id="reviewer", entry_type="decision", importance=0.73)
    finally:
        reset_current_write_origin(token)
    assert result["success"] and not result.get("staged")
    manager.on_memory_write.assert_called_once_with(
        "add", "memory", "Permitted decision", metadata={"written_by": "reviewer", "project": "hermes"},
    )
    assert wa.list_pending(wa.MEMORY) == []
    row = next(row for row in store.recent_entries(limit=20) if row["content"] == "Permitted decision")
    assert (row["type"], row["importance"], row["project"], row["written_by"]) == (
        "decision", 0.73, "hermes", "reviewer",
    )
    assert view.rollback(target="memory")["deprecated"] == 1
    assert {row["content"] for row in store.recent_entries(limit=20)} == {"Foreign row", "Other target"}


def test_disabled_target_rejects_live_and_pending_bus_writes(environment):
    store, bus, view, manager = environment
    result = view.remember("Will be disabled")
    assert result["staged"]
    store.memory_enabled = False
    assert not view.remember("No new proposal")["success"]
    assert not view.rollback(target="memory")["success"]
    output = handle_pending_subcommand(wa.MEMORY, ["approve", result["pending_id"]], memory_store=store)
    assert "Approved 0 memory write(s)." in output
    assert "disabled" in output
    assert store.recent_entries(limit=20) == []
    assert wa.get_pending(wa.MEMORY, result["pending_id"]) is not None
    assert len(wa.list_pending(wa.MEMORY)) == 1
    manager.on_memory_write.assert_not_called()
