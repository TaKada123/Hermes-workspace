"""Real config.yaml -> AIAgent: unusable supplied retrieval config fails startup."""

import os
from pathlib import Path

import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, write_hermes_home


@pytest.mark.integration
@pytest.mark.parametrize("setting,key", [
    ("token_budget: many", "token_budget"),
    ("max_entries: 0", "max_entries"),
    ("weights: []", "weights"),
    ("weights: {relevance: .nan}", "weights.relevance"),
])
@pytest.mark.parametrize("enabled", ["true", "false"])
def test_agent_startup_rejects_invalid_orchestrator_or_bus_config(setting, key, enabled):
    from run_agent import AIAgent

    with FakeLLMServer([]) as srv:
        write_hermes_home(Path(os.environ["HERMES_HOME"]), srv.base_url, extra_config=(
            "memory:\n  backend: sqlite_v2\n  orchestrator:\n"
            f"    enabled: {enabled}\n    {setting}\n"
            "updates:\n  check: false\nmodels_dev:\n  url: http://127.0.0.1:9/api.json\n"
        ))
        with pytest.raises(ValueError) as error:
            agent = AIAgent(provider="custom", base_url=srv.base_url, api_key="sk-fake-e2e",
                            model="fake-model", quiet_mode=True, enabled_toolsets=["memory"],
                            skip_context_files=True, skip_background_review=True)
            agent.close()
        message = str(error.value)
        assert f"memory.orchestrator.{key}" in message
        assert "must be" in message and "set " in message.lower()
        assert not srv.main_requests()


@pytest.mark.integration
def test_metadata_rich_pack_in_real_provider_payload_obeys_configured_budget():
    from agent.memory_store_v2 import MemoryStoreV2
    from agent.model_metadata import estimate_tokens_rough
    from run_agent import AIAgent
    from tests.fakes.fake_llm_provider import Text

    with FakeLLMServer([Text("Noted.")]) as srv:
        write_hermes_home(Path(os.environ["HERMES_HOME"]), srv.base_url, extra_config=(
            "memory:\n  backend: sqlite_v2\n  memory_char_limit: 1\n  user_char_limit: 1\n"
            "  nudge_interval: 0\n  orchestrator:\n    token_budget: 220\n"
            "updates:\n  check: false\nmodels_dev:\n  url: http://127.0.0.1:9/api.json\n"
        ))
        store = MemoryStoreV2(memory_char_limit=1, user_char_limit=1)
        store.load_from_disk()
        try:
            for i, kind in enumerate(("decision", "constraint", "pattern", "preference", "fact", "legacy")):
                target = "user" if i % 2 else "memory"
                old = store.add(target, f"Old quartz {i}: " + "история " * 15, entry_type=kind)
                assert old["success"]
                assert store.supersede(target, old_id=old["id"], content=f"quartz record-{i}",
                                       entry_type=kind, reason="updated")["success"]
        finally:
            store.close()
        agent = AIAgent(provider="custom", base_url=srv.base_url, api_key="sk-fake-e2e",
                        model="fake-model", quiet_mode=True, enabled_toolsets=["memory"],
                        skip_context_files=True, skip_background_review=True)
        try:
            result = agent.run_conversation("quartz", conversation_history=[], task_id="budget-e2e")
            assert result.get("final_response")
            srv.wait_for_requests(1)
            users = [m["content"] for r in srv.main_requests() for m in r["messages"]
                     if m["role"] == "user" and isinstance(m.get("content"), str)]
            injected = next(c for c in users if "## Retrieved memory" in c)
            pack = injected[injected.index("## Retrieved memory"):]
            assert estimate_tokens_rough(pack) <= 220
            assert "[supersedes:" in pack and "quartz record-" in pack
            assert all("## Retrieved memory" not in str(m.get("content", "")) for m in result["messages"])
        finally:
            agent.close()
