"""Configuration and enabled targets at the public AIAgent startup seam."""
import os
from pathlib import Path

import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, write_hermes_home


@pytest.mark.integration
@pytest.mark.parametrize("setting,key", [
    ("bus: invalid", "memory.bus"), ("bus: []", "memory.bus"),
    ("bus: 0", "memory.bus"), ("bus: false", "memory.bus"),
    ("bus: {enabled: invalid}", "memory.bus.enabled"),
    ("bus: {enabled: []}", "memory.bus.enabled"),
    ("bus: {enabled: null}", "memory.bus.enabled"),
])
def test_public_agent_rejects_invalid_bus_config(setting, key):
    from run_agent import AIAgent
    with FakeLLMServer([]) as srv:
        write_hermes_home(Path(os.environ["HERMES_HOME"]), srv.base_url, extra_config=(
            f"memory:\n  backend: sqlite_v2\n  {setting}\n"
            "updates:\n  check: false\nmodels_dev:\n  url: http://127.0.0.1:9/api.json\n"))
        with pytest.raises(ValueError) as error:
            agent = AIAgent(provider="custom", base_url=srv.base_url, api_key="sk-fake-e2e",
                            model="fake-model", quiet_mode=True, enabled_toolsets=["memory"],
                            skip_context_files=True, skip_background_review=True)
            agent.close()
        assert key in str(error.value)
        assert "must be" in str(error.value) and "set " in str(error.value).lower()
        assert not srv.main_requests()


@pytest.mark.integration
@pytest.mark.parametrize("aliases", ["[]", "false", "42", "{network: [vpn, false]}"])
def test_public_agent_rejects_malformed_aliases_with_specific_config_error(aliases):
    from agent.memory_store_v2 import MemoryAliasConfigError
    from run_agent import AIAgent

    with FakeLLMServer([]) as srv:
        write_hermes_home(Path(os.environ["HERMES_HOME"]), srv.base_url, extra_config=(
            f"memory:\n  backend: sqlite_v2\n  aliases: {aliases}\n"
            "updates:\n  check: false\nmodels_dev:\n  url: http://127.0.0.1:9/api.json\n"))
        with pytest.raises(MemoryAliasConfigError, match="memory.aliases") as raised:
            agent = AIAgent(provider="custom", base_url=srv.base_url, api_key="sk-fake-e2e",
                            model="fake-model", quiet_mode=True, enabled_toolsets=["memory"],
                            skip_context_files=True, skip_background_review=True)
            agent.close()
        assert type(raised.value) is MemoryAliasConfigError
        assert raised.value.key.startswith("memory.aliases")
        assert raised.value.cause
        assert raised.value.remediation
        assert not srv.main_requests()


@pytest.mark.integration
@pytest.mark.parametrize("disabled,enabled", [("memory_enabled", "user"), ("user_profile_enabled", "memory")])
def test_public_agent_bus_keeps_only_enabled_target(disabled, enabled):
    from run_agent import AIAgent
    with FakeLLMServer([]) as srv:
        write_hermes_home(Path(os.environ["HERMES_HOME"]), srv.base_url, extra_config=(
            f"memory:\n  backend: sqlite_v2\n  {disabled}: false\n"
            "updates:\n  check: false\nmodels_dev:\n  url: http://127.0.0.1:9/api.json\n"))
        agent = AIAgent(provider="custom", base_url=srv.base_url, api_key="sk-fake-e2e",
                        model="fake-model", quiet_mode=True, enabled_toolsets=["memory"],
                        skip_context_files=True, skip_background_review=True)
        try:
            assert agent._memory_bus is not None
            assert agent._memory_bus.targets == (enabled,)
            assert agent._memory_bus.capabilities() == frozenset({f"read:{enabled}", f"write:{enabled}", f"rollback:{enabled}"})
        finally:
            agent.close()
