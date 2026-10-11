# Ported from the Architecture 2.0 Hermes fork (MIT License)
# Copyright (c) 2025-2026 Dmitry Antipin (multi-agent orchestration fork)
"""Schema + registry-wiring tests for the v2-extended memory tool (ticket #5).

The v2 action surface extends the existing schema ADDITIVELY (the legacy
add/replace/remove/operations contract stays byte-identical) and the registry
handler must pass ALL new params through — arch2 dropped written_by/old_id/
superseded_by_id in its registration lambda (a defect we must not inherit).
"""

from __future__ import annotations

import json

import pytest

import tools.memory_tool as mt
from tools.memory_tool import MEMORY_SCHEMA, registry
from agent.memory_store_v2 import MemoryStoreV2


def test_action_enum_gains_v2_actions():
    assert MEMORY_SCHEMA["parameters"]["properties"]["action"]["enum"] == [
        "add", "replace", "remove", "supersede", "deprecate", "read",
    ]


def test_v2_params_present_and_optional():
    props = MEMORY_SCHEMA["parameters"]["properties"]
    for key in ("old_id", "superseded_by_id", "type", "importance", "query", "reason"):
        assert key in props, key
    assert props["type"]["enum"] == [
        "fact", "decision", "constraint", "pattern", "preference"]
    assert props["importance"]["minimum"] == 0
    assert props["importance"]["maximum"] == 1
    # Optional fields stay optional; target stays the only required key
    # (the Codex-rejected allOf/if-then shape must not come back).
    assert MEMORY_SCHEMA["parameters"].get("required") == ["target"]
    _FORBIDDEN = ("allOf", "anyOf", "oneOf", "enum", "not")
    for key in _FORBIDDEN:
        assert key not in MEMORY_SCHEMA["parameters"], key


def test_legacy_contract_unchanged():
    # Legacy surface intact: same enum inside operations, same aliases.
    params = MEMORY_SCHEMA["parameters"]
    assert params["properties"]["operations"]["items"]["properties"]["action"]["enum"] == [
        "add", "replace", "remove"]
    assert params["properties"]["target"]["enum"] == ["memory", "user"]
    assert "new_text" in params["properties"]
    assert "content" in params["properties"]
    assert "old_text" in params["properties"]


def _memory_entry():
    return next(e for e in registry.get_all_entries() if e.name == "memory")


def test_registry_handler_passes_all_params(tmp_path, monkeypatch):
    """The arch2 registry lambda dropped written_by/old_id/superseded_by_id —
    the ported handler must wire ALL of them through to the store."""
    monkeypatch.setattr(mt, "get_memory_dir", lambda: tmp_path)
    store = MemoryStoreV2()
    store.load_from_disk()
    try:
        entry = _memory_entry()

        # add: type/importance/written_by arrive at the store.
        res = json.loads(entry.handler({
            "action": "add", "target": "memory", "content": "handled entry",
            "type": "constraint", "importance": 0.9, "written_by": "main:test",
        }, store=store))
        assert res["success"], res
        rows = list(store._connect().execute(
            "SELECT type, importance, written_by FROM memories"
            " WHERE content='handled entry'").fetchall())
        assert len(rows) == 1
        assert rows[0]["type"] == "constraint"
        assert abs(rows[0]["importance"] - 0.9) < 1e-9
        assert rows[0]["written_by"] == "main:test"

        # supersede: old_id + reason + written_by arrive at the store.
        first = store.add("memory", "entry to supersede")
        res2 = json.loads(entry.handler({
            "action": "supersede", "target": "memory", "old_id": first["id"],
            "content": "replacement entry", "reason": "because",
            "type": "decision", "importance": 0.85, "written_by": "main:test",
        }, store=store))
        assert res2["success"], res2
        assert res2["new_id"]

        # deprecate: old_id + superseded_by_id + reason arrive at the store.
        # (A separate entry: the supersede above already deprecated `first`.)
        third = store.add("memory", "standalone entry to deprecate")
        res3 = json.loads(entry.handler({
            "action": "deprecate", "target": "memory", "old_id": third["id"],
            "superseded_by_id": res2["new_id"], "reason": "superseded",
        }, store=store))
        assert res3["success"], res3
        assert res3.get("link_created") is True

        # read: query arrives at the store.
        res4 = json.loads(entry.handler({
            "action": "read", "target": "memory", "query": "replacement",
        }, store=store))
        assert res4["success"], res4
        assert res4["count"] >= 1
    finally:
        store.close()


def test_handler_still_dispatches_legacy_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(mt, "get_memory_dir", lambda: tmp_path)
    store = MemoryStoreV2()
    store.load_from_disk()
    try:
        entry = _memory_entry()
        res = json.loads(entry.handler({
            "action": "add", "target": "memory", "content": "plain legacy call",
        }, store=store))
        assert res["success"], res
        assert store.recall("plain legacy call")["count"] == 1
    finally:
        store.close()


def test_pending_summary_warns_about_unverifiable_old_id_pin():
    """An old ID-only proposal is no longer a verified revision pin."""
    from hermes_cli.write_approval_commands import _matched_entries
    lines = _matched_entries({
        "action": "supersede", "target": "memory", "old_id": "abc123",
        "content": "new entry"})
    assert "unpinned legacy target" in lines[0]
    lines = _matched_entries({
        "action": "deprecate", "target": "memory", "old_text": "x",
        "matched_entry": "Full entry text"})
    assert lines == ["deprecates entry: Full entry text"]
