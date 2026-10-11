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
                            first = await caller.ask(channel, "first", operation_id="request-1", timeout=5)

            # Both disk-backed Hub and profile bridges restart. The existing
            # AG2 channel and per-profile ledger must continue the same Hermes session.
            async with network_hub(store, keys) as hub:
                second = await ask_once(hub.url, channel, "request-2", "second")
                third = await ask_once(hub.url, channel, "request-3", "third")
                replayed = await ask_once(hub.url, channel, "request-1", "first")
                assert first.session_id.startswith("ag2-")
                assert second.session_id == "rotated-session"
                assert third.session_id == "rotated-session"
                assert replayed.session_id == first.session_id
                session_posts = [body for path, _, body in requests if path.endswith("/api/sessions")]
                run_posts = [body for path, _, body in requests if path.endswith("/v1/runs")]
                assert all(body["id"] == first.session_id for body in session_posts)
                # Hermes' run response is stale on a mid-run rotation; only
                # the explicit session-tip endpoint advances the next turn.
                assert [body["session_id"] for body in run_posts] == [
                    first.session_id, first.session_id, "rotated-session"]
                assert [body["input"] for body in run_posts] == ["first", "second", "third"]
                assert [requests[index][1]["Idempotency-Key"] for index in (1, 3, 5)] == [
                    "request-1", "request-2", "request-3"]

        asyncio.run(scenario())
