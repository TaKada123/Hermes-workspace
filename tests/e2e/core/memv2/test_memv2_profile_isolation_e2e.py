"""E2E for ticket #10 — MAIN/Design profile isolation over separate HERMES_HOMEs.

Everything real except the model: each profile's agent runs as a REAL
subprocess (fresh interpreter, ``env HERMES_HOME=<profile home>``) against a
recording ``FakeLLMServer``, so a cross-profile payload leak would be a
genuine code leak, not an in-process test artifact. All homes are temp dirs
under ``tmp_path`` — the real ``~/.hermes`` and ``~/.hermes/profiles/design``
are never touched.

Acceptance criteria covered (AC → test):

- canary strings never cross profiles (snapshot + context pack checked) → test_canary_memory_never_crosses_profiles
- SOUL + skills load from each profile's own HERMES_HOME                → test_soul_and_skills_load_per_profile
- a write in one process is seen by a NEW process of the same profile   → test_persistence_across_real_process_restart
- design.route passes only sanctioned context (no Main memory)          → test_design_route_handoff_payload_is_sanctioned
- backend flag is per-profile (main file + design sqlite_v2 mixed)      → test_backend_flag_is_per_profile

Runs only under ``--include-integration -m integration`` (e2e/ is skipped by
default discovery).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall, write_hermes_home

REPO_ROOT = Path(__file__).resolve().parents[4]
ROUTE_SCRIPT = (
    REPO_ROOT / "runtime-config" / "skills" / "routing"
    / "design-router" / "scripts" / "route_design_profile.py"
)

PACK_HEADER = "## Retrieved memory"

CANARY_MAIN_SNAP = "CANARY-MAIN-SNAP-7f3a правило: деплой только по понедельникам"
CANARY_MAIN_PACK = "CANARY-MAIN-PACK-d2e8: кластер разворачиваем farmdeploy-манифестом"
CANARY_DESIGN_SNAP = "CANARY-DESIGN-SNAP-1b6c правило: макеты сначала в Figma"
CANARY_DESIGN_PACK = "CANARY-DESIGN-PACK-f0a7: фирменный стиль рендерим через brandkit-токены"

_FILLER = "Стоящее решение-наполнитель номер {i} занимает дорожку"

_V2_EXTRA_CONFIG = (
    "memory:\n"
    "  backend: sqlite_v2\n"
    "  memory_char_limit: 1500\n"
    "  user_char_limit: 1375\n"
    "  nudge_interval: 0\n"
    "  orchestrator:\n"
    "    enabled: true\n"
    "skills:\n"
    "  creation_nudge_interval: 0\n"
    "updates:\n"
    "  check: false\n"
    "models_dev:\n"
    "  url: http://127.0.0.1:9/api.json\n"
)

_LEGACY_EXTRA_CONFIG = (
    "memory:\n"
    "  backend: file\n"
    "  memory_char_limit: 1500\n"
    "  user_char_limit: 1375\n"
    "  nudge_interval: 0\n"
    "skills:\n"
    "  creation_nudge_interval: 0\n"
    "updates:\n"
    "  check: false\n"
    "models_dev:\n"
    "  url: http://127.0.0.1:9/api.json\n"
)

# Fresh-interpreter agent run: reads the turn prompts + provider endpoint from
# argv JSON, runs them against the recording server, prints {"ok": true} and
# exits 0 — or exits 3 with the error. HERMES_HOME (the profile home) comes
# from the environment set by _run_profile_agent.
_RUNNER = r"""
import json, sys
from run_agent import AIAgent

spec = json.loads(sys.argv[1])
agent = AIAgent(
    provider="custom",
    base_url=spec["base_url"],
    api_key="sk-fake-e2e",
    model="fake-model",
    quiet_mode=True,
    enabled_toolsets=spec.get("toolsets", ["memory"]),
    skip_context_files=True,
    load_soul_identity=True,
    skip_background_review=True,
)
try:
    history = []
    for i, prompt in enumerate(spec["prompts"]):
        r = agent.run_conversation(prompt, conversation_history=history, task_id="t%d" % i)
        if not r.get("final_response"):
            print(json.dumps({"ok": False, "error": r.get("error")}, ensure_ascii=False))
            sys.exit(3)
        history = r["messages"]
    print(json.dumps({"ok": True}, ensure_ascii=False))
