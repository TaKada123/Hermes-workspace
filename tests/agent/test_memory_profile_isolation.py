"""Unit tests: MAIN/Design profile isolation of the MEM-V2 memory stack (#10).

The typed store resolves its db path from ``get_hermes_home()`` at CONSTRUCTION
time (the ``HERMES_HOME`` ContextVar override wins over env), and the
orchestrator + bus are plain per-agent attributes wired in ``agent_init``.
Two agents bound to two homes must never share rows, store objects,
orchestrators or bus handles. All homes here are per-test temp dirs — the real
``~/.hermes`` and ``profiles/design`` are never touched.

AC → test:

- MemoryStoreV2 db path resolves per HERMES_HOME; two overridden homes →
  two distinct db files, rows don't mix                     → test_v2_db_path_resolves_per_hermes_home
- orchestrator/bus attributes are per-agent (no module-level shared state)
                                                            → test_orchestrator_and_bus_are_per_agent
- main's context pack never includes design-home rows       → test_main_pack_never_contains_design_rows
- design.route passes only sanctioned context               → test_design_route_prompt_contains_only_sanctioned_context
"""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hermes_constants import reset_hermes_home_override, set_hermes_home_override

CANARY_MAIN = "CANARY-MAIN-профиль-запись-47b1"
CANARY_DESIGN = "CANARY-DESIGN-профиль-запись-9c3d"

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTE_SCRIPT = (
    REPO_ROOT / "runtime-config" / "skills" / "routing"
    / "design-router" / "scripts" / "route_design_profile.py"
)


@pytest.fixture()
def homes(tmp_path):
    """Two distinct profile homes (MAIN + Design) under the test tempdir."""
    main_home = tmp_path / "main-home"
    design_home = tmp_path / "design-home"
    main_home.mkdir(parents=True)
    design_home.mkdir(parents=True)
    return main_home, design_home


def _rows_of(db: Path) -> set:
    conn = sqlite3.connect(str(db))
    try:
        return {row[0] for row in conn.execute("SELECT content FROM memories")}
    finally:
        conn.close()


def test_v2_db_path_resolves_per_hermes_home(homes):
    """AC: two overridden homes → two distinct db files; rows never mix."""
    from agent.memory_store_v2 import MemoryStoreV2

    main_home, design_home = homes

    s_main = None
    token_main = set_hermes_home_override(main_home)
    try:
        s_main = MemoryStoreV2()
        s_main.load_from_disk()
        s_main.add("memory", CANARY_MAIN, entry_type="fact", importance=1.0)
        main_db = s_main._db_path
    finally:
        if s_main is not None:
            s_main.close()
        reset_hermes_home_override(token_main)

    s_design = None
    token_design = set_hermes_home_override(design_home)
    try:
        s_design = MemoryStoreV2()
        s_design.load_from_disk()
        s_design.add("memory", CANARY_DESIGN, entry_type="fact", importance=1.0)
        design_db = s_design._db_path
    finally:
        if s_design is not None:
            s_design.close()
        reset_hermes_home_override(token_design)

    assert main_db == main_home / "memories" / "memory.db", (
        "v2 db must resolve inside the profile's own HERMES_HOME"
    )
    assert design_db == design_home / "memories" / "memory.db"
    assert main_db != design_db, "profiles must own distinct db files"
    assert main_db.is_file() and design_db.is_file()

    main_rows = _rows_of(main_db)
    design_rows = _rows_of(design_db)
    assert any(CANARY_MAIN in row for row in main_rows)
    assert all(CANARY_DESIGN not in row for row in main_rows), "design rows leaked into main db"
    assert any(CANARY_DESIGN in row for row in design_rows)
    assert all(CANARY_MAIN not in row for row in design_rows), "main rows leaked into design db"

    # Store-level recall is home-scoped too: reopening under the main home
    # must surface main's row and never the design one.
    s = None
    token = set_hermes_home_override(main_home)
    try:
        s = MemoryStoreV2()
        s.load_from_disk()
        hits = {str(r["content"]) for r in s.recall_candidates("CANARY", limit=50)}
    finally:
        if s is not None:
            s.close()
        reset_hermes_home_override(token)
    assert any(CANARY_MAIN in content for content in hits)
    assert all(CANARY_DESIGN not in content for content in hits)


