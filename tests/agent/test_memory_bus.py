# Ported from the Architecture 2.0 Hermes fork (MIT License)
# Copyright (c) 2025-2026 Dmitry Antipin (multi-agent orchestration fork)
# Source: commit 0c76ec28, sha256 bd9b259e1a32bcdb6998b15e0fda921220ddb013023be6ed9d9ea653cd80b181
"""Tests for the Cognitive Memory Bus (Phase 3 of the memory roadmap).

Ported from the Architecture 2.0 fork (tests/agent/test_memory_bus.py,
commit 0c76ec28) and adapted for ticket #7:

- Rollback is a SEPARATE capability right (``rollback:memory`` /
  ``rollback:user``) — arch2 had none; every bus-rollback path is gated
  on it and the refusals are covered by a parametrized capability matrix.
- The store-level tests (written_by provenance, realm filter, scoped
  revert) stay: they are the acceptance evidence for "rollback touches
  only the consumer's own rows".
- Dropped from the arch2 file: the v1→v2 schema-migration test (store
  migration is owned by tickets #3/#4, covered in test_memory_store_v2.py)
  and the tools/delegate_tool + memory-tool provenance tests (owned by
  tickets #5/#8 — the workspace memory tool does not accept written_by
  until #5 lands).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agent.memory_bus import (
    ALL_CAPABILITIES,
    READ_MEMORY,
    READ_USER,
    ROLLBACK_MEMORY,
    ROLLBACK_USER,
    WRITE_MEMORY,
    WRITE_USER,
    ConsumerSpec,
    MemoryBus,
    build_delegation_briefing,
)
from agent.memory_store_v2 import MemoryStoreV2


@pytest.fixture()
def mem_dir(tmp_path, monkeypatch):
    """Isolated temp HERMES_HOME per test — store DB + projections live there."""
    home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home / "memories"


def _fresh(mem_dir: Path, **kw) -> MemoryStoreV2:
    s = MemoryStoreV2(**kw)
    s.load_from_disk()
    return s


def _bus(store, **kw) -> MemoryBus:
    return MemoryBus(store=store, targets=kw.pop("targets", ("memory", "user")), **kw)


# ============================================================================
# Store — written_by provenance, realm filter, scoped revert
# ============================================================================

def test_written_by_persisted(mem_dir):
    s = _fresh(mem_dir)
    s.add("memory", "Запись с провенансом", entry_type="fact", written_by="main:sess-1")
    row = s.recent_entries(limit=5)[0]
    assert row["written_by"] == "main:sess-1"
    s.close()


def test_written_by_optional_backwards_compatible(mem_dir):
    s = _fresh(mem_dir)
    r = s.add("memory", "Обычная запись без провенанса")
    assert r["success"]
    assert s.recent_entries(limit=5)[0]["written_by"] is None
    s.close()


def test_project_realm_filter_in_recall_candidates(mem_dir):
    s = _fresh(mem_dir)
    s.add("memory", "Правило проекта hermes про тесты", entry_type="constraint", project="hermes")
    s.add("memory", "Секрет проекта skynet", entry_type="fact", project="skynet")
    s.add("memory", "Глобальное правило бэкапов", entry_type="constraint")
    s.close()

    s2 = _fresh(mem_dir)
    hermes_view = [c["content"] for c in s2.recall_candidates("правило секрет", project="hermes")]
    assert any("hermes" in c for c in hermes_view), "own project visible"
    assert any("Глобальное" in c for c in hermes_view), "global rows visible"
    assert not any("skynet" in c for c in hermes_view), "foreign project invisible (Codex §8.4)"
    s2.close()


def test_rollback_consumer_deprecates_only_that_scope(mem_dir):
    s = _fresh(mem_dir)
    s.add("memory", "Вывод делегации А", entry_type="fact", written_by="delegation:sa-1")
    s.add("memory", "Вывод делегации Б", entry_type="fact", written_by="delegation:sa-2")
    s.add("memory", "Запись основного агента", entry_type="fact", written_by="main:sess-9")
    s.close()

    s2 = _fresh(mem_dir)
    result = s2.rollback_consumer("delegation:sa-1", reason="scoped revert: бракованный batch")
    assert result["success"] and result["deprecated"] == 1
    hits = s2.recall("Вывод делегации")
    contents = [h["content"] for h in hits["results"]]
    assert contents == ["Вывод делегации Б"], "only the rolled-back scope disappears"
    # The main agent's record is untouched.
    assert s2.recall("основного агента")["count"] == 1
    # Deprecated rows stay auditable, not deleted (roadmap §1.7).
    dep = s2._query("SELECT status, deprecate_reason FROM memories WHERE written_by='delegation:sa-1'")[0]
    assert dep["status"] == "deprecated" and "scoped revert" in dep["deprecate_reason"]
    s2.close()


def test_rollback_consumer_rejects_empty_scope(mem_dir):
    s = _fresh(mem_dir)
    assert not s.rollback_consumer("")["success"]
    s.close()


def test_rollback_consumer_target_scoping(mem_dir):
    """Store-level per-target revert: ``target`` filters by written_by AND
    target; ``target=None`` keeps the cross-target revert."""
    s = _fresh(mem_dir)
    s.add("memory", "Память делегации", entry_type="fact", written_by="delegation:sa-1")
    s.add("user", "Профиль делегации", entry_type="preference", written_by="delegation:sa-1")
    s.add("memory", "Чужая память", entry_type="fact", written_by="main:sess-9")
    s.close()

    s2 = _fresh(mem_dir)
    result = s2.rollback_consumer("delegation:sa-1", target="memory")
    assert result["success"] and result["deprecated"] == 1
    assert result["target"] == "memory"
    # The writer's USER row is untouched — the revert is per-target.
    user_rows = s2._query("SELECT status FROM memories WHERE written_by='delegation:sa-1' AND target='user'")
    assert user_rows and user_rows[0]["status"] == "active"
    # Other writers untouched.
    assert s2._query("SELECT status FROM memories WHERE written_by='main:sess-9'")[0]["status"] == "active"

    # Cross-target revert without a target: both of the writer's rows go.
    result2 = s2.rollback_consumer("delegation:sa-1")
    assert result2["success"] and result2["deprecated"] == 1
    assert result2["target"] is None
    left = s2._query(
        "SELECT status FROM memories WHERE written_by='delegation:sa-1'"
    )
    assert all(r["status"] == "deprecated" for r in left)
    s2.close()


def test_rollback_consumer_rejects_unknown_target(mem_dir):
    s = _fresh(mem_dir)
    r = s.rollback_consumer("delegation:x", target="disk")
    assert not r["success"] and "Unknown target" in r["error"]
    s.close()


# ============================================================================
# Bus — coeffect subscriptions + capability derivation
# ============================================================================

def test_capabilities_derived_from_targets(mem_dir):
    s = _fresh(mem_dir)
    s.close()
    bus = MemoryBus(store=None)
    assert bus.capabilities() == frozenset()
    bus2 = _bus(s, targets=("memory",))
    assert bus2.capabilities() == frozenset({READ_MEMORY, WRITE_MEMORY, ROLLBACK_MEMORY})
    bus3 = _bus(s)
    assert bus3.capabilities() == frozenset(ALL_CAPABILITIES)
    s.close()


class _NoRollbackStore:
    """Duck store exposing everything except ``rollback_consumer``."""

    def __init__(self, real: MemoryStoreV2):
        self._real = real

    def __getattr__(self, name):
        if name == "rollback_consumer":
            raise AttributeError("rollback_consumer")
        return getattr(self._real, name)


def test_rollback_capability_derived_only_when_store_supports_it(mem_dir):
    s = _fresh(mem_dir)
    proxy = _NoRollbackStore(s)
    bus = _bus(proxy)
    caps = bus.capabilities()
    assert {READ_MEMORY, READ_USER, WRITE_MEMORY, WRITE_USER} <= caps
    assert ROLLBACK_MEMORY not in caps and ROLLBACK_USER not in caps
    # A subscription needing rollback is unsatisfiable → refused, not activated.
    sub = bus.subscribe(ConsumerSpec("rb", needs=frozenset({READ_MEMORY, ROLLBACK_MEMORY})))
    assert sub is None
    assert bus.subscription("rb") is None
    s.close()


def test_subscribe_satisfaction_predicate(mem_dir):
    s = _fresh(mem_dir)
    bus = _bus(s)
    # Satisfied: every requested capability exists.
    assert bus.subscribe(ConsumerSpec("main:x", needs=frozenset(ALL_CAPABILITIES))) is not None
    # Unsatisfiable: a target the bus doesn't offer → NOT activated.
    narrow = _bus(s, targets=("memory",))
    assert narrow.subscribe(ConsumerSpec("u1", needs=frozenset({READ_USER}))) is None
    assert narrow.subscription("u1") is None
    # Malformed: empty id / unknown capability keys only.
    assert bus.subscribe(ConsumerSpec("", needs=frozenset({READ_MEMORY}))) is None
    assert bus.subscribe(ConsumerSpec("bad", needs=frozenset({"fly:moon"}))) is None
    assert bus.subscription("bad") is None
    s.close()


def test_subscribe_warns_on_refusal(mem_dir, caplog):
    s = _fresh(mem_dir)
    bus = _bus(s)
    with caplog.at_level(logging.WARNING, logger="agent.memory_bus"):
        bus.subscribe(ConsumerSpec("", needs=frozenset({READ_MEMORY})))
        bus.subscribe(ConsumerSpec("u2", needs=frozenset({"fly:moon"})))
    s.close()


def test_readonly_is_structural_not_polite(mem_dir):
    s = _fresh(mem_dir)
    bus = _bus(s)
    sub = bus.subscribe(ConsumerSpec("subagent:ro", needs=frozenset({READ_MEMORY})))
    assert sub is not None and sub.spec.read_only
    w = bus.remember("попытка записи", consumer_id="subagent:ro", entry_type="fact")
    assert not w["success"] and "read-only" in w["error"]
    r = bus.rollback("subagent:ro", target="memory")
    assert not r["success"] and "rollback refused" in r["error"]
    s.close()


def test_refresh_capabilities_reactive_transitions(mem_dir):
    """A source change deactivates unsatisfied subscriptions and reactivates
    them when the capability returns (research doc §2)."""
    s = _fresh(mem_dir)
    bus = _bus(s)
    sub = bus.subscribe(ConsumerSpec("c1", needs=frozenset({READ_USER, WRITE_USER})))
    assert sub.active
    bus.targets = ("memory",)  # user source dropped
    bus.refresh_capabilities()
    assert not sub.active and sub.deactivation_reason
    # A read on a deactivated consumer is refused, not half-alive.
    res = bus.recall("что угодно", consumer_id="c1")
    assert not res["success"]
    bus.targets = ("memory", "user")
    bus.refresh_capabilities()
    assert sub.active and sub.deactivation_reason is None
    s.close()


def test_recall_requires_subscription(mem_dir):
    s = _fresh(mem_dir)
    bus = _bus(s)
    res = bus.recall("тест", consumer_id="ghost")
    assert not res["success"] and "no active read subscription" in res["error"]
    s.close()


def test_recall_target_visibility_follows_needs(mem_dir):
    """A consumer holding only read:memory must not see user-profile rows."""
    s = _fresh(mem_dir)
    s.add("memory", "Правило проекта", entry_type="constraint")
    s.add("user", "Личные предпочтения Дмитрия", entry_type="preference")
    s.close()
    s2 = _fresh(mem_dir)
    bus = _bus(s2)
    bus.subscribe(ConsumerSpec("worker", needs=frozenset({READ_MEMORY})))
    res = bus.recall("правило предпочтения", consumer_id="worker")
    assert res["success"]
    assert all(e["content"] != "Личные предпочтения Дмитрия" for e in res["entries"])
    s2.close()


def test_recall_realm_from_spec(mem_dir):
    s = _fresh(mem_dir)
    s.add("memory", "Тонкости проекта hermes", entry_type="fact", project="hermes")
    s.add("memory", "Тонкости проекта skynet", entry_type="fact", project="skynet")
    s.close()
    s2 = _fresh(mem_dir)
    bus = _bus(s2)
    bus.subscribe(ConsumerSpec("scoped", needs=frozenset({READ_MEMORY}), project="hermes"))
    res = bus.recall("тонкости проекта", consumer_id="scoped")
    contents = [e["content"] for e in res["entries"]]
    assert any("hermes" in c for c in contents)
    assert not any("skynet" in c for c in contents)
    s2.close()


def test_remember_provenance_project_and_mirror(mem_dir):
    s = _fresh(mem_dir)
    mirrored = []
    manager = type("M", (), {"on_memory_write": staticmethod(
        lambda action, target, content, metadata=None: mirrored.append((action, target, content, metadata))
    )})()
    bus = MemoryBus(store=s, manager=manager, targets=("memory", "user"))
    bus.subscribe(ConsumerSpec(
        "delegation:sa-7", needs=frozenset({READ_MEMORY, WRITE_MEMORY}), project="hermes",
    ))
    r = bus.remember("Финальный вывод: миграция ok", consumer_id="delegation:sa-7", entry_type="fact")
    assert r["success"]
    row = s.recent_entries(limit=5)[0]
    assert row["written_by"] == "delegation:sa-7"
    assert row["project"] == "hermes"
    assert mirrored and mirrored[0][2] == "Финальный вывод: миграция ok"
    s.close()


def test_scoped_view_pins_spec_and_can_write_only_with_caps(mem_dir):
    s = _fresh(mem_dir)
    bus = _bus(s)
    view = bus.scoped_view(ConsumerSpec(
        "delegation:w", needs=frozenset({READ_MEMORY, WRITE_MEMORY, ROLLBACK_MEMORY}),
    ))
    assert view is not None
    assert view.remember("вывод")["success"]
    assert view.rollback(target="memory")["deprecated"] == 1
    ro = bus.scoped_view(ConsumerSpec("subagent:ro", needs=frozenset({READ_MEMORY})))
    assert ro is not None
    assert not ro.remember("нет прав")["success"]
    assert not ro.rollback(target="memory")["success"]
    s.close()


# ============================================================================
# Rollback as a separate right (ticket #7 — NEW design, arch2 lacks it)
# ============================================================================

def test_write_capability_does_not_imply_rollback(mem_dir):
    """A write-capable consumer must still be refused rollback (story 11)."""
    s = _fresh(mem_dir)
    bus = _bus(s)
    bus.subscribe(ConsumerSpec("w1", needs=frozenset({READ_MEMORY, WRITE_MEMORY})))
    assert bus.remember("запись", consumer_id="w1")["success"]
    r = bus.rollback("w1", target="memory")
    assert not r["success"] and "rollback refused" in r["error"]
    # Store-level scoping is untouched: the consumer's rows stay active.
    assert s.recent_entries(limit=5)[0]["status"] == "active"
    s.close()


def test_rollback_works_without_write_capability(mem_dir):
    """Rollback is independent of write: a consumer with rollback rights
    but no write caps can still revert its own (previously written) rows."""
    s = _fresh(mem_dir)
    s.add("memory", "Ранее написанное", entry_type="fact", written_by="rb-1")
    s.close()
    s2 = _fresh(mem_dir)
    bus = _bus(s2)
    bus.subscribe(ConsumerSpec("rb-1", needs=frozenset({READ_MEMORY, ROLLBACK_MEMORY})))
    r = bus.rollback("rb-1", target="memory")
    assert r["success"] and r["deprecated"] == 1
    s2.close()


def test_rollback_target_consent_gate(mem_dir):
    """Explicit target requires the matching rollback capability."""
    s = _fresh(mem_dir)
    bus = _bus(s)
    bus.subscribe(ConsumerSpec("mixed", needs=frozenset({READ_MEMORY, ROLLBACK_MEMORY})))
    assert bus.rollback("mixed", target="memory")["success"]
    r = bus.rollback("mixed", target="user")
    assert not r["success"] and "rollback refused" in r["error"]
    s.close()


def test_rollback_requires_explicit_target(mem_dir):
    """The bus rollback must NAME the target — a bare call is refused
    instead of silently reverting both stores."""
    s = _fresh(mem_dir)
    bus = _bus(s)
    bus.subscribe(ConsumerSpec("all", needs=frozenset(ALL_CAPABILITIES)))
    r = bus.rollback("all")
    assert not r["success"] and "rollback refused" in r["error"]
    assert "target" in r["error"]
    # The store was never reached: the consumer's rows stay active.
    s.add("memory", "запись", entry_type="fact", written_by="all")
    assert s.recent_entries(limit=5)[0]["status"] == "active"
    s.close()


def test_rollback_memory_only_cannot_revert_user_rows(mem_dir):
    """A rollback:memory-only consumer CANNOT revert user rows, and its
    memory-target rollback never touches its own user rows."""
    s = _fresh(mem_dir)
    s.add("memory", "Память этого потребителя", entry_type="fact", written_by="part")
    s.add("user", "Профиль этого потребителя", entry_type="preference", written_by="part")
    s.close()
    s2 = _fresh(mem_dir)
    bus = _bus(s2)
    bus.subscribe(ConsumerSpec("part", needs=frozenset({READ_MEMORY, ROLLBACK_MEMORY})))
    r = bus.rollback("part", target="user")
    assert not r["success"] and "rollback refused" in r["error"]
    # The refusal is structural: nothing changed.
    assert s2._query("SELECT status FROM memories WHERE written_by='part' AND target='user'")[0]["status"] == "active"
    r = bus.rollback("part", target="memory")
    assert r["success"] and r["deprecated"] == 1
    assert s2._query("SELECT status FROM memories WHERE written_by='part' AND target='memory'")[0]["status"] == "deprecated"
    # The consumer's USER rows are untouched by the memory-target revert.
    assert s2._query("SELECT status FROM memories WHERE written_by='part' AND target='user'")[0]["status"] == "active"
    s2.close()


def test_rollback_both_caps_can_revert_each_target(mem_dir):
    """A consumer holding both rollback caps can revert each target —
    and each call only touches the named target."""
    s = _fresh(mem_dir)
    s.add("memory", "Память оба", entry_type="fact", written_by="both")
    s.add("user", "Профиль оба", entry_type="preference", written_by="both")
    s.add("memory", "Чужая запись", entry_type="fact", written_by="main:sess-9")
    s.close()
    s2 = _fresh(mem_dir)
    bus = _bus(s2)
    bus.subscribe(ConsumerSpec(
        "both", needs=frozenset({READ_MEMORY, READ_USER, ROLLBACK_MEMORY, ROLLBACK_USER}),
    ))
    r = bus.rollback("both", target="memory")
    assert r["success"] and r["deprecated"] == 1
    assert s2._query("SELECT status FROM memories WHERE written_by='both' AND target='user'")[0]["status"] == "active"
    r = bus.rollback("both", target="user")
    assert r["success"] and r["deprecated"] == 1
    # Other writers' rows untouched throughout.
    assert s2._query("SELECT status FROM memories WHERE written_by='main:sess-9'")[0]["status"] == "active"
    s2.close()


def test_rollback_spec_with_rollback_cap_is_not_read_only(mem_dir):
    """ConsumerSpec.read_only means NO write AND NO rollback caps: a spec
    holding only ``rollback:memory`` is NOT read-only."""
    spec = ConsumerSpec("rb", needs=frozenset({READ_MEMORY, ROLLBACK_MEMORY}))
    assert not spec.read_only
    assert ConsumerSpec("ro", needs=frozenset({READ_MEMORY})).read_only
    assert ConsumerSpec("rw", needs=frozenset({READ_MEMORY, WRITE_MEMORY})).read_only is False
    s = _fresh(mem_dir)
    s.close()


def test_bus_rollback_only_touches_own_consumer_rows(mem_dir):
    """Scoped revert through the bus: other consumers', MAIN's and
    anonymous rows stay active."""
    s = _fresh(mem_dir)
    bus = _bus(s)
    bus.subscribe(ConsumerSpec(
        "delegation:a", needs=frozenset({READ_MEMORY, WRITE_MEMORY, ROLLBACK_MEMORY}),
    ))
    bus.subscribe(ConsumerSpec(
        "delegation:b", needs=frozenset({READ_MEMORY, WRITE_MEMORY, ROLLBACK_MEMORY}),
    ))
    assert bus.remember("Вывод А один", consumer_id="delegation:a")["success"]
    assert bus.remember("Вывод А два", consumer_id="delegation:a")["success"]
    assert bus.remember("Вывод Б", consumer_id="delegation:b")["success"]
    s.add("memory", "Запись MAIN", entry_type="fact", written_by="main:sess-9")
    s.add("memory", "Запись без провенанса", entry_type="fact")

    r = bus.rollback("delegation:a", reason="scoped revert через bus", target="memory")
    assert r["success"] and r["deprecated"] == 2

    # Only A's rows are deprecated — never deleted, still auditable.
    a_rows = s._query(
        "SELECT status, deprecate_reason FROM memories WHERE written_by='delegation:a'"
    )
    assert len(a_rows) == 2
    assert all(row["status"] == "deprecated" for row in a_rows)
    assert all("scoped revert через bus" in row["deprecate_reason"] for row in a_rows)
    # B, MAIN and anonymous rows stay active and visible.
    assert s.recall("Вывод Б")["count"] == 1
    assert s.recall("Запись MAIN")["count"] == 1
    assert s.recall("Запись без провенанса")["count"] == 1
    s.close()


def test_bus_realm_consumer_sees_only_own_and_global(mem_dir):
    s = _fresh(mem_dir)
    s.add("memory", "Правило проекта hermes", entry_type="constraint", project="hermes")
    s.add("memory", "Правило проекта skynet", entry_type="constraint", project="skynet")
    s.add("memory", "Глобальное правило", entry_type="constraint")
    s.close()
    s2 = _fresh(mem_dir)
    bus = _bus(s2)
    bus.subscribe(ConsumerSpec("scoped", needs=frozenset({READ_MEMORY}), project="hermes"))
    res = bus.recall("правило", consumer_id="scoped")
    contents = [e["content"] for e in res["entries"]]
    assert "Правило проекта hermes" in contents, "own project visible"
    assert "Глобальное правило" in contents, "global rows visible"
    assert "Правило проекта skynet" not in contents, "foreign project invisible"
    # Bus writes carry the realm too.
    w = bus.scoped_view(ConsumerSpec(
        "scoped-w", needs=frozenset({READ_MEMORY, WRITE_MEMORY}), project="hermes",
    ))
    assert w is not None and w.remember("Новая запись realm")["success"]
    row = [r for r in s2.recent_entries(limit=10) if r["content"] == "Новая запись realm"][0]
    assert row["project"] == "hermes"
    s2.close()


# ============================================================================
# Capability refusal matrix — every refusal path, parametrized (AC)
# ============================================================================

class TestCapabilityRefusalMatrix:
    """One parametrized grid over every refusal the bus can produce.

    Covers: read-only write refusal (both targets), read-only rollback
    refusal (implicit + explicit target), write-cap-without-rollback
    rollback refusal, wrong-target rollback cap, unknown targets,
    unsubscribed and deactivated consumers.
    """

    # (name, needs, action, kwargs, expected_error_substr)
    CASES = [
        ("read-only-write-memory", {READ_MEMORY}, "remember",
         {"target": "memory", "content": "матрица запись"}, "write refused"),
        ("read-only-write-user", {READ_MEMORY}, "remember",
         {"target": "user", "content": "матрица запись"}, "write refused"),
        ("read-only-user-write", {READ_USER}, "remember",
         {"target": "user", "content": "матрица запись"}, "write refused"),
        ("read-only-rollback-no-target", {READ_MEMORY}, "rollback",
         {}, "rollback refused"),
        ("read-only-rollback-no-target-user", {READ_USER}, "rollback",
         {}, "rollback refused"),
        ("read-only-rollback-explicit-memory", {READ_MEMORY}, "rollback",
         {"target": "memory"}, "rollback refused"),
        ("read-only-rollback-explicit-user", {READ_USER}, "rollback",
         {"target": "user"}, "rollback refused"),
        ("write-memory-without-rollback", {READ_MEMORY, WRITE_MEMORY}, "rollback",
         {"target": "memory"}, "rollback refused"),
        ("write-user-without-rollback", {READ_USER, WRITE_USER}, "rollback",
         {"target": "user"}, "rollback refused"),
        ("write-memory-without-rollback-implicit", {READ_MEMORY, WRITE_MEMORY}, "rollback",
         {}, "rollback refused"),
        ("rollback-user-asking-memory", {READ_MEMORY, ROLLBACK_USER}, "rollback",
         {"target": "memory"}, "rollback refused"),
        ("rollback-memory-asking-user", {READ_USER, ROLLBACK_MEMORY}, "rollback",
         {"target": "user"}, "rollback refused"),
        ("unknown-target-write", {READ_MEMORY, WRITE_MEMORY}, "remember",
         {"target": "disk", "content": "матрица запись"}, "Unknown target"),
        ("unknown-target-rollback", {READ_MEMORY, ROLLBACK_MEMORY}, "rollback",
         {"target": "disk"}, "Unknown target"),
        ("unsubscribed-write", None, "remember",
         {"target": "memory", "content": "матрица запись"}, "write refused"),
        ("unsubscribed-rollback", None, "rollback",
         {}, "rollback refused"),
        ("unsubscribed-rollback-explicit", None, "rollback",
         {"target": "memory"}, "rollback refused"),
    ]

    @pytest.mark.parametrize(
        "name,needs,action,kwargs,expected",
        CASES,
        ids=[c[0] for c in CASES],
    )
    def test_refused(self, mem_dir, name, needs, action, kwargs, expected):
        s = _fresh(mem_dir)
        bus = _bus(s)
        if needs is not None:
            sub = bus.subscribe(ConsumerSpec("m1", needs=frozenset(needs)))
            assert sub is not None, f"matrix case {name}: subscription must activate"
        fn = getattr(bus, action)
        result = fn(consumer_id="m1", **kwargs)
        assert not result["success"], name
        assert expected in result["error"], name
        # Refused actions never reach the store: no rows beyond the schema.
        s.close()


class TestDeactivatedRefusalMatrix:
    """Deactivation flips every consumer right off — writes and rollbacks
    of a deactivated subscription are refused, not half-alive."""

    @pytest.mark.parametrize(
        "action,kwargs,expected",
        [
            ("recall", {"query": "любое"}, "no active read subscription"),
            ("remember", {"target": "memory", "content": "запись"}, "write refused"),
            ("rollback", {}, "rollback refused"),
            ("rollback", {"target": "memory"}, "rollback refused"),
        ],
        ids=["recall", "write", "rollback-no-target", "rollback-explicit"],
    )
    def test_deactivated_subscription_refused(self, mem_dir, action, kwargs, expected):
        s = _fresh(mem_dir)
        bus = _bus(s)
        sub = bus.subscribe(ConsumerSpec("d1", needs=frozenset(
            {READ_MEMORY, WRITE_MEMORY, ROLLBACK_MEMORY, ROLLBACK_USER},
        )))
        assert sub is not None and sub.active
        bus.targets = ("memory",)
        bus.refresh_capabilities()
        assert not sub.active
        result = getattr(bus, action)(consumer_id="d1", **kwargs)
        assert not result["success"]
        assert expected in result["error"]
        s.close()


class TestCapabilityGrantMatrix:
    """The positive half of the matrix: granted rights actually work."""

    CASES = [
        ("write-memory-granted", {READ_MEMORY, WRITE_MEMORY}, "remember",
         {"target": "memory", "content": "грант запись"}),
        ("write-user-granted", {READ_USER, WRITE_USER}, "remember",
         {"target": "user", "content": "грант запись"}),
        ("rollback-memory-granted", {READ_MEMORY, ROLLBACK_MEMORY}, "rollback",
         {"target": "memory"}),
        ("rollback-user-granted", {READ_USER, ROLLBACK_USER}, "rollback",
         {"target": "user"}),
        ("rollback-full-granted", ALL_CAPABILITIES, "rollback",
         {"target": "memory"}),
    ]

    @pytest.mark.parametrize(
        "name,needs,action,kwargs",
        CASES,
        ids=[c[0] for c in CASES],
    )
    def test_granted(self, mem_dir, name, needs, action, kwargs):
        s = _fresh(mem_dir)
        bus = _bus(s)
        sub = bus.subscribe(ConsumerSpec("g1", needs=frozenset(needs)))
        assert sub is not None, name
        result = getattr(bus, action)(consumer_id="g1", **kwargs)
        assert result["success"], name
        s.close()


# ============================================================================
# agent_init wiring (ticket #8) — bus budgets come from config, not hardcoded
# ============================================================================

def _init_bus_via_agent_init(mem_dir, memory_cfg: dict):
    """Run the REAL ``agent_init._init_memory_bus`` against a stub agent."""
    from agent.agent_init import _init_memory_bus

    s = _fresh(mem_dir)
    agent = type("A", (), {})()
    _init_memory_bus(agent, {"memory": memory_cfg}, s, None)
    return agent


def test_agent_init_bus_reads_orchestrator_budget_from_config(mem_dir):
    """memory.orchestrator.token_budget/max_entries drive the bus budget —
    the hardcoded 2500/20 are replaced by config values."""
    agent = _init_bus_via_agent_init(mem_dir, {
        "backend": "sqlite_v2",
        "bus": {"enabled": True},
        "orchestrator": {"token_budget": 123, "max_entries": 4},
    })
    bus = getattr(agent, "_memory_bus", None)
    assert bus is not None
    assert bus.token_budget == 123
    assert bus.max_entries == 4


def test_agent_init_bus_budget_falls_back_to_defaults(mem_dir):
    """No orchestrator block (or malformed values) → 2500/20 defaults."""
    agent = _init_bus_via_agent_init(mem_dir, {
        "backend": "sqlite_v2",
        "bus": {"enabled": True},
    })
    bus = getattr(agent, "_memory_bus", None)
    assert bus is not None
    assert (bus.token_budget, bus.max_entries) == (2500, 20)


def test_agent_init_bus_absent_on_legacy_backend(mem_dir):
    agent = _init_bus_via_agent_init(mem_dir, {"backend": "file"})
    assert getattr(agent, "_memory_bus", None) is None


# ============================================================================
# Delegation briefing (roadmap 3.2)
# ============================================================================

def test_delegation_briefing_from_parent_bus(mem_dir):
    s = _fresh(mem_dir)
    s.add("memory", "Правило проекта: тесты через run_tests.sh", entry_type="constraint", importance=0.9)
    s.close()
    s2 = _fresh(mem_dir)
    bus = _bus(s2)
    parent = type("P", (), {"_memory_bus": bus})()
    brief = build_delegation_briefing(parent, "прогони тесты проекта по правилам")
    assert "Memory briefing" in brief
    assert "run_tests.sh" in brief
    assert "<memory-context" not in brief, "briefing uses its own plain-markdown slot"
    s2.close()


def test_delegation_briefing_respects_realm(mem_dir):
    s = _fresh(mem_dir)
    s.add("memory", "Секрет skynet", entry_type="fact", project="skynet", importance=0.9)
    s.add("memory", "Правило hermes", entry_type="constraint", project="hermes", importance=0.9)
    s.close()
    s2 = _fresh(mem_dir)
    parent = type("P", (), {"_memory_bus": _bus(s2)})()
    brief = build_delegation_briefing(parent, "секреты и правила проекта", subagent_id="sa-1", project="hermes")
    assert "Правило hermes" in brief
    assert "skynet" not in brief
    s2.close()


def test_delegation_briefing_no_bus_or_failure(mem_dir):
    parent_no_bus = type("P", (), {})()
    assert build_delegation_briefing(parent_no_bus, "цель") == ""
    s = _fresh(mem_dir)
    s.add("memory", "запись", entry_type="fact")
    s.close()
    s2 = _fresh(mem_dir)
    broken_bus = _bus(s2)
    broken_bus.store.recall_candidates = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    parent_broken = type("P", (), {"_memory_bus": broken_bus})()
    assert build_delegation_briefing(parent_broken, "цель") == ""
    s2.close()


def test_delegation_briefing_logs_evidence_line(mem_dir, caplog):
    """Non-empty delegation briefings emit one INFO line (agent.log evidence)."""
    s = _fresh(mem_dir)
    s.add("memory", "Правило проекта про тесты", entry_type="constraint", importance=0.9)
    s.close()
    s2 = _fresh(mem_dir)
    parent = type("P", (), {"_memory_bus": _bus(s2)})()
    with caplog.at_level(logging.INFO, logger="agent.memory_bus"):
        build_delegation_briefing(parent, "правила тестирования", subagent_id="sa-1")
        lines = [r for r in caplog.records if "delegation briefing" in r.message]
        assert len(lines) == 1 and "subagent:sa-1" in lines[0].message
    s2.close()
