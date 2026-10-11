"""An undelivered native WAL request is reconciled after a recipient restart."""
import asyncio
from pathlib import Path

from hermes_ag2_network import ExecutionResult, Network, network_hub


def test_unreplayed_request_runs_once_after_bridge_and_hub_restart(tmp_path: Path):
    async def scenario():
        store = tmp_path / "hub"
        keys = {"caller": "a", "architect": "b"}
        executions = []
        async def executor(request):
            executions.append(request.operation_id)
            return ExecutionResult("Recovered from the native WAL.", "session-1", "run-1")

        async with network_hub(store, keys) as hub:
            async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                       ledger_path=tmp_path / "caller.sqlite") as caller:
                async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                           executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                    channel = await caller.open(peer="architect", project_id="replay")
                # The receiver is offline. AG2 persists the request in channel WAL.
                request_id = await caller.send(channel, "Deliver after reconnect.", operation_id="replay-1")


        assert executions == []
        async with network_hub(store, keys) as hub:
            async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                       executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                           ledger_path=tmp_path / "caller.sqlite") as caller:
                    history = await caller.history(channel)
                    assert [(m.kind, m.text) for m in history] == [
                        ("request", "Deliver after reconnect."),
                        ("reply", "Recovered from the native WAL."),
                    ]
                    assert history[0].envelope_id == request_id
                    assert history[1].causation_id == request_id
                    assert executions == ["replay-1"]
        assert executions == ["replay-1"]

    asyncio.run(scenario())
