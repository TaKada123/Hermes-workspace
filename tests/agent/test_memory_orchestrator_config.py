"""Configuration rejection at the public MEM-V2 build boundary."""

from contextlib import closing

import pytest

from agent.memory_orchestrator import ScoringWeights, build_memory_orchestrator
from agent.memory_store_v2 import MemoryStoreV2


@pytest.mark.parametrize("key,value", [
    ("token_budget", "many"), ("token_budget", None),
    ("token_budget", -1), ("token_budget", 1.5),
    ("token_budget", True), ("token_budget", float("inf")),
    ("max_entries", "many"), ("max_entries", None),
    ("max_entries", 0), ("max_entries", -1),
    ("max_entries", 1.5), ("max_entries", False),
    ("max_entries", float("nan")),
    ("weights", []), ("weights", "relevance=1"), ("weights", None),
    ("weights.relevance", "bad"), ("weights.importance", None),
    ("weights.recency", float("nan")), ("weights.confidence", float("inf")),
    ("weights.project_link", -0.1), ("weights.decision_value", True),
])
def test_supplied_unusable_config_is_rejected_with_remediation(key, value):
    cfg = {"weights": {key.split(".")[1]: value}} if "." in key else {key: value}
    with closing(MemoryStoreV2()) as store:
        with pytest.raises(ValueError) as error:
            build_memory_orchestrator(store, {"orchestrator": cfg},
                                      memory_enabled=True, user_profile_enabled=True)
    message = str(error.value)
    assert f"memory.orchestrator.{key}" in message
    assert "must be" in message
    assert "set " in message.lower()


@pytest.mark.parametrize("value", [[], "bad", 0, None])
def test_supplied_orchestrator_section_must_be_a_mapping(value):
    with closing(MemoryStoreV2()) as store:
        with pytest.raises(ValueError, match=r"memory\.orchestrator.*mapping.*[Ss]et"):
            build_memory_orchestrator(store, {"orchestrator": value},
                                      memory_enabled=True, user_profile_enabled=True)


@pytest.mark.parametrize("value", [[], "bad", {"relevance": "bad"},
                                        {"relevance": float("nan")}, {"relevance": -1}])
def test_weights_public_config_boundary_rejects_unusable_values(value):
    with pytest.raises(ValueError, match=r"memory\.orchestrator\.weights"):
        ScoringWeights.from_config(value)


def test_absent_defaults_and_compatible_numeric_strings():
    with closing(MemoryStoreV2()) as store:
        default = build_memory_orchestrator(store, {}, memory_enabled=True, user_profile_enabled=True)
        assert default.token_budget == 2500
        assert default.weights == ScoringWeights()
        configured = build_memory_orchestrator(store, {"orchestrator": {
            "token_budget": "0", "max_entries": "2", "weights": {"relevance": "2.5", "unknown": "ignored"},
        }}, memory_enabled=True, user_profile_enabled=True)
        assert configured.token_budget == 0
        assert configured.build_pack("Docker") == ""
        assert configured.weights.relevance == 2.5
        assert ScoringWeights.from_config(None) == ScoringWeights()
