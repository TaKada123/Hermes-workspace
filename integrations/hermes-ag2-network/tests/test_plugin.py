"""The standalone plugin registers safe names and calls only its profile-bound loopback bridge."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types

from hermes_ag2_network import ExecutionResult, Network, network_hub
from hermes_ag2_network.tool_api import ToolAPI


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "plugin"


def _load_plugin():
    name = "agent_network_plugin_test"
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PluginContext:
    def __init__(self, profile_name: str, bridge_url: str):
        self.profile_name = profile_name
        self.settings = {"bridge_url": bridge_url, "timeout_seconds": 8}
        self.tools = {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


def test_plugin_registers_five_profile_bound_tools_and_uses_real_bridge(tmp_path, monkeypatch):
    async def scenario():
        completed = []

        async def architect(request):
            completed.append(request)
            return ExecutionResult(
                text=f"Architect reply to: {request.text}",
                session_id="architect-session", run_id=f"run-{request.operation_id}",
            )

        keys = {"caller": "caller-hub-key", "architect": "architect-hub-key"}
        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(
                hub.url, name="architect", token=keys["architect"], allowed_peers={"caller"},
                executor=architect, ledger_path=tmp_path / "architect.sqlite",
            ):
                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers=set(),
                    project_peers={"plugin-test": {"architect"}},
                    ledger_path=tmp_path / "caller.sqlite",
                ) as caller:
                    async with ToolAPI(caller, "profile-tool-secret", port=0) as tool_api:
                        secret_scope = types.ModuleType("agent.secret_scope")
                        secret_scope.__dict__["get_secret"] = lambda name, default=None: (
                            "profile-tool-secret" if name == "AGENT_NETWORK_TOOLS_KEY" else default
                        )
                        agent_package = types.ModuleType("agent")
                        agent_package.__path__ = []
                        monkeypatch.setitem(sys.modules, "agent", agent_package)
                        monkeypatch.setitem(sys.modules, "agent.secret_scope", secret_scope)
                        plugin = _load_plugin()
                        context = PluginContext("caller", tool_api.url)
                        plugin.register(context)
                        assert set(context.tools) == {
                            "agent_network_peers", "agent_network_open", "agent_network_send",
                            "agent_network_ask", "agent_network_history",
                        }
                        assert all(tool["check_fn"]() for tool in context.tools.values())

                        async def call(name, args=None):
                            raw = await asyncio.to_thread(context.tools[name]["handler"], args or {})
                            return json.loads(raw)

                        peers = await call("agent_network_peers")
                        assert peers["ok"] is True
                        assert [peer["name"] for peer in peers["result"]] == ["architect"]
                        project_peers = await call("agent_network_peers", {"project_id": "plugin-test"})
                        assert [peer["name"] for peer in project_peers["result"]] == ["architect"]
                        assert await call("agent_network_peers", {"project_id": "other-project"}) == {
                            "ok": True, "result": [],
                        }

                        opened = await call("agent_network_open", {"peer": "architect", "project_id": "plugin-test"})
                        channel_id = opened["result"]["channel_id"]
                        asked = await call("agent_network_ask", {
                            "channel_id": channel_id,
                            "text": "Please review the interface.",
                            "operation_id": "plugin-ask-01",
                            "timeout_seconds": 5,
                        })
                        assert asked["ok"] is True
                        assert asked["result"]["kind"] == "reply"
                        assert asked["result"]["text"] == "Architect reply to: Please review the interface."

                        repeated = await call("agent_network_ask", {
                            "channel_id": channel_id,
                            "text": "Please check one follow-up detail.",
                            "operation_id": "plugin-ask-02",
                            "timeout_seconds": 5,
                        })
                        assert repeated["ok"] is True
                        assert completed[0].session_origin_id
                        assert completed[1].session_origin_id == completed[0].session_origin_id
                        assert completed[1].session_current_id == "architect-session"

                        sent = await call("agent_network_send", {
                            "channel_id": channel_id,
                            "text": "One final asynchronous note.",
                            "operation_id": "plugin-send-03",
                        })
                        assert sent["ok"] is True
                        await asyncio.sleep(0.05)
                        history = await call("agent_network_history", {"channel_id": channel_id})
                        assert [item["kind"] for item in history["result"]] == [
                            "request", "reply", "request", "reply", "request", "reply",
                        ]
                        assert len(completed) == 3

                        # The plugin's profile binding is derived from PluginContext, not a model argument.
                        misbound = PluginContext("architect", tool_api.url)
                        plugin.register(misbound)
                        result = json.loads(await asyncio.to_thread(
                            misbound.tools["agent_network_peers"]["handler"], {},
                        ))
                        assert result == {"ok": False, "error": "peer or channel access denied"}

                        invalid_endpoint = PluginContext("caller", "https://example.org")
                        plugin.register(invalid_endpoint)
                        assert not invalid_endpoint.tools["agent_network_peers"]["check_fn"]()

                        captured = {}
                        def capture_request(_ctx, _method, _path, **options):
                            captured.update(options)
                            return {"ok": True, "profile": "caller", "result": []}

                        monkeypatch.setattr(plugin, "request", capture_request)
                        task_scoped = json.loads(await asyncio.to_thread(
                            context.tools["agent_network_peers"]["handler"], {}, task_id="run-session-id",
                            run_context_id="a" * 64,
                        ))
                        assert task_scoped["ok"] is True
                        assert "task_id" not in captured
                        assert captured["run_context_id"] == "a" * 64

    asyncio.run(scenario())
