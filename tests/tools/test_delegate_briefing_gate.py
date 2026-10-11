"""Tests for ticket #8 — the delegate-path briefing hook.

The hook (``tools.delegate_tool_child_run._attach_delegation_briefing``)
appends the parent-recalled read-only memory briefing to the child's one-time
goal message. Covered here:

- gate ON: the goal carries the briefing (real bus + real v2 store);
- gate OFF via ``delegation.memory_briefing: false`` (the ACTUAL config
  reader, not a monkeypatched constant): the goal is untouched;
- the config default is True (fail-open when the key is absent);
- no parent bus: goal untouched;
- the briefing is appended exactly once and never wrapped in a
  ``<memory-context>`` fence;
- multimodal (content-parts list) goals gain the briefing as a trailing
  text part.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.memory_bus import MemoryBus
from agent.memory_store_v2 import MemoryStoreV2
from tools.delegate_tool_child_run import _attach_delegation_briefing


@pytest.fixture()
def mem_dir(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home / "memories"


def _parent_with_bus(mem_dir, *, with_entry=True):
    store = MemoryStoreV2()
    store.load_from_disk()
    if with_entry:
        store.add("memory", "Сервер гипервизор требует TLS 1.3", entry_type="constraint")
    bus = MemoryBus(store=store)
    return SimpleNamespace(_memory_bus=bus), store


GOAL = "напиши отчёт про сервер гипервизор"


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------


def test_briefing_attached_when_gate_on(mem_dir):
    parent, store = _parent_with_bus(mem_dir)
    out = _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL)
    assert isinstance(out, str)
    assert out.startswith(GOAL + "\n\n")
    assert "Memory briefing" in out
    assert "TLS" in out
    store.close()


def test_briefing_attached_when_gate_key_absent(mem_dir, monkeypatch):
    """Default-on: an absent ``memory_briefing`` key behaves like True."""
    from tools import delegate_tool_config

    monkeypatch.setattr(delegate_tool_config, "_load_config", lambda: {})
    parent, store = _parent_with_bus(mem_dir)
    out = _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL)
    assert "Memory briefing" in out
    store.close()


def test_briefing_not_attached_when_gate_off(mem_dir, monkeypatch):
    """AC: delegation.memory_briefing=false really disables the feature."""
    from tools import delegate_tool_config

    monkeypatch.setattr(delegate_tool_config, "_load_config", lambda: {"memory_briefing": False})
    parent, store = _parent_with_bus(mem_dir)
    out = _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL)
    assert out == GOAL
    store.close()


def test_gate_default_is_true_in_config_defaults():
    """The shipped default: delegation.memory_briefing is True."""
    from hermes_cli.config_defaults import DEFAULT_CONFIG

    delegation = DEFAULT_CONFIG.get("delegation") or {}
    assert delegation.get("memory_briefing") is True


def test_gate_reads_delegation_section_not_top_level(mem_dir):
    """Regression for the arch2 bug: the gate is ``delegation.memory_briefing``,
    not a top-level ``memory_briefing`` key.

    A user config carrying ``memory_briefing: false`` at the TOP level (the
    arch2 read pattern) must not disable the briefing: the real config loader
    exposes the key only under ``delegation``.
    """
    home = mem_dir.parent  # <tmp>/.hermes — the isolated HERMES_HOME
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        "memory_briefing: false\n"
        "delegation:\n"
        "  max_iterations: 250\n",
        encoding="utf-8",
    )
    parent, store = _parent_with_bus(mem_dir)
    out = _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL)
    assert "Memory briefing" in out
    store.close()


# ---------------------------------------------------------------------------
# hook behavior
# ---------------------------------------------------------------------------


def test_no_parent_bus_leaves_goal_untouched(mem_dir):
    parent = SimpleNamespace()  # no _memory_bus attribute at all
    assert _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL) == GOAL


def test_none_parent_bus_leaves_goal_untouched(mem_dir):
    parent = SimpleNamespace(_memory_bus=None)
    assert _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL) == GOAL


def test_briefing_appended_exactly_once(mem_dir):
    parent, store = _parent_with_bus(mem_dir)
    out = _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL)
    assert out.count("Memory briefing") == 1
    # A second call (defensive: idempotence on an already-appended goal) must
    # still only ever add one block — the hook never double-wraps its own
    # output because the caller always passes the RAW goal.
    out2 = _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL)
    assert out2.count("Memory briefing") == 1
    store.close()


def test_briefing_has_no_memory_context_fence(mem_dir):
    parent, store = _parent_with_bus(mem_dir)
    out = _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL)
    assert "<memory-context" not in out
    store.close()


def test_briefing_failure_returns_goal_unchanged(mem_dir):
    """'' on error: a bus whose store raises during recall must not break the spawn."""
    store = MemoryStoreV2()
    store.load_from_disk()
    store.close()  # recall against a closed store raises — swallowed by the bus
    parent = SimpleNamespace(_memory_bus=MemoryBus(store=store))
    out = _attach_delegation_briefing(parent, GOAL, "sa-1", GOAL)
    assert out == GOAL


def test_multimodal_goal_gains_briefing_as_text_part(mem_dir):
    parent, store = _parent_with_bus(mem_dir)
    parts = [{"type": "text", "text": GOAL}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,xx"}}]
    out = _attach_delegation_briefing(parent, GOAL, "sa-1", parts)
    assert isinstance(out, list)
    assert len(out) == len(parts) + 1
    assert out[0]["type"] == "text" and out[0]["text"] == GOAL
    assert out[-1]["type"] == "text" and "Memory briefing" in out[-1]["text"]
    store.close()
