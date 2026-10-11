"""Authenticated, profile-bound loopback tool API exercises the public Network seam."""
import asyncio
from pathlib import Path

import httpx
import pytest

from hermes_ag2_network import ExecutionResult, Network, network_hub
from hermes_ag2_network.tool_api import ToolAPI


def test_local_tool_api_authenticates_and_exposes_network_operations(tmp_path: Path):
    async def scenario():
        received = []

        async def architect(request):
            received.append(request)
            return ExecutionResult(
                text=f"Architect reviewed: {request.text}",
                session_id="architect-session", run_id=f"run-{request.operation_id}",
            )

        keys = {"caller": "caller-hub-key", "architect": "architect-hub-key"}
        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(
                hub.url, name="architect", token=keys["architect"], allowed_peers={"caller"},
                executor=architect, ledger_path=tmp_path / "architect.sqlite",
            ):
                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                    ledger_path=tmp_path / "caller.sqlite",
                ) as caller:
                    async with ToolAPI(caller, "caller-tools-key", port=0) as tool_api:
                        async with httpx.AsyncClient() as client:
                            headers = {"Authorization": "Bearer caller-tools-key", "X-Hermes-Profile": "caller"}
                            assert (await client.get(tool_api.url + "/v1/peers")).status_code == 401
                            wrong_profile = {**headers, "X-Hermes-Profile": "architect"}
                            assert (await client.get(tool_api.url + "/v1/peers", headers=wrong_profile)).status_code == 403

                            peers = await client.get(tool_api.url + "/v1/peers", headers=headers)
                            assert peers.status_code == 200
                            assert [peer["name"] for peer in peers.json()["result"]] == ["architect"]

                            denied = await client.post(tool_api.url + "/v1/open", headers=headers,
                                                       json={"peer": "unknown", "project_id": "api-test"})
                            assert denied.status_code == 403

                            missing = await client.get(tool_api.url + "/v1/history", headers=headers,
                                                      params={"channel_id": "not-an-owned-channel"})
                            assert missing.status_code == 404

                            opened = await client.post(tool_api.url + "/v1/open", headers=headers,
                                                       json={"peer": "architect", "project_id": "api-test"})
                            assert opened.status_code == 200
                            channel_id = opened.json()["result"]["channel_id"]

                            asked = await client.post(tool_api.url + "/v1/ask", headers=headers, json={
                                "channel_id": channel_id,
                                "text": "Review this project-bound request.",
                                "operation_id": "api-ask-01",
                                "timeout_seconds": 5,
                            })
                            assert asked.status_code == 200
                            answer = asked.json()["result"]
                            assert answer["kind"] == "reply"
                            assert answer["text"] == "Architect reviewed: Review this project-bound request."
                            assert answer["request_id"] and answer["session_id"] == "architect-session"
                            assert received[0].profile == "architect"

                            sent = await client.post(tool_api.url + "/v1/send", headers=headers, json={
                                "channel_id": channel_id,
                                "text": "Also check the follow-up.",
                                "operation_id": "api-send-02",
                            })
                            assert sent.status_code == 200
                            assert sent.json()["result"]["operation_id"] == "api-send-02"
                            await asyncio.sleep(0.05)

                            history = await client.get(tool_api.url + "/v1/history",
                                                       headers=headers, params={"channel_id": channel_id})
                            assert history.status_code == 200
                            messages = history.json()["result"]
                            assert [(item["kind"], item["operation_id"]) for item in messages] == [
                                ("request", "api-ask-01"), ("reply", "api-ask-01"),
                                ("request", "api-send-02"), ("reply", "api-send-02"),
                            ]
                            assert messages[1]["causation_id"] == messages[0]["envelope_id"]

        # The endpoint is an opt-in listener, and its context manager closes it.
        async with httpx.AsyncClient() as client:
            with pytest.raises(httpx.ConnectError):
                await client.get(tool_api.url + "/v1/peers")

    asyncio.run(scenario())
