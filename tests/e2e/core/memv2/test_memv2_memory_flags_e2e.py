"""Strict opt-out configuration at real startup and public delegation."""
import json
import os
from pathlib import Path

import pytest
from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_hermes_home


def start(srv, extra):
    from run_agent import AIAgent
    write_hermes_home(Path(os.environ["HERMES_HOME"]), srv.base_url, extra_config=(
        "memory:\n  backend: sqlite_v2\n" + extra +
        "updates:\n  check: false\nmodels_dev:\n  url: http://127.0.0.1:9/api.json\n"))
    return AIAgent(provider="custom", base_url=srv.base_url, api_key="sk-fake-e2e",
                   model="fake-model", quiet_mode=True, enabled_toolsets=["memory", "terminal"],
                   skip_context_files=True, skip_background_review=True)


@pytest.mark.integration
@pytest.mark.parametrize("setting,key", [
    ('  orchestrator: {enabled: "false"}\n', "memory.orchestrator.enabled"),
    ('  orchestrator: {enabled: null}\n', "memory.orchestrator.enabled"),
    ('  orchestrator: []\n', "memory.orchestrator"),
    ('  recall_log: {enabled: "false"}\n', "memory.recall_log.enabled"),
    ('  recall_log: {enabled: 1}\n', "memory.recall_log.enabled"),
    ('  recall_log: []\n', "memory.recall_log"),
    ('  recall_log: null\n', "memory.recall_log"),
])
def test_startup_rejects_explicit_invalid_memory_flag(setting, key):
    with FakeLLMServer([]) as srv:
        with pytest.raises(ValueError) as error:
            agent = start(srv, setting)
            agent.close()
        message = str(error.value)
        assert key in message and "must be" in message and "set " in message
        assert not srv.main_requests()


@pytest.mark.integration
@pytest.mark.parametrize("section,key", [
    ('{memory_briefing: "false"}', "delegation.memory_briefing"),
    ('{memory_briefing: null}', "delegation.memory_briefing"),
    ('{memory_briefing: 1}', "delegation.memory_briefing"),
    ('[]', "delegation"),
    ('null', "delegation"),
])
def test_public_delegation_rejects_invalid_briefing_flag(section, key):
    from tools.delegate_tool import delegate_task
    with FakeLLMServer([Text("child done")]) as srv:
        parent = start(srv, "")
        try:
            # Live config changes must be validated on dispatch, not only startup.
            path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
            path.write_text(path.read_text() + f"delegation: {section}\n")
            try:
                result = delegate_task(goal="quartz report", parent_agent=parent, background=False)
            except ValueError as error:
                message = str(error)
            else:
                message = str(json.loads(result))
            assert key in message and "must be" in message and "set " in message
            assert not srv.main_requests(), "invalid config must not run the child provider"
        finally:
            parent.close()


@pytest.mark.integration
@pytest.mark.parametrize("section,key", [
    ('{memory_briefing: "false"}', "delegation.memory_briefing"),
    ('[]', "delegation"),
    ('null', "delegation"),
])
def test_startup_rejects_invalid_briefing_flag(section, key):
    with FakeLLMServer([]) as srv:
        with pytest.raises(ValueError) as error:
            agent = start(srv, f"delegation: {section}\n")
            agent.close()
        assert key in str(error.value) and "must be" in str(error.value) and "set " in str(error.value)
        assert not srv.main_requests()


@pytest.mark.integration
def test_real_false_memory_flags_opt_out():
    with FakeLLMServer([]) as srv:
        agent = start(srv, "  orchestrator: {enabled: false}\n  recall_log: {enabled: false}\n")
        try:
            assert agent._memory_orchestrator is None
            assert agent._memory_store._recall_log_enabled is False
        finally:
            agent.close()
