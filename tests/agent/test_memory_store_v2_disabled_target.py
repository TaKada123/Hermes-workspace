"""Cross-target correction respects the actual store's enable flag (#3/#5)."""

import pytest

from agent.memory_store_v2 import MemoryStoreV2


@pytest.mark.parametrize("actual_target", ["memory", "user"])
@pytest.mark.parametrize("action", ["deprecate", "supersede"])
def test_disabled_actual_target_refused_without_side_effects(tmp_path, monkeypatch, actual_target, action):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profile"))
    store = MemoryStoreV2()
    store.load_from_disk()
    try:
        assert store.add(actual_target, "Original standing rule")["success"]
        assert store.add(actual_target, "Existing successor rule")["success"]
        rows = store.visible_rows(actual_target)
        old_id = next(r["id"] for r in rows if r["content"] == "Original standing rule")
        successor_id = next(r["id"] for r in rows if r["content"] == "Existing successor rule")
        paths = [store.db_path.parent / name for name in ("MEMORY.md", "USER.md")]
        before = {p: p.read_bytes() if p.exists() else None for p in paths}
        if actual_target == "memory":
            store.memory_enabled = False
        else:
            store.user_profile_enabled = False
        requested = "user" if actual_target == "memory" else "memory"
        if action == "deprecate":
            result = store.deprecate(requested, old_id=old_id[:8], superseded_by_id=successor_id, reason="revision")
        else:
            result = store.supersede(requested, old_id[:8], "Replacement standing rule", reason="revision")
        assert not result["success"]
        assert actual_target in result["error"] and "disabled" in result["error"]
        assert store.visible_rows(actual_target) == rows
        assert store.supersedes_neighbors([old_id, successor_id]) == {}
        assert {p: p.read_bytes() if p.exists() else None for p in paths} == before
    finally:
        store.close()


@pytest.mark.parametrize("actual_target", ["memory", "user"])
@pytest.mark.parametrize("action", ["deprecate", "supersede"])
def test_enabled_cross_target_correction_still_works(tmp_path, monkeypatch, actual_target, action):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profile"))
    store = MemoryStoreV2()
    store.load_from_disk()
    try:
        assert store.add(actual_target, "Original standing rule")["success"]
        old_id = store.visible_rows(actual_target)[0]["id"]
        requested = "user" if actual_target == "memory" else "memory"
        if action == "deprecate":
            result = store.deprecate(requested, old_id=old_id[:8], reason="revision")
        else:
            result = store.supersede(requested, old_id[:8], "Replacement standing rule", reason="revision")
        assert result["success"] and result["target"] == actual_target
        assert all(r["id"] != old_id for r in store.visible_rows(actual_target))
        if action == "supersede":
            assert store.supersedes_neighbors([result["new_id"]])[result["new_id"]][0]["id"] == old_id
    finally:
        store.close()