def test_orchestrator_and_bus_are_per_agent(homes):
    """AC: orchestrator/bus are per-agent attributes — no module-level shared state."""
    from agent import agent_init
    from agent.memory_store_v2 import MemoryStoreV2

    main_home, design_home = homes
    cfg_v2 = {
        "memory": {
            "backend": "sqlite_v2",
            "orchestrator": {"enabled": True},
            "bus": {"enabled": True},
        }
    }

    def _make(home: Path):
        token = set_hermes_home_override(home)
        try:
            store = MemoryStoreV2()
            store.load_from_disk()
            agent = SimpleNamespace(_memory_enabled=True, _user_profile_enabled=True)
            agent_init._init_memory_orchestrator(agent, cfg_v2, store)
            agent_init._init_memory_bus(agent, cfg_v2, store, None)
            return agent, store, token
        except BaseException:
            reset_hermes_home_override(token)
            raise

    agent_main, store_main, token_main = _make(main_home)
    agent_design, store_design, token_design = _make(design_home)
    try:
        assert agent_main._memory_orchestrator is not None
        assert agent_design._memory_orchestrator is not None
        assert agent_main._memory_orchestrator is not agent_design._memory_orchestrator, (
            "orchestrators must be per-agent instances, not a module-level singleton"
        )
        assert agent_main._memory_orchestrator._store is store_main
        assert agent_design._memory_orchestrator._store is store_design

        assert agent_main._memory_bus is not None
        assert agent_design._memory_bus is not None
        assert agent_main._memory_bus is not agent_design._memory_bus, (
            "bus handles must be per-agent instances, not a module-level singleton"
        )
        assert agent_main._memory_bus.store is store_main
        assert agent_design._memory_bus.store is store_design

        # A third agent built from the same config gets a THIRD pair of
        # instances (each call constructs fresh objects).
        agent_third = SimpleNamespace(_memory_enabled=True, _user_profile_enabled=True)
        agent_init._init_memory_orchestrator(agent_third, cfg_v2, store_main)
        agent_init._init_memory_bus(agent_third, cfg_v2, store_main, None)
        assert agent_third._memory_orchestrator is not agent_main._memory_orchestrator
        assert agent_third._memory_bus is not agent_main._memory_bus
    finally:
        for store in (store_main, store_design):
            store.close()
        reset_hermes_home_override(token_design)
        reset_hermes_home_override(token_main)


def test_main_pack_never_contains_design_rows(homes):
    """AC: the main agent's context pack never includes design-home rows."""
    from agent.memory_orchestrator import MemoryOrchestrator
    from agent.memory_store_v2 import MemoryStoreV2

    main_home, design_home = homes
    evicted_main = "Кластер разворачиваем farmdeploy-манифестом"
    evicted_design = "Дизайн-система бренда — токены из brandkit-токенов"

    # Design home owns a REAL recallable row (proves it exists to leak).
    s = None
    token = set_hermes_home_override(design_home)
    try:
        s = MemoryStoreV2(memory_char_limit=200, user_char_limit=1375)
        s.load_from_disk()
        s.add("memory", evicted_design, entry_type="decision", importance=0.4)
        hits = {str(r["content"]) for r in s.recall_candidates("brandkit", limit=10)}
        assert any(evicted_design in content for content in hits), "design row must be recallable in its own home"
    finally:
        if s is not None:
            s.close()
        reset_hermes_home_override(token)

    # Main home: crowd the snapshot so the main row is evicted from the
    # prompt but searchable — the exact condition the pack exists for.
    token = set_hermes_home_override(main_home)
    s2 = None
    try:
        s = MemoryStoreV2(memory_char_limit=200, user_char_limit=1375)
        s.load_from_disk()
        for i in range(6):
            s.add(
                "memory",
                f"Стоящее решение-наполнитель номер {i} занимает дорожку",
                entry_type="decision", importance=0.95,
            )
        s.add("memory", evicted_main, entry_type="decision", importance=0.4)
        s.close()

        s2 = MemoryStoreV2(memory_char_limit=200, user_char_limit=1375)
        s2.load_from_disk()
        orch = MemoryOrchestrator(s2)
        try:
            pack_main = orch.build_pack("как разворачиваем кластер farmdeploy?")
            pack_design_topic = orch.build_pack("где взять токены бренда brandkit?")
        finally:
            s2.close()
    finally:
        reset_hermes_home_override(token)

    assert evicted_main in pack_main, "main's own evicted row must reach the pack"
    assert evicted_design not in pack_main, "design row leaked into main's pack"
    # Even a query targeting the DESIGN topic must not surface design rows —
    # the main orchestrator can only see its own store.
    assert evicted_design not in pack_design_topic, "design row leaked into main's pack on a design-topic query"


