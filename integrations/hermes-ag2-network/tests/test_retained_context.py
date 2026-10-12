"""Held work blocks unrelated requests until an explicit terminal reconciliation."""
import asyncio
from pathlib import Path
import pytest
from hermes_ag2_network import ExecutionResult, ExecutionUncertain, Network, NetworkBudgetExceeded, network_hub


def test_uncertain_run_retains_context_until_terminal_reconciliation(tmp_path: Path):
    async def scenario():
        requests = []
        terminal = False
        class Runtime:
            async def __call__(self, request):
                requests.append(request)
                if request.operation_id == "held":
                    raise ExecutionUncertain("run still executing")
                return ExecutionResult("fresh finished", request.session_current_id, "fresh-run")
            async def reconcile(self, request):
                if not terminal:
                    raise ExecutionUncertain("run still executing")
                return ExecutionResult("held finished", request.session_current_id, "held-run")
        keys = {"caller": "a", "worker": "b"}
        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(hub.url, name="worker", token="b", allowed_peers={"caller"},
                                       executor=Runtime(), ledger_path=tmp_path / "worker.sqlite") as worker:
                async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"worker"},
                                           ledger_path=tmp_path / "caller.sqlite") as caller:
                    channel = await caller.open(peer="worker", project_id="held-project")
                    with pytest.raises(ExecutionUncertain):
                        await caller.ask(channel, "start", operation_id="held", timeout=5)
                    context_id = requests[0]._task_context.network_context_id
                    with pytest.raises(NetworkBudgetExceeded):
                        await worker.send(channel, "foreign", operation_id="foreign",
                                          _network_context_id="0" * 64, _inherit_context=False)
                    with pytest.raises(NetworkBudgetExceeded):
                        await worker.send(channel, "fresh root", operation_id="root", _inherit_context=False)
                    with pytest.raises(NetworkBudgetExceeded):
                        await caller.ask(channel, "new run", operation_id="fresh", timeout=5)
                    assert [r.operation_id for r in requests] == ["held"]
                    with pytest.raises(ExecutionUncertain):
                        await worker.reconcile(context_id)
                    terminal = True
                    assert (await worker.reconcile(context_id)).text == "held finished"
                    with pytest.raises(NetworkBudgetExceeded):
                        await worker.send(channel, "stale", operation_id="stale",
                                          _network_context_id=context_id, _inherit_context=False)
                    assert (await caller.ask(channel, "new run", operation_id="fresh", timeout=5)).text == "fresh finished"
                    assert [r.operation_id for r in requests] == ["held", "fresh"]
    asyncio.run(scenario())


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "cancelled", "interrupted"])
def test_http_timeout_holds_external_run_across_bridge_reconnect(tmp_path: Path, terminal_status: str):
    from test_http_executor import hermes_api
    from hermes_ag2_network.executor import HermesHTTPExecutor
    from hermes_ag2_network import NetworkLimits

    from hermes_ag2_network.types import ExecutionTerminated
    terminal = {"ready": False, "status": terminal_status}
    with hermes_api(terminal=terminal) as (url, posts):
        async def scenario():
            keys = {"caller": "a", "architect": "b"}
            async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret", deadline=5) as runtime:
                async with network_hub(tmp_path / "hub", keys) as hub:
                    async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite") as caller:
                        async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                                   executor=runtime, ledger_path=tmp_path / "architect.sqlite",
                                                   limits=NetworkLimits(request_timeout=2)) as architect:
                            channel = await caller.open(peer="architect", project_id="live-held")
                            with pytest.raises(ExecutionUncertain):
                                await caller.ask(channel, "stay queued", operation_id="held-http", timeout=5)
                            run_posts = [post for post in posts if post[0].endswith("/v1/runs")]
                            assert len(run_posts) == 1
                            context_id = run_posts[0][1]["X-Hermes-Run-Context-Id"]
                            with pytest.raises(NetworkBudgetExceeded):
                                await caller.ask(channel, "fresh", operation_id="fresh-http", timeout=5)
                            with pytest.raises(ExecutionUncertain):
                                await architect.reconcile(context_id)
                        async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                                   executor=runtime, ledger_path=tmp_path / "architect.sqlite") as restored:
                            with pytest.raises(NetworkBudgetExceeded):
                                await restored.send(channel, "fresh root", operation_id="root-http", _inherit_context=False)
                            terminal["ready"] = True
                            if terminal_status == "completed":
                                result = await restored.reconcile(context_id)
                                assert result.run_id == "http-controlled-run-1"
                                assert result.text == "HTTP runtime replied."
                            else:
                                with pytest.raises(ExecutionTerminated):
                                    await restored.reconcile(context_id)
                                with pytest.raises(ExecutionUncertain):
                                    await caller.ask(channel, "stay queued", operation_id="held-http", timeout=5)
                            with pytest.raises(NetworkBudgetExceeded):
                                await restored.send(channel, "stale", operation_id="stale-http",
                                                    _network_context_id=context_id, _inherit_context=False)
                            assert (await caller.ask(channel, "fresh", operation_id="fresh-http", timeout=5)).text == "HTTP runtime replied."
                            assert len([post for post in posts if post[0].endswith("/v1/runs")]) == 2
                        async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                                   executor=runtime, ledger_path=tmp_path / "architect.sqlite") as again:
                            with pytest.raises(NetworkBudgetExceeded):
                                await again.send(channel, "stale", operation_id="stale-after-restart",
                                                 _network_context_id=context_id, _inherit_context=False)
                            assert (await caller.ask(channel, "fresh after restart", operation_id="fresh-after-restart",
                                                     timeout=5)).text == "HTTP runtime replied."
                            assert len([post for post in posts if post[0].endswith("/v1/runs")]) == 3
        asyncio.run(scenario())
