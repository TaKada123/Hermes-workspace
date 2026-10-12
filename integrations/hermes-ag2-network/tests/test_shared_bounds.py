"""Shared interaction and admission bounds across controlled network participants."""
import asyncio
from contextlib import AsyncExitStack
from pathlib import Path
import pytest
from hermes_ag2_network import ExecutionResult, Network, NetworkBudgetExceeded, NetworkLimits, network_hub


def test_branching_descendants_cannot_spend_the_same_turn_twice(tmp_path: Path):
    async def scenario():
        networks = {}
        executed = []
        async def runtime(request):
            executed.append(request.profile)
            if request.profile == "a":
                c = await networks["a"].open(peer="b", project_id="tree")
                await networks["a"].ask(c, "branch one", operation_id="branch-one", timeout=5)
                c = await networks["a"].open(peer="d", project_id="tree")
                with pytest.raises(NetworkBudgetExceeded):
                    await networks["a"].ask(c, "branch two", operation_id="branch-two", timeout=5)
            if request.profile == "b":
                c = await networks["b"].open(peer="c", project_id="tree")
                await networks["b"].ask(c, "grandchild", operation_id="grandchild", timeout=5)
            return ExecutionResult("done", request.session_current_id, "run-" + request.profile)
        names = {"caller", "a", "b", "c", "d"}
        async with network_hub(tmp_path / "hub", {n: n for n in names}) as hub:
            async with AsyncExitStack() as stack:
                for name in sorted(names):
                    networks[name] = await stack.enter_async_context(Network.connect(
                        hub.url, name=name, token=name, allowed_peers=names - {name},
                        executor=runtime if name != "caller" else None,
                        ledger_path=tmp_path / (name + ".sqlite"), limits=NetworkLimits(max_turns=3, request_timeout=5)))
                channel = await networks["caller"].open(peer="a", project_id="tree")
                assert (await networks["caller"].ask(channel, "root", operation_id="root", timeout=5)).text == "done"
                assert executed == ["a", "b", "c"]
    asyncio.run(scenario())


def test_global_capacity_rejects_a_different_profile_before_executor_admission(tmp_path: Path):
    async def scenario():
        from hermes_ag2_network import ExecutionUncertain
        requests = []
        async def runtime(request):
            requests.append(request.profile)
            if request.profile == "a":
                raise ExecutionUncertain("external work still live")
            return ExecutionResult("unexpected admission", request.session_current_id, "run-b")
        names = {"caller", "a", "b"}
        limits = NetworkLimits(max_active=1)
        async with network_hub(tmp_path / "hub", {name: name for name in names}) as hub:
            async with AsyncExitStack() as stack:
                networks = {}
                for name in sorted(names):
                    networks[name] = await stack.enter_async_context(Network.connect(
                        hub.url, name=name, token=name, allowed_peers=names - {name},
                        executor=runtime if name != "caller" else None,
                        ledger_path=tmp_path / (name + ".sqlite"), limits=limits))
                a = await networks["caller"].open(peer="a", project_id="one")
                b = await networks["caller"].open(peer="b", project_id="two")
                with pytest.raises(ExecutionUncertain):
                    await networks["caller"].ask(a, "first", operation_id="first", timeout=5)
                with pytest.raises(NetworkBudgetExceeded):
                    await networks["caller"].ask(b, "second", operation_id="second", timeout=5)
                assert requests == ["a"]
    asyncio.run(scenario())


def test_global_capacity_is_shared_by_separate_bridge_processes_and_survives_disconnect(tmp_path: Path):
    import json
    import os
    from test_cli import command
    from test_http_executor import hermes_api
    from hermes_ag2_network import ExecutionUncertain
    from hermes_ag2_network.discovery import enroll_profile

    tokens = {"caller": "a", "architect": "b", "designer": "c"}
    keys = tmp_path / "keys.json"
    keys.write_text(json.dumps(tokens), encoding="utf-8")
    keys.chmod(0o600)
    for name, secret in (("architect", "b"), ("designer", "c"), ("api", "fixture-secret")):
        path = tmp_path / (name + ".key")
        path.write_text(secret, encoding="utf-8")
        path.chmod(0o600)
    control = tmp_path / "shared-control.sqlite"
    hermes_home = tmp_path / "hermes-home"
    for profile in ("architect", "designer"):
        (hermes_home / "profiles" / profile).mkdir(parents=True, exist_ok=True)
        enroll_profile(profile, hermes_home)
    bridge_env = {**os.environ, "HERMES_HOME": str(hermes_home)}

    def bridge(hub_url, name, api_url):
        return command("bridge", "--hub-url", hub_url, "--name", name,
                       "--allow-peer", "caller", "--max-active", "1", "--timeout", "2",
                       "--control-db", str(control), "--ledger", str(tmp_path / (name + ".sqlite")),
                       "--api-url", api_url, "--api-key-file", str(tmp_path / "api.key"),
                       "--hub-key-file", str(tmp_path / (name + ".key")), env=bridge_env)

    with hermes_api() as (architect_url, architect_posts), hermes_api(profile="designer") as (designer_url, designer_posts):
        async def scenario():
            with command("hub", "--store", str(tmp_path / "hub"), "--keys-file", str(keys), "--port", "0") as hub:
                with bridge(hub["url"], "designer", designer_url):
                    async with Network.connect(hub["url"], name="caller", token="a", allowed_peers={"architect", "designer"},
                                               ledger_path=tmp_path / "caller.sqlite", control_path=control,
                                               limits=NetworkLimits(max_active=1)) as caller:
                        with bridge(hub["url"], "architect", architect_url):
                            a = await caller.open(peer="architect", project_id="one")
                            b = await caller.open(peer="designer", project_id="two")
                            with pytest.raises(ExecutionUncertain):
                                await caller.ask(a, "stay queued", operation_id="global-held", timeout=5)
                            with pytest.raises(NetworkBudgetExceeded):
                                await caller.ask(b, "new run", operation_id="global-blocked", timeout=5)
                        # Disconnecting the old bridge is not evidence that its HTTP Run stopped.
                        with pytest.raises(NetworkBudgetExceeded):
                            await caller.ask(b, "new run", operation_id="global-blocked", timeout=5)
                        with bridge(hub["url"], "architect", architect_url):
                            with pytest.raises(NetworkBudgetExceeded):
                                await caller.ask(b, "new run", operation_id="global-blocked", timeout=5)
                            with pytest.raises(ExecutionUncertain):
                                await caller.ask(a, "stay queued", operation_id="global-held", timeout=5)
                        assert len([post for post in architect_posts if post[0].endswith("/v1/runs")]) == 1
                        assert designer_posts == []
                        with pytest.raises(NetworkBudgetExceeded):
                            await caller.send(b, "async blocked", operation_id="global-async-blocked")
                        assert [m for m in await caller.history(b) if m.kind == "request"] == []
        asyncio.run(scenario())