def _load_route_module() -> Any:
    spec = importlib.util.spec_from_file_location("route_design_profile_under_test", ROUTE_SCRIPT)
    assert spec is not None and spec.loader is not None, f"route script missing: {ROUTE_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _handoff_file(tmp_path: Path, **overrides: Any) -> Path:
    """Write a handoff JSON file (the router's real input surface) and return its path."""
    import json

    payload: dict = {
        "schema_version": 1,
        "route_type": "profile",
        "route_id": "design",
        "action_id": "design.route",
        "source_profile": "default",
        "original_user_request": "Сделай лендинг для бренда A",
        "attachments": ["/tmp/mock/brief.png"],
        "project_context": ["Бренд A — минимализм, тёмная тема"],
    }
    payload.update(overrides)
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_design_route_prompt_contains_only_sanctioned_context(tmp_path):
    """AC: design.route passes only sanctioned context; Main memory is never mixed in."""
    mod = _load_route_module()
    handoff_path = _handoff_file(
        tmp_path,
        # Un-sanctioned Main-agent context smuggled into the handoff file must
        # be dropped by the router — it only forwards the sanctioned fields.
        main_memory=["CANARY-MAIN-MEMORY-11aa секрет деплоя"],
        reasoning="CANARY-MAIN-REASONING-22bb размышления про деплой",
        main_notes="CANARY-MAIN-NOTES-33cc",
    )

    data = mod._load(handoff_path)  # valid: extra keys are tolerated by validation…
    prompt = mod._prompt(data)  # …but the PROMPT is built from sanctioned fields only.

    assert data["original_user_request"] in prompt, "original user request must ride verbatim"
    assert "design.route" in prompt
    assert "attachments" in prompt and "brief.png" in prompt
    assert "project_context" in prompt and "Бренд A — минимализм" in prompt
    assert "CANARY-MAIN-MEMORY-11aa" not in prompt, "Main memory content leaked into the route handoff"
    assert "CANARY-MAIN-REASONING-22bb" not in prompt, "Main reasoning leaked into the route handoff"
    assert "CANARY-MAIN-NOTES-33cc" not in prompt

    # Exact shape: metadata block + verbatim request, nothing else.
    expected = (
        "[PROFILE ROUTING CONTRACT — metadata, not a rewrite]\n"
        "{\n"
        '  "schema_version": 1,\n'
        '  "route_type": "profile",\n'
        '  "route_id": "design",\n'
        '  "action_id": "design.route",\n'
        '  "source_profile": "default",\n'
        '  "attachments": [\n'
        '    "/tmp/mock/brief.png"\n'
        "  ],\n"
        '  "project_context": [\n'
        '    "Бренд A — минимализм, тёмная тема"\n'
        "  ]\n"
        "}\n"
        "\n[ORIGINAL USER REQUEST — VERBATIM]\n"
        "Сделай лендинг для бренда A\n"
        "[END ORIGINAL USER REQUEST]\n"
    )
    assert prompt == expected


def test_design_route_validation_rejects_malformed_handoffs(tmp_path):
    """AC: the router refuses handoffs that would widen the sanctioned surface."""
    mod = _load_route_module()

    with pytest.raises(ValueError, match="original_user_request"):
        mod._load(_handoff_file(tmp_path, original_user_request="   "))
    with pytest.raises(ValueError, match="action_id"):
        mod._load(_handoff_file(tmp_path, action_id="main.memory.read"))
    with pytest.raises(ValueError, match="route_id"):
        mod._load(_handoff_file(tmp_path, route_id="main"))
    with pytest.raises(ValueError, match="attachments"):
        mod._load(_handoff_file(tmp_path, attachments=["ok", 42]))
    with pytest.raises(ValueError, match="project_context"):
        mod._load(_handoff_file(tmp_path, project_context=[123]))
    with pytest.raises(ValueError, match="100000"):
        mod._load(_handoff_file(tmp_path, original_user_request="x" * 100_001))
