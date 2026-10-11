"""E2E for ticket #8 — the subagent receives a read-only memory briefing.

Real in-process ``AIAgent`` against ``FakeLLMServer`` (the fake provider
records every request payload): the parent (memory.backend: sqlite_v2) writes
a memory entry via the scripted memory tool, then calls ``delegate_task``.
The child runs against the same server, so its provider request payload is
the observable contract:

- the child's request carries the parent-recalled briefing in its first user
  message (goal + briefing), and the briefing never leaks back into any
  parent request (one-time copy, never persisted into the parent's context);
- the child's request carries NO memory tool definition — the child can
  neither write memory nor roll it back (structural isolation);
- with ``delegation.memory_briefing: false`` the child's goal stays clean —
  the gate really disables the feature.

Run with ``--include-integration`` (the e2e tree is skipped by default
discovery).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall, write_hermes_home

ENTRY = "Правило E2E-BRIEF-MARKER: сервер гипервизор всегда под TLS"
GOAL = "напиши отчёт про сервер гипервизор (E2E-BRIEF-GOAL)"

_EXTRA = (
    "memory:\n"
    "  backend: sqlite_v2\n"
    "  nudge_interval: 0\n"
    "skills:\n"
    "  creation_nudge_interval: 0\n"
    "updates:\n"
    "  check: false\n"
)


def _child_requests(srv: FakeLLMServer) -> list[dict]:
    """Main requests whose last message is the child's user goal turn."""
    out = []
    for body in srv.main_requests():
        messages = body.get("messages") or []
        if not messages:
            continue
        last = messages[-1]
        if last.get("role") == "user" and GOAL in str(last.get("content") or ""):
            out.append(body)
    return out


def _tool_names(body: dict) -> set:
    return {t.get("function", {}).get("name") for t in body.get("tools") or []}


def _run_delegation(extra_config: str) -> tuple[FakeLLMServer, dict]:
    from run_agent import AIAgent

    script = [
        ToolCall("memory", {"action": "add", "target": "memory", "content": ENTRY}),
        ToolCall("delegate_task", {"goal": GOAL, "max_iterations": 5}),
        Text("the parent continues meanwhile"),
        Text("the child's own answer"),
    ]
    with FakeLLMServer(script, default_text="ok") as srv:
        home = Path(os.environ["HERMES_HOME"])  # per-test isolated by tests/conftest
        write_hermes_home(home, srv.base_url, extra_config=extra_config)
        agent = AIAgent(
            provider="custom", base_url=srv.base_url, api_key="sk-fake-e2e", model="fake-model",
            quiet_mode=True, skip_context_files=True,
            enabled_toolsets=["terminal", "memory", "delegation"],
        )
        try:
            result = agent.run_conversation("сначала запиши факт про сервер, потом делегируй отчёт")
        finally:
            agent.close()
        # The delegation batch runs on a background thread: the child's first
        # provider request lands right after the parent's turn ends. Poll for
        # it while the server is still up (the scripted stream answers it).
        deadline = time.monotonic() + 60.0
        child_reqs: list[dict] = []
        while time.monotonic() < deadline:
            child_reqs = _child_requests(srv)
            if child_reqs:
                break
            time.sleep(0.1)
        assert child_reqs, "the child never reached the provider (no child request recorded)"
        # Give the child's in-flight turn a moment to finish against the live
        # server before the context manager stops it.
        time.sleep(1.0)
        return srv, result


@pytest.mark.integration
def test_subagent_payload_has_briefing_and_no_memory_tool(tmp_path):
    """AC: the child's payload contains the briefing; the child carries no
    memory tool, so it cannot write or roll back memory."""
    srv, _ = _run_delegation(_EXTRA)

    child_reqs = _child_requests(srv)
    assert len(child_reqs) == 1, (
        f"expected exactly one child request; got {len(child_reqs)}"
    )
    child = child_reqs[0]

    # The briefing rides the child's first user message, appended to the goal.
    user_content = child["messages"][-1]["content"]
    assert GOAL in user_content
    assert "Memory briefing" in user_content, "child goal must carry the recalled briefing"
    assert "E2E-BRIEF-MARKER" in user_content, "the stored entry reached the child"
    assert "<memory-context" not in user_content, "briefing must not be fenced"

    # Structural isolation: no memory tool in the child's payload.
    assert "memory" not in _tool_names(child), "child payload must carry no memory tool"

    # One-time copy: no OTHER request (parent included) ever carries the briefing.
    for body in srv.main_requests():
        if body is child:
            continue
        for msg in body.get("messages") or []:
            assert "Memory briefing" not in str(msg.get("content") or ""), (
                "the briefing leaked into another request — it must be a one-time copy"
            )

    # The parent itself HAS the memory tool (and its request stream proves the
    # write path used it — the entry was added before delegation).
    parent_tools = _tool_names(srv.main_requests()[0])
    assert "memory" in parent_tools, "the parent must keep its memory tool"


@pytest.mark.integration
def test_gate_off_removes_briefing_from_child_payload(tmp_path):
    """AC: delegation.memory_briefing=false really disables the feature."""
    srv, _ = _run_delegation(_EXTRA + "delegation:\n  memory_briefing: false\n")

    child_reqs = _child_requests(srv)
    assert len(child_reqs) == 1
    child = child_reqs[0]
    user_content = child["messages"][-1]["content"]
    assert GOAL in user_content
    assert "Memory briefing" not in user_content, "gate off: the child goal must stay clean"
    assert "E2E-BRIEF-MARKER" not in user_content