finally:
    try:
        agent.close()
    except Exception:
        pass
"""


def _run_profile_agent(home: Path, base_url: str, prompts: list[str],
                       toolsets: list[str] | None = None) -> subprocess.CompletedProcess:
    """One real profile-agent process: fresh interpreter, HERMES_HOME=home."""
    spec = {"base_url": base_url, "prompts": prompts, "toolsets": toolsets or ["memory"]}
    env = {**os.environ, "HERMES_HOME": str(home), "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-c", _RUNNER, json.dumps(spec, ensure_ascii=False)],
        cwd=str(home), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=240,
    )


def _assert_agent_ok(proc: subprocess.CompletedProcess, label: str) -> None:
    assert proc.returncode == 0, (
        f"{label} agent process failed (rc={proc.returncode}):\n"
        f"stdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}"
    )


def _user_contents(req: dict) -> list:
    return [
        str(m.get("content", ""))
        for m in req.get("messages", [])
        if m.get("role") == "user" and isinstance(m.get("content"), str)
    ]


def _system_contents(req: dict) -> list:
    return [
        str(m.get("content", ""))
        for m in req.get("messages", [])
        if m.get("role") == "system" and isinstance(m.get("content"), str)
    ]


def _all_contents(req: dict) -> str:
    return "".join(str(m.get("content", "")) for m in req.get("messages", []))


def _seed_v2(home: Path, snap_canary: str, pack_canary: str, fillers: int = 40) -> None:
    """Seed a profile home's typed store BEFORE the agent process starts.

    ``snap_canary`` (importance 1.0) outranks the fillers and lands in the
    frozen snapshot; ``pack_canary`` (importance 0.4) is crowded out of the
    snapshot but stays searchable — the exact condition the context pack
    exists for.
    """
    from agent.memory_store_v2 import MemoryStoreV2
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    token = set_hermes_home_override(home)
    store = None
    try:
        store = MemoryStoreV2(memory_char_limit=1500, user_char_limit=1375)
        store.load_from_disk()
        store.add("memory", snap_canary, entry_type="decision", importance=1.0)
        for i in range(fillers):
            store.add("memory", _FILLER.format(i=i), entry_type="decision", importance=0.95)
        store.add("memory", pack_canary, entry_type="decision", importance=0.4)
    finally:
        if store is not None:
            store.close()
        reset_hermes_home_override(token)


@pytest.mark.integration
def test_canary_memory_never_crosses_profiles(tmp_path):
    """AC: main memory never appears in the Design payload and vice versa.

    Checks BOTH the frozen snapshot block in the system prompt AND the
    per-turn context pack of each profile's real provider payload.
    """
    main_home = tmp_path / "main-home"
    design_home = tmp_path / "design-home"
    main_home.mkdir(parents=True)
    design_home.mkdir(parents=True)

    _seed_v2(main_home, CANARY_MAIN_SNAP, CANARY_MAIN_PACK)
    _seed_v2(design_home, CANARY_DESIGN_SNAP, CANARY_DESIGN_PACK)

    main_script = [
        ToolCall("memory", {"action": "add", "target": "memory",
                            "content": "Кластер обновляем только через farmdeploy-манифест",
                            "entry_type": "fact"}),
        Text("Записал."),
        Text("Через farmdeploy-манифест."),
    ]
    with FakeLLMServer(main_script) as srv_main:
        write_hermes_home(main_home, srv_main.base_url, extra_config=_V2_EXTRA_CONFIG)
        proc = _run_profile_agent(
            main_home, srv_main.base_url,
            ["запомни: кластер обновляем только через farmdeploy-манифест",
             "как разворачиваем кластер farmdeploy?"],
        )
        _assert_agent_ok(proc, "main")
        reqs = srv_main.main_requests()

        # Frozen snapshot block: main's canary is in the system prompt.
        assert any(CANARY_MAIN_SNAP in c for req in reqs for c in _system_contents(req)), (
            "main's snapshot canary must ride the frozen system-prompt block"
        )
        # Context pack: the evicted main canary rides the relevant turn's user message.
        pack_carriers = [c for req in reqs for c in _user_contents(req) if PACK_HEADER in c]
        assert pack_carriers, "main's relevant turn must receive a context pack"
        assert any(CANARY_MAIN_PACK in c for c in pack_carriers), "main's pack must carry its own row"
        assert all(CANARY_DESIGN_SNAP not in c for c in pack_carriers)

        # Cross-profile canaries must never appear in ANY request of main's run.
        for req in reqs:
            blob = _all_contents(req)
            assert CANARY_DESIGN_SNAP not in blob, "design snapshot canary leaked into main payload"
            assert CANARY_DESIGN_PACK not in blob, "design pack canary leaked into main payload"

    design_script = [
        ToolCall("memory", {"action": "add", "target": "memory",
                            "content": "Макеты сначала собираем в Figma",
                            "entry_type": "fact"}),
        Text("Записал."),
        Text("Через brandkit-токены."),
    ]
    with FakeLLMServer(design_script) as srv_design:
        write_hermes_home(design_home, srv_design.base_url, extra_config=_V2_EXTRA_CONFIG)
        proc = _run_profile_agent(
            design_home, srv_design.base_url,
            ["запомни: макеты сначала собираем в Figma",
             "как рендерим фирменный стиль brandkit?"],
        )
        _assert_agent_ok(proc, "design")
        reqs = srv_design.main_requests()

        assert any(CANARY_DESIGN_SNAP in c for req in reqs for c in _system_contents(req)), (
            "design's snapshot canary must ride its frozen system-prompt block"
        )
        pack_carriers = [c for req in reqs for c in _user_contents(req) if PACK_HEADER in c]
        assert pack_carriers, "design's relevant turn must receive a context pack"
        assert any(CANARY_DESIGN_PACK in c for c in pack_carriers), "design's pack must carry its own row"
        assert all(CANARY_MAIN_SNAP not in c for c in pack_carriers)

        for req in reqs:
            blob = _all_contents(req)
            assert CANARY_MAIN_SNAP not in blob, "main snapshot canary leaked into design payload"
            assert CANARY_MAIN_PACK not in blob, "main pack canary leaked into design payload"


@pytest.mark.integration
def test_soul_and_skills_load_per_profile(tmp_path):
    """AC: SOUL and skills of each profile load from its own HERMES_HOME."""
    main_home = tmp_path / "main-home"
    design_home = tmp_path / "design-home"
    main_home.mkdir(parents=True)
    design_home.mkdir(parents=True)

    SOUL_MAIN = "SOUL-MAIN-MARKER-88cd: ты главный инженерный агент"
    SOUL_DESIGN = "SOUL-DESIGN-MARKER-4f1e: ты ведущий дизайнер"
    SKILL_MAIN = "SKILL-MAIN-MARKER-77aa: чек-лист деплоя"
    SKILL_DESIGN = "SKILL-DESIGN-MARKER-3b9e: ревью фирменного стиля"

    (main_home / "SOUL.md").write_text(f"{SOUL_MAIN}\n", encoding="utf-8")
    (design_home / "SOUL.md").write_text(f"{SOUL_DESIGN}\n", encoding="utf-8")
    (main_home / "skills" / "iso-main").mkdir(parents=True)
    (main_home / "skills" / "iso-main" / "SKILL.md").write_text(
        f"---\nname: iso-main\ndescription: {SKILL_MAIN}\n---\n\nbody\n", encoding="utf-8",
    )
    (design_home / "skills" / "iso-design").mkdir(parents=True)
    (design_home / "skills" / "iso-design" / "SKILL.md").write_text(
        f"---\nname: iso-design\ndescription: {SKILL_DESIGN}\n---\n\nbody\n", encoding="utf-8",
    )

    with FakeLLMServer([Text("привет")]) as srv_main:
        write_hermes_home(main_home, srv_main.base_url, extra_config=_V2_EXTRA_CONFIG)
        proc = _run_profile_agent(main_home, srv_main.base_url, ["привет"], toolsets=["memory", "skills"])
        _assert_agent_ok(proc, "main")
        sys_main = "".join(c for req in srv_main.main_requests() for c in _system_contents(req))
        assert SOUL_MAIN in sys_main, "main's SOUL must load from its own home"
        assert SOUL_DESIGN not in sys_main, "design's SOUL leaked into main's prompt"
        assert SKILL_MAIN in sys_main, "main's skills must load from its own home"
        assert SKILL_DESIGN not in sys_main, "design's skills leaked into main's prompt"

    with FakeLLMServer([Text("привет")]) as srv_design:
        write_hermes_home(design_home, srv_design.base_url, extra_config=_V2_EXTRA_CONFIG)
        proc = _run_profile_agent(design_home, srv_design.base_url, ["привет"], toolsets=["memory", "skills"])
        _assert_agent_ok(proc, "design")
        sys_design = "".join(c for req in srv_design.main_requests() for c in _system_contents(req))
        assert SOUL_DESIGN in sys_design, "design's SOUL must load from its own home"
        assert SOUL_MAIN not in sys_design, "main's SOUL leaked into design's prompt"
        assert SKILL_DESIGN in sys_design, "design's skills must load from its own home"
        assert SKILL_MAIN not in sys_design, "main's skills leaked into design's prompt"


@pytest.mark.integration
def test_persistence_across_real_process_restart(tmp_path):
    """AC: a write in one process is visible to a NEW process of the same profile."""
    home = tmp_path / "design-home"
    home.mkdir(parents=True)
    persisted = "CANARY-PERSIST-e11a: сервер гипервизора обновляется только в четверг"

    # Process 1: a real agent writes the entry through the memory tool.
    with FakeLLMServer([
        ToolCall("memory", {"action": "add", "target": "memory",
                            "content": persisted, "entry_type": "fact"}),
        Text("Записал."),
    ]) as srv1:
        write_hermes_home(home, srv1.base_url, extra_config=_V2_EXTRA_CONFIG)
        proc1 = _run_profile_agent(
            home, srv1.base_url, ["запомни: сервер гипервизора обновляется только в четверг"],
        )
        _assert_agent_ok(proc1, "writer")

    db = home / "memories" / "memory.db"
    assert db.is_file(), "the write must land in the profile's sqlite memory db"

    # Process 2: a FRESH interpreter with the same home recalls the entry.
    with FakeLLMServer([Text("В четверг.")]) as srv2:
        write_hermes_home(home, srv2.base_url, extra_config=_V2_EXTRA_CONFIG)
        proc2 = _run_profile_agent(
            home, srv2.base_url, ["когда обновляем сервер гипервизора?"],
        )
        _assert_agent_ok(proc2, "reader")
        blob = "".join(_all_contents(req) for req in srv2.main_requests())
        assert persisted in blob, (
            "the new process must recall the entry persisted by the previous process"
        )


@pytest.mark.integration
def test_backend_flag_is_per_profile(tmp_path):
    """AC: the backend flag is per-profile — main on legacy file, design on sqlite_v2."""
    main_home = tmp_path / "main-home"
    design_home = tmp_path / "design-home"
    main_home.mkdir(parents=True)
    design_home.mkdir(parents=True)

    legacy_canary = "CANARY-LEGACY-MAIN-5c2a: сборку гоняем через make build"

    # Main: legacy file backend — seed MEMORY.md through the flat store.
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override
    from tools.memory_tool_store import MemoryStore

    token = set_hermes_home_override(main_home)
    try:
        store = MemoryStore(memory_char_limit=1500, user_char_limit=1375)
        store.load_from_disk()
        store.add("memory", legacy_canary)
    finally:
        reset_hermes_home_override(token)

    # Design: sqlite_v2 with a crowded snapshot — its canary needs the pack.
    _seed_v2(design_home, CANARY_DESIGN_SNAP, CANARY_DESIGN_PACK)

    with FakeLLMServer([Text("make build")]) as srv_main:
        write_hermes_home(main_home, srv_main.base_url, extra_config=_LEGACY_EXTRA_CONFIG)
        proc = _run_profile_agent(main_home, srv_main.base_url, ["как гоняем сборку?"])
        _assert_agent_ok(proc, "main-legacy")
        reqs = srv_main.main_requests()
        # Legacy: canary rides the frozen snapshot, never a pack.
        assert any(legacy_canary in c for req in reqs for c in _system_contents(req))
        assert not any(PACK_HEADER in c for req in reqs for c in _user_contents(req)), (
            "legacy backend must never build a context pack"
        )
        assert not any(PACK_HEADER in c for req in reqs for c in _system_contents(req))
        # Legacy keeps files, not a db.
        assert (main_home / "memories" / "MEMORY.md").is_file()
        assert not (main_home / "memories" / "memory.db").exists(), (
            "legacy profile must not create a sqlite memory db"
        )

    with FakeLLMServer([Text("brandkit")]) as srv_design:
        write_hermes_home(design_home, srv_design.base_url, extra_config=_V2_EXTRA_CONFIG)
        proc = _run_profile_agent(
            design_home, srv_design.base_url, ["как рендерим фирменный стиль brandkit?"],
        )
        _assert_agent_ok(proc, "design-v2")
        reqs = srv_design.main_requests()
        pack_carriers = [c for req in reqs for c in _user_contents(req) if PACK_HEADER in c]
        assert pack_carriers, "sqlite_v2 profile must receive the context pack"
        assert any(CANARY_DESIGN_PACK in c for c in pack_carriers)
        assert (design_home / "memories" / "memory.db").is_file()


@pytest.mark.integration
def test_design_route_handoff_payload_is_sanctioned(tmp_path):
    """AC: design.route forwards only sanctioned context — no Main memory, ever."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("route_design_profile_e2e", ROUTE_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "route_type": "profile",
        "route_id": "design",
        "action_id": "design.route",
        "source_profile": "default",
        "original_user_request": "Сделай лендинг для бренда A",
        "attachments": ["/tmp/mock/brief.png"],
        "project_context": ["Бренд A — минимализм"],
        # Main-agent context that a buggy router must never forward:
        "main_memory": ["CANARY-MAIN-MEMORY-e2e секрет деплоя"],
        "reasoning": "CANARY-MAIN-REASONING-e2e",
    }
    handoff_path = tmp_path / "handoff.json"
    handoff_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    data = mod._load(handoff_path)
    prompt = mod._prompt(data)

    assert payload["original_user_request"] in prompt
    assert "brief.png" in prompt and "Бренд A — минимализм" in prompt
    assert "design.route" in prompt
    assert "CANARY-MAIN-MEMORY-e2e" not in prompt, "Main memory leaked into the design route"
    assert "CANARY-MAIN-REASONING-e2e" not in prompt, "Main reasoning leaked into the design route"

    # Dry-run end-to-end through the real CLI surface (no `hermes` exec needed).
    import subprocess as sp

    result = sp.run(
        [sys.executable, str(ROUTE_SCRIPT), "--handoff-file", str(handoff_path), "--dry-run"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60,
    )
    assert result.returncode == 0, f"router dry-run failed: {result.stderr[-1000:]}"
    report = json.loads(result.stdout)
    assert report.get("ok") is True and report.get("profile") == "design"
    assert report.get("action_id") == "design.route"
    assert report.get("prompt_chars", 0) > 0
