"""Session continuation is observable across operation IDs and Hub/bridge restart."""
import asyncio
from pathlib import Path

from hermes_ag2_network import Network, network_hub
from hermes_ag2_network.executor import HermesHTTPExecutor
from test_http_executor import hermes_api


def test_session_lineage_survives_restart_and_native_rotation(tmp_path: Path):
    with hermes_api() as (url, requests):
        async def ask_once(hub_url, channel, operation_id, text):
            async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret") as executor:
                async with Network.connect(hub_url, name="architect", token="b", allowed_peers={"caller"},
                                           executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                    async with Network.connect(hub_url, name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite") as caller:
                        return await caller.ask(channel, text, operation_id=operation_id, timeout=5)

        async def ask_project_once(hub_url, project_id, operation_id, text):
            async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret") as executor:
                async with Network.connect(hub_url, name="architect", token="b", allowed_peers={"caller"},
                                           executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                    async with Network.connect(hub_url, name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite") as caller:
                        channel = await caller.open(peer="architect", project_id=project_id)
                        return channel, await caller.ask(channel, text, operation_id=operation_id, timeout=5)

        async def scenario():
            store = tmp_path / "hub"
            keys = {"caller": "a", "architect": "b"}
            async with network_hub(store, keys) as hub:
                async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret") as executor:
                    async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                               executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                        async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                                   ledger_path=tmp_path / "caller.sqlite") as caller:
                            channel = await caller.open(peer="architect", project_id="lineage")
                            assert await caller.open(peer="architect", project_id="lineage") == channel
                            first = await caller.ask(channel, "first", operation_id="request-1", timeout=5)

            # Both disk-backed Hub and profile bridges restart. The existing
            # AG2 channel and per-profile ledger must continue the same Hermes session.
            async with network_hub(store, keys) as hub:
                async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                           ledger_path=tmp_path / "caller.sqlite") as caller:
                    # Recover channel identity from native Hub state if the
                    # local channel mapping was lost after a process crash.
                    caller.ledger.forget_channel("caller", "architect", "lineage")
                    assert await caller.open(peer="architect", project_id="lineage") == channel
                second = await ask_once(hub.url, channel, "request-2", "second")
                third = await ask_once(hub.url, channel, "request-3", "third")
                isolated_channel, isolated = await ask_project_once(hub.url, "project-two", "request-4", "isolated project")
                replayed = await ask_once(hub.url, channel, "request-1", "first")
                assert first.session_id.startswith("ag2-")
                assert second.session_id == f"rotated-{first.session_id}"
                assert third.session_id == f"rotated-{first.session_id}"
                assert replayed.session_id == first.session_id
                assert isolated_channel != channel
                assert isolated.session_id.startswith("ag2-") and isolated.session_id != first.session_id
                session_posts = [body for path, _, body in requests if path.endswith("/api/sessions")]
                run_posts = [body for path, _, body in requests if path.endswith("/v1/runs")]
                assert [body["id"] for body in session_posts] == [first.session_id] * 3 + [isolated.session_id]
                # Hermes' run response is stale on a mid-run rotation; only
                # the explicit session-tip endpoint advances the next turn.
                assert [body["session_id"] for body in run_posts] == [
                    first.session_id, first.session_id, f"rotated-{first.session_id}", isolated.session_id]
                assert [body["input"] for body in run_posts] == ["first", "second", "third", "isolated project"]
                assert [requests[index][1]["Idempotency-Key"] for index in (1, 3, 5, 7)] == [
                    "request-1", "request-2", "request-3", "request-4"]
                async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret") as executor:
                    async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                               executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                        async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                                   ledger_path=tmp_path / "caller.sqlite") as caller:
                            assert await caller.open(peer="architect", project_id="lineage") == channel
                            await caller.hub_client.close_channel(channel, reason="test terminal channel handling")
                            replacement = await caller.open(peer="architect", project_id="lineage")
                            assert replacement != channel
                            assert await caller.open(peer="architect", project_id="lineage") == replacement

        asyncio.run(scenario())
