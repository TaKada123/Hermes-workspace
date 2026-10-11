"""Terminal-channel requests are surfaced for explicit operator recovery."""
import asyncio
from pathlib import Path

from hermes_ag2_network import ExecutionResult, Network, network_hub


def test_unanswered_request_on_closed_channel_is_reported_not_replayed(tmp_path: Path):
    async def scenario():
        store = tmp_path / "hub"
        keys = {"caller": "a", "architect": "b"}
        executions = []
        async def executor(request):
            executions.append(request.operation_id)
            return ExecutionResult("This must not run on a closed channel.", "session", "run")

        async with network_hub(store, keys) as hub:
            async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                       ledger_path=tmp_path / "caller.sqlite") as caller:
                async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                           executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                    channel = await caller.open(peer="architect", project_id="closed-recovery")
                request_id = await caller.send(channel, "Do not lose this unresolved request.",
                                               operation_id="closed-request-1")
                await caller.hub_client.close_channel(channel, reason="simulated terminal channel")

        recovered_history = None
        async with network_hub(store, keys) as hub:
            for _ in range(2):
                async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                           executor=executor, ledger_path=tmp_path / "architect.sqlite") as architect:
                    channel_rows = await architect.hub_client.list_channels(agent_id=architect.client.agent_id,
                                                                            include_terminal=True, limit=500)
                    assert any(item.channel_id == channel and item.is_terminal() for item in channel_rows)
                    assert architect.ledger.terminal_requests("architect", "closed-recovery") == [(channel, request_id, "closed-request-1")]
                    history = await architect.history(channel)
                    if recovered_history is None:
                        assert [(message.kind, message.operation_id) for message in history] == [
                            ("request", "closed-request-1"), ("status", "closed-request-1")]
                        notice = history[1]
                        assert notice.causation_id == request_id
                        assert "terminal" in notice.text.lower()
                        assert "operator" in notice.text.lower()
                        recovered_history = history
                    else:
                        assert history == recovered_history
                    async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite") as caller:
                        replacement = await caller.open(peer="architect", project_id="closed-recovery")
                        assert replacement != channel
                        assert await caller.open(peer="architect", project_id="closed-recovery") == replacement
                        new_history = await architect.history(replacement)
                        assert len(new_history) == 1 and new_history[0].kind == "status"
                        assert new_history[0].causation_id == request_id
                        assert channel in new_history[0].envelope_id
                        assert await caller.history(replacement) == []
                    assert executions == []
        assert executions == []

    asyncio.run(scenario())
