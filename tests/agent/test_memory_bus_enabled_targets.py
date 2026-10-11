"""Enable flags are live authorization boundaries, not just snapshot settings."""
from contextlib import closing
from types import SimpleNamespace

import pytest

from agent.memory_bus import (MemoryBus, ConsumerSpec, READ_MEMORY, READ_USER,
                              WRITE_MEMORY, WRITE_USER, ROLLBACK_MEMORY, ROLLBACK_USER,
                              build_delegation_briefing)
from agent.memory_store_v2 import MemoryStoreV2


@pytest.mark.parametrize("disabled", ["memory", "user"])
def test_disabled_target_cannot_be_read_briefed_written_or_rolled_back(tmp_path, monkeypatch, disabled):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    enabled = "user" if disabled == "memory" else "memory"
    with closing(MemoryStoreV2()) as store:
        store.load_from_disk()
        assert store.add(disabled, "quartz hidden", written_by="worker")["success"]
        assert store.add(enabled, "quartz visible", written_by="worker")["success"]
        bus = MemoryBus(store)
        mixed = ConsumerSpec("worker", frozenset({READ_MEMORY, READ_USER, WRITE_MEMORY, WRITE_USER, ROLLBACK_MEMORY, ROLLBACK_USER}))
        assert bus.subscribe(mixed)
        setattr(store, "memory_enabled" if disabled == "memory" else "user_profile_enabled", False)
        # No caller refresh required: operations must not use stale permissions.
        assert not bus.remember("quartz injected", consumer_id="worker", target=disabled)["success"]
        assert not bus.rollback("worker", target=disabled)["success"]
        assert not bus.recall("quartz", consumer_id="worker")["success"]
        bus.refresh_capabilities()
        assert bus.capabilities() == frozenset({f"read:{enabled}", f"write:{enabled}", f"rollback:{enabled}"})
        assert not bus.subscription("worker").active
        assert bus.subscription("worker").capabilities == bus.capabilities()
        assert bus.subscribe(ConsumerSpec("reader", frozenset({f"read:{enabled}"})))
        result = bus.recall("quartz", consumer_id="reader")
        assert [r["content"] for r in result["entries"]] == ["quartz visible"]
        briefing = build_delegation_briefing(SimpleNamespace(_memory_bus=bus), "quartz")
        assert "quartz visible" in briefing
        assert "quartz hidden" not in briefing
        # Enabled rollback remains usable and must not touch disabled records.
        assert bus.subscribe(ConsumerSpec("worker", frozenset({f"rollback:{enabled}"})))
        assert bus.rollback("worker", target=enabled)["success"]
        setattr(store, "memory_enabled" if disabled == "memory" else "user_profile_enabled", True)
        bus.refresh_capabilities()
        assert bus.subscribe(mixed)
        assert [r["content"] for r in bus.recall("quartz", consumer_id="worker")["entries"]] == ["quartz hidden"]
