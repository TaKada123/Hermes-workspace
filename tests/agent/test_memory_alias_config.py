"""Aliases are config input: reject bad shapes before clearing a working cache."""
import pytest

from agent.memory_store_v2 import MemoryAliasConfigError, MemoryStoreV2


@pytest.mark.parametrize("malformed", [
    [], "network", False, 42,
    {"": ["vpn"]}, {7: ["vpn"]},
    {"network": None}, {"network": 42}, {"network": {"vpn": True}},
    {"network": ["vpn", False]}, {"network": [" "]},
    {"valid": ["vpn"], "bad": ["ok", {"nested": "value"}]},
])
def test_rejected_alias_config_preserves_live_and_persisted_expansion(tmp_path, monkeypatch, malformed):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = MemoryStoreV2()
    store.load_from_disk()
    store.set_alias_cache({"network": ["vpn", "tunnel"]})
    expected = store.normalized_query("network")
    try:
        with pytest.raises(MemoryAliasConfigError, match="memory.aliases") as raised:
            store.set_alias_cache(malformed)
        assert raised.value.key.startswith("memory.aliases")
        assert raised.value.cause
        assert raised.value.remediation
        assert "expected" in str(raised.value)
        assert "Set memory.aliases" in str(raised.value)
        assert store.normalized_query("network") == expected
    finally:
        store.close()
    reloaded = MemoryStoreV2()
    try:
        reloaded.load_from_disk()
        assert reloaded.normalized_query("network") == expected
    finally:
        reloaded.close()


def test_rejected_alias_config_before_load_does_not_create_a_database(tmp_path, monkeypatch):
    home = tmp_path / "absent"
    monkeypatch.setenv("HERMES_HOME", str(home))
    store = MemoryStoreV2()
    with pytest.raises(MemoryAliasConfigError, match="memory.aliases"):
        store.set_alias_cache(["vpn"])
    assert not home.exists()


@pytest.mark.parametrize("aliases", ["VPN", ["VPN", "vpn"], (" VPN ",)])
def test_supported_scalar_list_and_tuple_aliases_remain_normalized(tmp_path, monkeypatch, aliases):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = MemoryStoreV2()
    try:
        store.load_from_disk()
        store.set_alias_cache({" NETWORK ": aliases})
        assert store.normalized_query("network").exact_terms == ("vpn",)
    finally:
        store.close()


@pytest.mark.parametrize("aliases", [None, {}, {"network": []}])
def test_absent_or_explicit_empty_aliases_can_clear_cache(tmp_path, monkeypatch, aliases):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = MemoryStoreV2()
    try:
        store.load_from_disk()
        baseline = store.normalized_query("network")
        store.set_alias_cache({"network": "vpn"})
        store.set_alias_cache(aliases)
        assert store.normalized_query("network") == baseline
    finally:
        store.close()
