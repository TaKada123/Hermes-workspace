"""Tests for ticket #8 — read-only memory briefing for subagents (agent side).

Covered here:
- the parent's MemoryBus wiring (``agent_init._init_memory_bus``): sqlite_v2
  backend + v2 store + ``memory.bus.enabled`` gate; legacy backend / flat
  store / disabled gate all leave the parent without a bus handle;
- the parent's ``_init_memory`` seam: a subagent (skip_memory + memory
  toolset blocked) structurally gets no ``_memory_store``, no ``_memory_bus``,
  no ``_memory_manager`` — the isolation is construction-level, not prompt
  politeness;
- ``build_delegation_briefing`` failure paths ('' on any error) and the
  provider-context exclusion (the briefing never carries the external
  provider's fenced tag).

The delegate-path hook (goal append, gate on/off) is covered in
tests/tools/test_delegate_briefing_gate.py; the live payload behaviour in
tests/e2e/core/memv2/test_memv2_subagent_briefing_e2e.py.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.memory_bus import MemoryBus, build_delegation_briefing
from agent.memory_store_v2 import MemoryStoreV2


@pytest.fixture()
def mem_dir(tmp_path, monkeypatch):
    """Isolated temp HERMES_HOME per test — store DB + projections live there."""
    home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home / "memories"


def _fresh_store(mem_dir, **kw):
    s = MemoryStoreV2(**kw)
    s.load_from_disk()
    return s


# ============================================================================
# Parent bus wiring (agent_init._init_memory_bus)
# ============================================================================


def test_parent_bus_wiring_on_sqlite_v2(mem_dir):
    from agent.agent_init import _init_memory_bus

    store = _fresh_store(mem_dir)
    agent = SimpleNamespace()
    _init_memory_bus(agent, {"memory": {"backend": "sqlite_v2"}}, store, None)
    bus = agent._memory_bus
    assert isinstance(bus, MemoryBus)
    assert bus.store is store
    assert set(bus.targets) == {"memory", "user"}
    assert bus.token_budget == 2500 and bus.max_entries == 20
    store.close()


def test_parent_bus_gate_actually_disables(mem_dir):
    """AC: the ``memory.bus.enabled`` gate (default True) really turns the bus off."""
    from agent.agent_init import _init_memory_bus

    store = _fresh_store(mem_dir)
    agent = SimpleNamespace()
    _init_memory_bus(agent, {"memory": {"backend": "sqlite_v2", "bus": {"enabled": False}}}, store, None)
    assert agent._memory_bus is None
    store.close()


def test_parent_bus_legacy_backend_is_none(mem_dir):
    from agent.agent_init import _init_memory_bus

    store = _fresh_store(mem_dir)
    agent = SimpleNamespace()
    _init_memory_bus(agent, {"memory": {"backend": "file"}}, store, None)
    assert agent._memory_bus is None
    store.close()


def test_parent_bus_requires_v2_store_duck_type(mem_dir):
    from agent.agent_init import _init_memory_bus

    agent = SimpleNamespace()
    # A flat legacy store has no recall_candidates — the bus must not attach.
    _init_memory_bus(agent, {"memory": {"backend": "sqlite_v2"}}, SimpleNamespace(), None)
    assert agent._memory_bus is None


def test_parent_bus_reads_orchestrator_weights(mem_dir):
    from agent.agent_init import _init_memory_bus

    store = _fresh_store(mem_dir)
    agent = SimpleNamespace()
    _init_memory_bus(
        agent,
        {"memory": {"backend": "sqlite_v2", "orchestrator": {"weights": {"relevance": 0.5}}}},
        store, None,
    )
    assert agent._memory_bus.weights.relevance == 0.5
    store.close()


def test_parent_bus_failure_is_non_fatal(mem_dir):
    from agent.agent_init import _init_memory_bus

    agent = SimpleNamespace()
    # A store whose recall_candidates attribute explodes on access must not
    # break agent init: the bus stays None.
    class ExplodingStore:
        @property
        def recall_candidates(self):
            raise RuntimeError("boom")

    _init_memory_bus(agent, {"memory": {"backend": "sqlite_v2"}}, ExplodingStore(), None)
    assert agent._memory_bus is None


# ============================================================================
# Parent init seam — the parent gets store + bus; the child gets neither
# ============================================================================


def test_parent_init_gets_store_and_bus(tmp_path, monkeypatch):
    from agent.agent_init import _init_memory

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    parent = SimpleNamespace(enabled_toolsets=["memory"], disabled_toolsets=[])
    _init_memory(parent, {"memory": {"backend": "sqlite_v2"}}, skip_memory=False, platform="cli")
    assert isinstance(parent._memory_store, MemoryStoreV2)
    assert isinstance(parent._memory_bus, MemoryBus)
    parent._memory_store.close()


def test_child_init_gets_no_store_bus_or_manager(tmp_path, monkeypatch):
    """AC: the child runs without memory tool, bus handle and DB path.

    A subagent arrives with skip_memory=True and the memory toolset
    denylisted; ``_init_memory`` must leave every memory attribute inert.
    """
    from agent.agent_init import _init_memory

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    child = SimpleNamespace(
        enabled_toolsets=["terminal", "file", "web"],
        disabled_toolsets=["memory", "delegation", "clarify", "send_message", "cronjob_manage"],
    )
    _init_memory(
        child,
        {"memory": {"backend": "sqlite_v2", "bus": {"enabled": True}}},
        skip_memory=True, platform="subagent",
    )
    assert child._memory_store is None
    assert child._memory_bus is None
    assert child._memory_manager is None
    assert getattr(child, "_memory_orchestrator", None) is None


# ============================================================================
# build_delegation_briefing — failure paths + provider-context exclusion
# ============================================================================


def test_delegation_briefing_empty_without_bus(mem_dir):
    parent = SimpleNamespace()
    assert build_delegation_briefing(parent, "goal") == ""


def test_delegation_briefing_empty_with_none_bus(mem_dir):
    parent = SimpleNamespace(_memory_bus=None)
    assert build_delegation_briefing(parent, "goal") == ""


def test_delegation_briefing_empty_on_store_failure(mem_dir):
    """'' on any failure: a closed store raises inside recall and is swallowed."""
    store = _fresh_store(mem_dir)
    bus = MemoryBus(store=store)
    parent = SimpleNamespace(_memory_bus=bus)
    store.close()
    assert build_delegation_briefing(parent, "любой запрос") == ""


def test_delegation_briefing_excludes_provider_context(mem_dir):
    """AC: the briefing never contains the external provider's fenced tag.

    Even when the parent's bus carries a manager whose prefetch returns a
    ``<memory-context>`` block, the delegation briefing is store-only.
    """
    store = _fresh_store(mem_dir)
    store.add("memory", "Правило ревью: два аппрува", entry_type="constraint")
    store.close()
    store2 = _fresh_store(mem_dir)
    manager = SimpleNamespace(
        prefetch_all=lambda q: "<memory-context>внешний провайдер помнит</memory-context>",
    )
    bus = MemoryBus(store=store2, manager=manager)
    parent = SimpleNamespace(_memory_bus=bus)
    brief = build_delegation_briefing(parent, "ревью аппрувы правило")
    assert "Memory briefing" in brief
    assert "<memory-context" not in brief
    assert "внешний провайдер" not in brief
    store2.close()


def test_delegation_briefing_recalls_parent_entries(mem_dir):
    """The parent recalls its own store on the child's behalf (read-only)."""
    store = _fresh_store(mem_dir)
    store.add("memory", "Сервер гипервизор требует TLS 1.3", entry_type="constraint")
    store.close()
    store2 = _fresh_store(mem_dir)
    parent = SimpleNamespace(_memory_bus=MemoryBus(store=store2))
    brief = build_delegation_briefing(parent, "напиши отчёт про сервер гипервизор", subagent_id="sa-1")
    assert "Memory briefing" in brief
    assert "TLS" in brief
    store2.close()
