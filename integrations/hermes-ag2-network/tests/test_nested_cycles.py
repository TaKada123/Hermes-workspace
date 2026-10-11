"""Nested network asks reject a visited specialist without deadlocking."""
import asyncio
from pathlib import Path

import httpx

from hermes_ag2_network import ExecutionResult, Network, network_hub
from hermes_ag2_network.tool_api import ToolAPI


def test_nested_request_cannot_reenter_a_profile_already_in_the_chain(tmp_path: Path):
    async def scenario():
        calls = {"coding": 0, "architect": 0}
        coding_network: Network
        tool_api: ToolAPI
        consulted_channels = []

        async def coding_executor(request):
            calls["coding"] += 1
            if request.text == "A fresh unrelated request.":
                return ExecutionResult(
                    text="The independent request completed.",
                    session_id="coding-session", run_id="coding-run-2",
                )
            assert request.text == "Please consult Architect and continue."
            channel = await coding_network.open(peer="architect", project_id=request.project_id)
            consulted_channels.append(channel)
            reply = await coding_network.ask(
                channel, "Assess this design decision.", operation_id="coding-to-architect", timeout=2,
            )
            return ExecutionResult(
                text=f"I consulted Architect: {reply.text}",
                session_id="coding-session", run_id="coding-run",
            )

        async def architect_executor(request):
            calls["architect"] += 1
            async with httpx.AsyncClient() as client:
                cycle = await client.post(
                    tool_api.url + "/v1/ask",
                    headers={"Authorization": "Bearer architect-tools-key", "X-Hermes-Profile": "architect"},
                    json={"channel_id": request.channel_id,
                          "text": "Ask Coding to review me back.",
                          "operation_id": "architect-to-coding", "timeout_seconds": 2},
                )
            assert cycle.status_code == 409
            assert cycle.json()["error"] == "network cycle detected; request rejected before delivery"
            return ExecutionResult(
                text="The design is sound; preserve the session and keep the API narrow.",
                session_id="architect-session", run_id="architect-run",
            )

        async with network_hub(tmp_path / "hub", {
            "caller": "caller-key", "coding": "coding-key", "architect": "architect-key",
        }) as hub:
            async with Network.connect(
                hub.url, name="architect", token="architect-key", allowed_peers={"coding"},
                executor=architect_executor, ledger_path=tmp_path / "architect.sqlite",
            ) as architect:
                async with ToolAPI(architect, "architect-tools-key", port=0) as tool_api:
                    async with Network.connect(
                        hub.url, name="coding", token="coding-key", allowed_peers={"caller", "architect"},
                        executor=coding_executor, ledger_path=tmp_path / "coding.sqlite",
                    ) as coding:
                        coding_network = coding
                        async with Network.connect(
                            hub.url, name="caller", token="caller-key", allowed_peers={"coding"},
                            ledger_path=tmp_path / "caller.sqlite",
                        ) as caller:
                            channel = await caller.open(peer="coding", project_id="cycle-test")
                            reply = await caller.ask(
                                channel, "Please consult Architect and continue.",
                                operation_id="caller-to-coding", timeout=5,
                            )
                            assert reply.kind == "reply"
                            assert reply.text == (
                                "I consulted Architect: The design is sound; preserve the session and keep the API narrow."
                            )
                            history = await coding.history(consulted_channels[0])
                            assert [message.kind for message in history] == ["request", "reply"]
                            fresh = await caller.ask(
                                channel, "A fresh unrelated request.",
                                operation_id="caller-to-coding-02", timeout=5,
                            )
                            assert fresh.text == "The independent request completed."
                            assert calls == {"coding": 2, "architect": 1}

    asyncio.run(scenario())
