"""Observable agent_network contract; real AG2 disk hub and WS transport."""
import asyncio
from pathlib import Path

import pytest
from ag2.network import ProtocolError
from hermes_ag2_network import ExecutionResult, Network, network_hub


def test_incomplete_project_invitation_is_rejected_without_running_executor(tmp_path: Path):
    async def scenario():
        async def forbidden_executor(request):
            raise AssertionError("untrusted channel metadata must not reach the executor")

        async with network_hub(tmp_path / "hub", {"caller": "caller-key", "architect": "architect-key"}) as hub:
            async with Network.connect(hub.url, name="architect", token="architect-key",
                                       allowed_peers={"caller"}, executor=forbidden_executor,
                                       ledger_path=tmp_path / "architect.sqlite"):
                async with Network.connect(hub.url, name="caller", token="caller-key",
                                           allowed_peers={"architect"}, ledger_path=tmp_path / "caller.sqlite") as caller:
                    with pytest.raises(ProtocolError, match="invite_rejected"):
                        await caller.client.open(type="conversation", target="architect",
                                                 labels={"protocol": "hermes-tracer-v1"})

    asyncio.run(scenario())


def test_request_reply_is_durable_without_reply_ping_pong(tmp_path: Path):
    async def scenario():
        async def specialist(request):
            assert request.profile == "architect"
            assert request.text == "Review a two-party transport"
            return ExecutionResult(text="Keep the execution boundary external.",
                                   session_id="controlled-session", run_id="controlled-run")

        async def no_reply_execution(request):
            raise AssertionError("a reply must not execute another Hermes turn")

        async with network_hub(tmp_path / "hub", {"caller": "caller-key", "architect": "architect-key"}) as hub:
            async with Network.connect(hub.url, name="architect", token="architect-key",
                                       allowed_peers={"caller"}, executor=specialist,
                                       ledger_path=tmp_path / "architect.sqlite"):
                async with Network.connect(hub.url, name="caller", token="caller-key",
                                           allowed_peers={"architect"}, executor=no_reply_execution,
                                           ledger_path=tmp_path / "caller.sqlite") as caller:
                    assert [p.name for p in await caller.peers()] == ["architect"]
                    channel = await caller.open(peer="architect", project_id="tracer")
                    reply = await caller.ask(channel, "Review a two-party transport", operation_id="tracer-01", timeout=5)
                    assert reply.text == "Keep the execution boundary external."
                    assert reply.operation_id == "tracer-01"
                    assert reply.session_id == "controlled-session"
                    assert reply.run_id == "controlled-run"
                    history = await caller.history(channel)
                    assert [(m.kind, m.text) for m in history] == [
                        ("request", "Review a two-party transport"),
                        ("reply", "Keep the execution boundary external."),
                    ]
                    assert history[1].causation_id == history[0].envelope_id == reply.request_id
                    assert history[1].envelope_id == reply.envelope_id
                    # Wait for the reply receipt to settle; a loop would add another turn.
                    await asyncio.sleep(0.1)
                    assert await caller.history(channel) == history
                    original_peer_id = (await caller.peers())[0].agent_id
        # A fresh native hub hydrates the disk registry and channel WAL.
        async with network_hub(tmp_path / "hub", {"caller": "caller-key", "architect": "architect-key"}) as hub:
            async with Network.connect(hub.url, name="caller", token="caller-key",
                                       allowed_peers={"architect"}, ledger_path=tmp_path / "caller.sqlite") as caller:
                assert (await caller.peers())[0].agent_id == original_peer_id
                assert await caller.history(channel) == history
    asyncio.run(scenario())
