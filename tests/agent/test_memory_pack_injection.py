"""Unit tests for the context-pack injection (ticket #6, acceptance criteria 3-5).

The pack must ride the API copy of the CURRENT turn's user message ONLY:

- system prompt unchanged, persisted history unchanged (prompt-cache invariant);
- idempotent (never appended twice);
- legacy backend (no orchestrator / empty ``_memory_pack_cache``) → nothing
  changes, the wire bytes stay exactly as before;
- the pack is plain markdown — never fenced with ``<memory-context>`` (that
  tag is reserved for external-provider prefetch).

Tests drive the real ``agent.turn_context.build_api_messages`` composition
function against a minimal agent stub, so they exercise the actual wire-copy
code path without a full provider loop.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from agent.turn_context import build_api_messages


class _StubAgent:
    """Minimal agent surface ``build_api_messages`` reads; everything else is ``None``."""

    def __init__(self, **attrs: Any) -> None:
        self.__dict__.update(
            _current_turn_timestamp=time.time(),
            ephemeral_system_prompt="",
            _memory_pack_cache="",
        )
        self.__dict__.update(attrs)

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401 - stub double
        return None

    def _copy_reasoning_content_for_api(self, msg, api_msg) -> None:
        pass

    def _should_sanitize_tool_calls(self) -> bool:
        return False


PACK = "## Retrieved memory — this turn (12 tokens)\n\n### Decisions\n- [active · a1b2c3d4 · 2026-08-14] Не используем Docker"


def _history(*, sidecar_on_current: str | None = None) -> tuple[list, int]:
    """Three-message history: historical user, assistant, current user."""
    messages = [
        {"role": "user", "content": "какие у нас правила по деплою?"},
        {"role": "assistant", "content": "Разворачиваем через docker compose."},
        {"role": "user", "content": "давай развернём Docker в проде?"},
    ]
    if sidecar_on_current is not None:
        messages[2]["api_content"] = sidecar_on_current
    return messages, 2


def _user_contents(api_messages: list) -> list:
    return [m["content"] for m in api_messages if m.get("role") == "user"]


def test_pack_appended_to_current_turn_api_copy_only():
    """AC: pack rides the API copy of the CURRENT user message; history rows
    and the persisted ``messages`` list stay untouched."""
    messages, idx = _history()
    agent = _StubAgent(_memory_pack_cache=PACK)
    api_messages, _sys = build_api_messages(
        agent, messages, current_turn_user_idx=idx,
        ext_prefetch_cache="", plugin_user_context="", moa_config=None,
        active_system_prompt="SYSTEM",
    )
    users = _user_contents(api_messages)
    assert len(users) == 2
    assert users[0] == "какие у нас правила по деплою?", "historical row must stay clean"
    assert users[1] == "давай развернём Docker в проде?\n\n" + PACK
    # The persisted history list is untouched (no api_content stamp, no pack).
    assert messages[2]["content"] == "давай развернём Docker в проде?"
    assert "api_content" not in messages[2]
    assert all("Retrieved memory" not in str(m.get("content")) for m in messages)


def test_system_prompt_unchanged():
    """AC: the pack never leaks into the system prompt (frozen snapshot)."""
    messages, idx = _history()
    agent = _StubAgent(_memory_pack_cache=PACK)
    api_messages, effective_system = build_api_messages(
        agent, messages, current_turn_user_idx=idx,
        ext_prefetch_cache="", plugin_user_context="", moa_config=None,
        active_system_prompt="SYSTEM: frozen snapshot with Docker notes",
    )
    assert effective_system == "SYSTEM: frozen snapshot with Docker notes"
    assert api_messages[0]["role"] == "system"
    assert "Retrieved memory" not in effective_system
    assert "Retrieved memory" not in api_messages[0]["content"]


def test_legacy_backend_no_pack_no_change():
    """AC: on the legacy backend the pack is empty and NOTHING changes —
    the wire content is the plain user message."""
    messages, idx = _history()
    agent = _StubAgent(_memory_pack_cache="")  # orchestrator absent → ""
    api_messages, _sys = build_api_messages(
        agent, messages, current_turn_user_idx=idx,
        ext_prefetch_cache="", plugin_user_context="", moa_config=None,
        active_system_prompt="SYSTEM",
    )
    users = _user_contents(api_messages)
    assert users[1] == "давай развернём Docker в проде?"


def test_no_double_append_when_content_already_has_pack():
    """AC: idempotent — a content that already carries the pack is left alone."""
    messages, idx = _history(sidecar_on_current="давай развернём Docker в проде?\n\n" + PACK)
    agent = _StubAgent(_memory_pack_cache=PACK)
    api_messages, _sys = build_api_messages(
        agent, messages, current_turn_user_idx=idx,
        ext_prefetch_cache="", plugin_user_context="", moa_config=None,
        active_system_prompt="SYSTEM",
    )
    users = _user_contents(api_messages)
    assert users[1] == "давай развернём Docker в проде?\n\n" + PACK
    assert users[1].count(PACK) == 1


def test_historical_sidecar_replay_excludes_pack():
    """The next turn replays this row from its ``api_content`` sidecar (no
    pack) — the pack is ephemeral to the turn it was built for."""
    messages, _idx = _history(sidecar_on_current="давай развернём Docker в проде?")
    # On the NEXT turn the pack-bearing row is historical; the current turn
    # is a new message with its own (empty) pack.
    next_messages = messages + [{"role": "user", "content": "а что с бэкапами?"}]
    agent = _StubAgent(_memory_pack_cache="")
    api_messages, _sys = build_api_messages(
        agent, next_messages, current_turn_user_idx=3,
        ext_prefetch_cache="", plugin_user_context="", moa_config=None,
        active_system_prompt="SYSTEM",
    )
    users = _user_contents(api_messages)
    assert all("Retrieved memory" not in u for u in users)
    assert users[1] == "давай развернём Docker в проде?"  # sidecar replay, no pack


def test_pack_appends_after_prefetch_injection():
    """Pack is appended AFTER the prefetch/plugin context (separate channel,
    own unfenced slot), and the pack text itself carries no memory-context fence."""
    messages, idx = _history()
    agent = _StubAgent(_memory_pack_cache=PACK)
    api_messages, _sys = build_api_messages(
        agent, messages, current_turn_user_idx=idx,
        ext_prefetch_cache="<memory-context>external prefetch</memory-context>",
        plugin_user_context="", moa_config=None,
        active_system_prompt="SYSTEM",
    )
    content = _user_contents(api_messages)[1]
    assert content.startswith("давай развернём Docker в проде?")
    assert "<memory-context>" in content  # the external prefetch keeps its fence
    assert content.endswith(PACK)
    # The pack itself must not be fenced.
    assert "<memory-context>" not in PACK


def test_multimodal_list_content_not_pack_appended():
    """A list (multimodal) user message takes the text-part path; the string
    append path must not corrupt list content."""
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "как на картинке?"}]},
    ]
    agent = _StubAgent(_memory_pack_cache=PACK)
    api_messages, _sys = build_api_messages(
        agent, messages, current_turn_user_idx=0,
        ext_prefetch_cache="", plugin_user_context="", moa_config=None,
        active_system_prompt="SYSTEM",
    )
    assert isinstance(api_messages[1]["content"], list)
    assert all("Retrieved memory" not in str(p.get("text")) for p in api_messages[1]["content"])
