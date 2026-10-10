"""Whole rendered context packs must fit, admitting only complete records."""

import pytest

from agent.memory_orchestrator import MemoryOrchestrator, ScoringWeights
from agent.memory_store_v2 import MemoryStoreV2
from agent.model_metadata import estimate_tokens_rough


@pytest.fixture
def rich_store():
    store = MemoryStoreV2(memory_char_limit=1, user_char_limit=1)
    store.load_from_disk()
    for i, kind in enumerate(("decision", "constraint", "pattern", "preference", "fact", "legacy")):
        target = "user" if i % 2 else "memory"
        old = store.add(target, f"Old quartz record {i}: " + "история " * 15, entry_type=kind)
        assert old["success"]
        new = store.supersede(target, old_id=old["id"], content=f"quartz record-{i}",
                              entry_type=kind, importance=0.5, reason="updated")
        assert new["success"]
    store.load_from_disk()
    assert not store.snapshot_contents()
    yield store
    store.close()


@pytest.mark.parametrize("budget", [0, 1, 100, 150, 220, 300, 400, 600])
def test_whole_rendered_pack_fits_and_access_bumps_only_emitted_records(rich_store, budget):
    rows = rich_store.recent_entries(limit=30)
    before = {r["id"]: r["access_count"] for r in rows}
    pack = MemoryOrchestrator(rich_store, token_budget=budget).build_pack("quartz")
    assert estimate_tokens_rough(pack) <= budget
    after = {r["id"]: r["access_count"] for r in rich_store.recent_entries(limit=30)}
    for row in rows:
        emitted = row["content"] in pack
        assert after[row["id"]] - before[row["id"]] == int(emitted)
        if emitted:
            assert row["id"][:8] in pack
            assert "[supersedes:" in pack
    if budget >= 220:
        assert pack, "small complete records should still fit"


def test_exact_rendered_boundary_and_one_less_admit_complete_record(rich_store):
    full = MemoryOrchestrator(rich_store, max_entries=1).build_pack("quartz")
    size = estimate_tokens_rough(full)
    exact = MemoryOrchestrator(rich_store, max_entries=1, token_budget=size).build_pack("quartz")
    assert exact == full
    smaller = MemoryOrchestrator(rich_store, max_entries=1, token_budget=size - 1).build_pack("quartz")
    assert estimate_tokens_rough(smaller) <= size - 1
    assert smaller != full


def test_skips_oversized_top_record_and_keeps_deterministic_ranked_complete_records(rich_store):
    huge = rich_store.add("memory", "quartz huge " + "payload " * 1000,
                          entry_type="decision", importance=1.0)
    assert huge["success"]
    orch = MemoryOrchestrator(rich_store, token_budget=300, max_entries=2,
                              weights=ScoringWeights(importance=1, recency=0))
    first = orch.build_pack("quartz")
    assert first and "quartz huge" not in first
    assert estimate_tokens_rough(first) <= 300
    assert first.count("- [") <= 2
    assert orch.build_pack("quartz") == first


@pytest.mark.parametrize("budget", [0, 18, 36, 100])
def test_bus_recall_preserves_content_budget_skip_and_max_entries(rich_store, budget):
    from agent.memory_bus import ConsumerSpec, MemoryBus, READ_MEMORY, READ_USER

    assert rich_store.add("memory", "quartz huge " + "payload " * 1000,
                          entry_type="decision", importance=1)["success"]
    bus = MemoryBus(rich_store, token_budget=budget, max_entries=2)
    assert bus.subscribe(ConsumerSpec("budget-test", needs=frozenset({READ_MEMORY, READ_USER})))
    result = bus.recall("quartz", consumer_id="budget-test")
    assert result["success"]
    assert result["count"] <= 2
    assert sum(estimate_tokens_rough(r["content"]) + 8 for r in result["entries"]) <= budget
    assert all("quartz huge" not in r["content"] for r in result["entries"])
    if budget >= 18:
        assert result["count"] > 0


def test_measured_admission_retains_weighted_order_inside_relevance_classes():
    store = MemoryStoreV2(memory_char_limit=1, user_char_limit=1)
    store.load_from_disk()
    try:
        assert store.add("memory", "quartz amber decision", entry_type="decision", importance=0.1)["success"]
        assert store.add("memory", "quartz amber fact", entry_type="fact", importance=0.9)["success"]
        assert store.add("memory", "quartz partial", entry_type="decision", importance=1)["success"]
        by_importance = MemoryOrchestrator(store, token_budget=150, max_entries=1,
            weights=ScoringWeights(relevance=0, importance=1, project_link=0,
                                   decision_value=0, recency=0, confidence=0)).build_pack("quartz amber")
        assert "quartz amber fact" in by_importance
        assert "quartz partial" not in by_importance
        by_decision = MemoryOrchestrator(store, token_budget=150, max_entries=1,
            weights=ScoringWeights(relevance=0, importance=0, project_link=0,
                                   decision_value=1, recency=0, confidence=0)).build_pack("quartz amber")
        assert "quartz amber decision" in by_decision
        assert "quartz partial" not in by_decision
    finally:
        store.close()
