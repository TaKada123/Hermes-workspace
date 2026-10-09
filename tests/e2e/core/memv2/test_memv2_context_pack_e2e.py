"""E2E: the per-turn context pack rides the fake provider's payload (ticket #6).

Everything real except the model: an in-process ``AIAgent`` + ``MemoryStoreV2`` + a
recording ``FakeLLMServer`` (real loopback HTTP). The typed store is seeded BEFORE agent
init so the frozen snapshot is crowded and the target entry is evicted from the prompt
but searchable in SQLite — the exact condition the pack exists for.

Acceptance criteria covered (AC → test):

- relevant follow-up gets the rendered pack in the provider payload          → ``test_relevant_query_gets_pack``
- irrelevant query does NOT                                                  → same test, third turn
- persisted transcript/history never contains the pack                       → ``test_relevant_query_gets_pack`` + ``test_legacy_backend_no_pack``
- pack only on the API copy (system prompt untouched)                        → ``test_relevant_query_gets_pack`` (system content asserted clean)
- legacy backend: no pack, nothing changes                                   → ``test_legacy_backend_no_pack``
- memory tool works alongside the orchestrator (integration)                 → turn 1 of ``test_relevant_query_gets_pack``

Runs only under ``--include-integration`` (e2e/ is skipped by default discovery).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall, write_hermes_home

PACK_HEADER = "## Retrieved memory"

# Shrink the snapshot budget so a handful of seeded rows crowds it; disable the
# periodic background review + skill nudge (their forked agents would race the
# scripted turns); no network probes.
_V2_EXTRA_CONFIG = (
    "memory:\n"
    "  backend: sqlite_v2\n"
    "  memory_char_limit: 200\n"
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
    "  memory_char_limit: 200\n"
    "  user_char_limit: 1375\n"
    "  nudge_interval: 0\n"
    "skills:\n"
    "  creation_nudge_interval: 0\n"
    "updates:\n"
    "  check: false\n"
    "models_dev:\n"
    "  url: http://127.0.0.1:9/api.json\n"
)


def _hermes_home() -> Path:
    # tests/conftest.py isolates HERMES_HOME per test into a temp dir.
    return Path(os.environ["HERMES_HOME"])


def _seed_crowded_v2() -> None:
    """Fill the on-disk store BEFORE agent init (same limits as config).

    Lane-2 filler (high-importance decisions) crowds the standing lane so the
    Docker decision is evicted from the frozen snapshot but stays searchable.
    """
    from agent.memory_store_v2 import MemoryStoreV2

    s = MemoryStoreV2(memory_char_limit=200, user_char_limit=1375)
    s.load_from_disk()
    for i in range(6):
        s.add(
            "memory",
            f"Стоящее решение-наполнитель номер {i} занимает дорожку",
            entry_type="decision", importance=0.95,
        )
    s.add(
        "memory",
        "Не используем Docker — тяжело для одного сервера",
        entry_type="decision", importance=0.4,
    )
    s.close()


def _build_agent(base_url: str) -> Any:
    from run_agent import AIAgent

    return AIAgent(
        provider="custom", base_url=base_url, api_key="sk-fake-e2e", model="fake-model",
        quiet_mode=True, enabled_toolsets=["memory"], skip_context_files=True,
        skip_background_review=True,
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


@pytest.mark.integration
def test_relevant_query_gets_pack_irrelevant_does_not(tmp_path):
    with FakeLLMServer([
        ToolCall("memory", {
            "action": "add", "target": "memory",
            "content": "Сборку запускаем через make build",
            "entry_type": "fact",
        }),
        Text("Записал."),
        Text("Принято, Docker не используем."),
        Text("Не знаю, какая погода."),
    ]) as srv:
        home = _hermes_home()
        write_hermes_home(home, srv.base_url, extra_config=_V2_EXTRA_CONFIG)
        _seed_crowded_v2()

        agent = _build_agent(srv.base_url)
        try:
            # The orchestrator is wired at init on the sqlite_v2 backend.
            assert agent._memory_orchestrator is not None

            # Turn 1: a real memory-tool write runs alongside the orchestrator
            # (its pack for this message is irrelevant → may be empty).
            before = len(srv.main_requests())
            r1 = agent.run_conversation(
                "запомни: сборку запускаем через make build", conversation_history=[], task_id="t1",
            )
            srv.wait_for_requests(before + 2)
            assert r1.get("final_response"), f"turn 1 failed: {r1.get('error')}"

            # Turn 2: RELEVANT follow-up — the evicted Docker decision must ride
            # the API copy of this turn's user message.
            before = len(srv.main_requests())
            r2 = agent.run_conversation(
                "давай развернём Docker в проде?", conversation_history=r1["messages"], task_id="t2",
            )
            srv.wait_for_requests(before + 1)
            reqs2 = srv.main_requests()[before:]
            injected = [c for req in reqs2 for c in _user_contents(req) if PACK_HEADER in c]
            assert injected, "relevant query must receive the context pack in the payload"
            assert "Docker" in injected[0]
            assert "Не используем Docker" in injected[0]
            # Unfenced: <memory-context> is reserved for external prefetch.
            assert "<memory-context>" not in injected[0]

            # System prompt (frozen snapshot) untouched by the pack.
            for req in reqs2:
                assert not any(PACK_HEADER in c for c in _system_contents(req))

            # Persisted transcript/history never contains the pack.
            for msg in r2["messages"]:
                content = msg.get("content")
                if isinstance(content, str):
                    assert PACK_HEADER not in content, "persisted history must stay pack-free"
                else:
                    assert not any(
                        PACK_HEADER in str(part.get("text", ""))
                        for part in (content or []) if isinstance(part, dict)
                    ), "persisted multimodal parts must stay pack-free"

            # Turn 3: IRRELEVANT query — no pack.
            before = len(srv.main_requests())
            r3 = agent.run_conversation(
                "какая завтра погода в городе?", conversation_history=r2["messages"], task_id="t3",
            )
            srv.wait_for_requests(before + 1)
            reqs3 = srv.main_requests()[before:]
            assert not any(
                PACK_HEADER in c for req in reqs3 for c in _user_contents(req)
            ), "irrelevant query must not receive a pack"
            assert r3.get("final_response")
        finally:
            close = getattr(agent, "close", None)
            if callable(close):
                close()


@pytest.mark.integration
def test_legacy_backend_never_builds_pack(tmp_path):
    with FakeLLMServer([Text("Ок.")]) as srv:
        home = _hermes_home()
        write_hermes_home(home, srv.base_url, extra_config=_LEGACY_EXTRA_CONFIG)

        agent = _build_agent(srv.base_url)
        try:
            assert agent._memory_orchestrator is None, "legacy backend must not wire the orchestrator"
            assert agent._memory_pack_cache == ""

            before = len(srv.main_requests())
            r = agent.run_conversation(
                "давай развернём Docker в проде?", conversation_history=[], task_id="t",
            )
            srv.wait_for_requests(before + 1)
            reqs = srv.main_requests()[before:]
            assert not any(PACK_HEADER in c for req in reqs for c in _user_contents(req))
            assert not any(PACK_HEADER in c for req in reqs for c in _system_contents(req))
            for msg in r["messages"]:
                if isinstance(msg.get("content"), str):
                    assert PACK_HEADER not in msg["content"]
        finally:
            close = getattr(agent, "close", None)
            if callable(close):
                close()
