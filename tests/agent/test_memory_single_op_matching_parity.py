"""Public single writes must select the same real entry as the legacy store."""

import json

import pytest

import tools.memory_tool as mt
from agent.memory_store_v2 import MemoryStoreV2
from tools.memory_tool_store import MemoryStore


@pytest.mark.parametrize("api", ["tool", "store"])
@pytest.mark.parametrize("action", ["replace", "remove"])
@pytest.mark.parametrize("entries,old_text,selected", [
    (["test", "longer test entry"], "test", "test"),
    (["Test", "test", "longer test entry"], "test", "test"),
    (["TEST", "longer test entry"], "test", "longer test entry"),
    (["TEST", "Test"], "test", None),
    (["rate 100% done", "rate 1000 done"], "100%", "rate 100% done"),
    (["key_a value", "keyXa value"], "key_a", "key_a value"),
    (["plain text"], "%", None),
    (["plain text"], "_", None),
    (["Ёж", "ёж", "small ёж entry"], "ёж", "ёж"),
    (["ЁЖ lives here", "ёж lives there"], "ёж", "ёж lives there"),
    (["first needle entry", "second needle entry"], "needle", None),
    (["ordinary entry"], "absent", None),
])
def test_single_write_matches_legacy_entry(tmp_path, monkeypatch, api, action,
                                           entries, old_text, selected):
    outcomes = []
    for backend in (MemoryStore, MemoryStoreV2):
        directory = tmp_path / backend.__name__
        directory.mkdir()
        monkeypatch.setattr(mt, "get_memory_dir", lambda d=directory: d)
        monkeypatch.setenv("HERMES_HOME", str(directory / "home"))
        store = backend()
        try:
            store.load_from_disk()
            for entry in entries:
                assert store.add("memory", entry)["success"]
            if api == "tool":
                result = json.loads(mt.memory_tool(
                    action=action, target="memory", old_text=old_text,
                    content="replacement fact" if action == "replace" else "",
                    store=store))
            elif action == "replace":
                result = store.replace("memory", old_text, "replacement fact")
            else:
                result = store.remove("memory", old_text)
            remaining = sorted(store._entries_for("memory"))
            expected = list(entries)
            if selected is not None:
                expected.remove(selected)
                if action == "replace":
                    expected.append("replacement fact")
                assert result["success"] is True, result
                assert result["done"] is True
                assert result["target"] == "memory"
                assert result["entry_count"] == len(expected)
                assert "current_entries" not in result
            else:
                assert result["success"] is False, result
                assert "error" in result
            assert remaining == sorted(expected)
            outcomes.append(result)
        finally:
            if isinstance(store, MemoryStoreV2):
                store.close()
    # V2's existing no-match guidance mentions old_id; preserve its JSON
    # shape and retry entries without changing that established wording.
    if selected is None:
        assert outcomes[1].keys() == outcomes[0].keys()
        for key in outcomes[0].keys() - {"error"}:
            assert outcomes[1][key] == outcomes[0][key]
        if "matches" in outcomes[0]:
            assert outcomes[1]["error"] == outcomes[0]["error"]
        else:
            assert outcomes[1]["error"].startswith(f"No entry matched '{old_text}'")


@pytest.mark.parametrize("entries,old_text,selected", [
    (["test", "longer test entry"], "test", "test"),
    (["Ёж", "ёж", "small ёж entry"], "ёж", "ёж"),
    (["rate 100% done", "rate 1000 done"], "100%", "rate 100% done"),
    (["key_a value", "keyXa value"], "key_a", "key_a value"),
    (["TEST", "Test"], "test", None),
    (["first needle entry", "second needle entry"], "needle", None),
])
def test_deprecate_uses_same_literal_exact_first_resolution(
        tmp_path, monkeypatch, entries, old_text, selected):
    monkeypatch.setattr(mt, "get_memory_dir", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    store = MemoryStoreV2()
    try:
        store.load_from_disk()
        for entry in entries:
            assert store.add("memory", entry)["success"]
        result = json.loads(mt.memory_tool(
            action="deprecate", target="memory", old_text=old_text,
            reason="outdated fact", store=store))
        assert result["success"] is (selected is not None), result
        rows = store._connect().execute(
            "SELECT content, status FROM memories WHERE target='memory'").fetchall()
        assert {r["content"] for r in rows if r["status"] == "deprecated"} == (
            {selected} if selected is not None else set())
        assert {r["content"] for r in rows} == set(entries)
    finally:
        store.close()


@pytest.mark.parametrize("action", ["replace", "remove", "deprecate"])
def test_pin_still_overrides_exact_match_and_never_rematches(
        tmp_path, monkeypatch, action):
    monkeypatch.setattr(mt, "get_memory_dir", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    store = MemoryStoreV2()
    try:
        store.load_from_disk()
        for entry in ("test", "longer test entry"):
            assert store.add("memory", entry)["success"]
        def edit():
            if action == "replace":
                return store.replace("memory", "test", "replacement fact",
                                     matched_entry="longer test entry")
            return getattr(store, action)(
                "memory", "test", matched_entry="longer test entry")
        assert edit()["success"] is True
        before = [tuple(r) for r in store._connect().execute(
            "SELECT id, content, status FROM memories ORDER BY id")]
        stale = edit()
        assert stale["success"] is False
        assert "changed since it was staged" in stale["error"]
        assert [tuple(r) for r in store._connect().execute(
            "SELECT id, content, status FROM memories ORDER BY id")] == before
        assert "test" in store._entries_for("memory")
    finally:
        store.close()
