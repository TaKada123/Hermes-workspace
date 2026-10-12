"""Controlled send backpressure at the public Network seam (regression for #19)."""
import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from hermes_ag2_network import (
    ExecutionResult, ExecutionUncertain, Network, NetworkBudgetExceeded, NetworkLimits, network_hub,
)


@pytest.mark.parametrize("terminal_failure", [False, True])
def test_crossparticipant_send_refuses_before_wal_when_shared_capacity_is_held(tmp_path: Path, terminal_failure):
    async def scenario():
        executed = []
        class Runtime:
            async def __call__(self, request):
                executed.append(request)
                raise ExecutionUncertain("external work remains live")
            async def reconcile(self, request):
                if terminal_failure:
                    from hermes_ag2_network.types import ExecutionTerminated
                    raise ExecutionTerminated("authenticated failed Run")
                return ExecutionResult("terminal result", request.session_current_id, "held-run")
        names = {"caller", "other", "a", "b"}
        limits = NetworkLimits(max_active=1, max_pending=1)
        async with network_hub(tmp_path / "hub", {n: n for n in names}) as hub:
            async with AsyncExitStack() as stack:
                networks = {}
                for n in sorted(names):
                    networks[n] = await stack.enter_async_context(Network.connect(
                        hub.url, name=n, token=n, allowed_peers=names - {n},
                        executor=Runtime() if n in {"a", "b"} else None,
                        ledger_path=tmp_path / n / "ledger.sqlite", control_path=tmp_path / "shared.sqlite",
                        limits=limits))
                a = await networks["caller"].open(peer="a", project_id="one")
                b = await networks["other"].open(peer="b", project_id="two")
                with pytest.raises(ExecutionUncertain):
                    await networks["caller"].ask(a, "hold", operation_id="held", timeout=5)
                for i in range(5):
                    with pytest.raises(NetworkBudgetExceeded):
                        await networks["other"].send(b, "new transport request", operation_id=f"other-{i}")
                assert [m for m in await networks["other"].history(b) if m.kind == "request"] == []
                assert [r.operation_id for r in executed] == ["held"]
                # Reconciliation releases both execution and async transport capacity.
                context_id = executed[0]._task_context.network_context_id
                if terminal_failure:
                    from hermes_ag2_network.types import ExecutionTerminated
                    with pytest.raises(ExecutionTerminated):
                        await networks["a"].reconcile(context_id)
                    # Terminal failure cannot turn into a fresh execution on retry,
                    # and its status must not retain another transport reservation.
                    with pytest.raises(ExecutionUncertain):
                        await networks["caller"].ask(a, "hold", operation_id="held", timeout=5)
                else:
                    await networks["a"].reconcile(context_id)
                with pytest.raises(ExecutionUncertain):
                    await networks["other"].ask(b, "new transport request", operation_id="other-0", timeout=5)
                assert [r.operation_id for r in executed] == ["held", "other-0"]
    asyncio.run(scenario())


@pytest.mark.parametrize("limits, cause", [
    (NetworkLimits(max_active=1, max_pending=2), "global_capacity"),
    (NetworkLimits(max_active=2, max_pending=1), "pending_capacity"),
])
def test_async_ack_keeps_shared_reservation_until_terminal_reply_across_reconnect(tmp_path: Path, limits, cause):
    import httpx
    from hermes_ag2_network.tool_api import ToolAPI

    async def scenario():
        names = {"caller", "other", "worker"}
        async def runtime(request):
            return ExecutionResult("completed " + request.operation_id, request.session_current_id, "run-" + request.operation_id)
        def connect(name, executor=None):
            return Network.connect(hub.url, name=name, token=name, allowed_peers=names - {name},
                                   executor=executor, limits=limits, ledger_path=tmp_path / (name + ".sqlite"))
        async with network_hub(tmp_path / "hub", {n: n for n in names}) as hub:
            # Enroll, then take the recipient offline: send gets a real native ACK,
            # but no terminal reply. No event-loop timing assumption is needed.
            async with connect("worker"):
                async with connect("caller") as caller:
                    first = await caller.open(peer="worker", project_id="one")
            async with connect("caller") as caller:
                request_id = await caller.send(first, "queued request", operation_id="queued")
            async with connect("caller") as caller, connect("other") as other:
                with pytest.raises(ExecutionUncertain):
                    await caller.send(first, "queued request", operation_id="queued")
                assert [m.envelope_id for m in await caller.history(first) if m.kind == "request"] == [request_id]
                async with connect("worker", runtime):
                    # Recipient reconnect replays the unseen request once and releases
                    # its reservation only after recording the terminal result/receipt.
                    assert [m.kind for m in await caller.history(first)] == ["request", "reply"]
                    second = await other.open(peer="worker", project_id="two")
                # Recipient offline again: reserve the recovered slot with an async send.
                await other.send(second, "second queued", operation_id="second")
                async with ToolAPI(caller, "tools", port=0) as api, httpx.AsyncClient() as client:
                    response = await client.post(api.url + "/v1/send", headers={
                        "Authorization": "Bearer tools", "X-Hermes-Profile": "caller",
                    }, json={"channel_id": first, "text": "blocked", "operation_id": "blocked"})
                    assert response.status_code == 429
                    detail = response.json()["admission"]
                    assert detail["code"] == cause
                    assert "same operation ID" in detail["remediation"]
                assert [m.operation_id for m in await caller.history(first) if m.kind == "request"] == ["queued"]
                async with connect("worker", runtime):
                    assert (await caller.ask(first, "fresh", operation_id="fresh", timeout=5)).text == "completed fresh"
    asyncio.run(scenario())


def test_nested_capacity_refusal_does_not_wait_for_its_own_parent_slot(tmp_path: Path):
    async def scenario():
        networks = {}
        child_channels = []
        async def runtime(request):
            assert request.profile == "a"
            channel = await networks["a"].open(peer="b", project_id=request.project_id)
            child_channels.append(channel)
            with pytest.raises(NetworkBudgetExceeded) as refused:
                await networks["a"].ask(channel, "child", operation_id="child", timeout=5)
            assert refused.value.code == "global_capacity"
            return ExecutionResult("parent completed without deadlock", request.session_current_id, "run-parent")
        names = {"caller", "a", "b"}
        async with network_hub(tmp_path / "hub", {n: n for n in names}) as hub:
            async with AsyncExitStack() as stack:
                for n in sorted(names):
                    networks[n] = await stack.enter_async_context(Network.connect(
                        hub.url, name=n, token=n, allowed_peers=names - {n},
                        executor=runtime if n != "caller" else None, ledger_path=tmp_path / (n + ".sqlite"),
                        limits=NetworkLimits(max_active=1, max_pending=1)))
                channel = await networks["caller"].open(peer="a", project_id="nested")
                for operation in ("first", "second"):
                    assert (await networks["caller"].ask(channel, "root", operation_id=operation, timeout=5)).kind == "reply"
                assert [m for m in await networks["a"].history(child_channels[0]) if m.kind == "request"] == []
    asyncio.run(scenario())


def test_remote_profile_admission_cause_and_remediation_survive_reply(tmp_path: Path):
    async def scenario():
        async def runtime(request):
            raise ExecutionUncertain("secret must not leak")
        async with network_hub(tmp_path / "hub", {"caller": "a", "worker": "b"}) as hub:
            async with Network.connect(hub.url, name="worker", token="b", allowed_peers={"caller"},
                                       executor=runtime, ledger_path=tmp_path / "worker.sqlite"):
                async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"worker"},
                                           ledger_path=tmp_path / "caller.sqlite") as caller:
                    channel = await caller.open(peer="worker", project_id="held")
                    with pytest.raises(ExecutionUncertain):
                        await caller.ask(channel, "hold", operation_id="held", timeout=5)
                    for i in range(2):
                        with pytest.raises(NetworkBudgetExceeded) as refused:
                            await caller.ask(channel, "fresh", operation_id="fresh-" + str(i), timeout=5)
                        assert refused.value.code == "profile_held"
                        assert "owning profile" in refused.value.remediation
                    history = await caller.history(channel)
                    assert [m.admission_code for m in history if m.kind == "rejected"] == ["profile_held", "profile_held"]
                    assert all("secret must not leak" not in m.text for m in history)
    asyncio.run(scenario())


def test_lost_native_ack_retains_capacity_and_does_not_resubmit(tmp_path: Path, monkeypatch):
    async def scenario():
        async def runtime(request):
            raise ExecutionUncertain("external execution remains live")
        async with network_hub(tmp_path / "hub", {"caller": "a", "worker": "b"}) as hub:
            limits = NetworkLimits(max_active=1, max_pending=1)
            async with Network.connect(hub.url, name="worker", token="b", allowed_peers={"caller"},
                                       executor=runtime, ledger_path=tmp_path / "worker.sqlite", limits=limits):
                async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"worker"},
                                           ledger_path=tmp_path / "caller.sqlite", limits=limits) as caller:
                    channel = await caller.open(peer="worker", project_id="lost-ack")
                    native_send = caller.client.send_envelope
                    async def lose_ack(envelope):
                        await native_send(envelope)  # Real WS/disk acceptance, not a fabricated response.
                        await asyncio.Event().wait()  # Lose ACK until the bounded caller deadline.
                    monkeypatch.setattr(caller.client, "send_envelope", lose_ack)
                    with pytest.raises(ExecutionUncertain, match="submission deadline"):
                        await caller.ask(channel, "once", operation_id="once", timeout=2)
                    monkeypatch.setattr(caller.client, "send_envelope", native_send)
                    with pytest.raises(ExecutionUncertain):
                        await caller.send(channel, "once", operation_id="once")
                    with pytest.raises(NetworkBudgetExceeded):
                        await caller.send(channel, "fresh", operation_id="fresh")
                    assert [m.operation_id for m in await caller.history(channel) if m.kind == "request"] == ["once"]
    asyncio.run(scenario())


def test_definite_missing_executor_refusal_releases_transport_capacity(tmp_path: Path):
    async def scenario():
        keys = {"caller": "a", "worker": "b"}
        limits = NetworkLimits(max_active=1, max_pending=1)
        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"worker"},
                                       ledger_path=tmp_path / "caller.sqlite", limits=limits) as caller:
                async with Network.connect(hub.url, name="worker", token="b", allowed_peers={"caller"},
                                           ledger_path=tmp_path / "worker.sqlite", limits=limits):
                    channel = await caller.open(peer="worker", project_id="missing-executor")
                    for _ in range(2):
                        with pytest.raises(NetworkBudgetExceeded) as refused:
                            await caller.ask(channel, "safe request", operation_id="same", timeout=5)
                        assert refused.value.code == "executor_unavailable"
                async def runtime(request):
                    return ExecutionResult("executed after enrollment", request.session_current_id, "run")
                async with Network.connect(hub.url, name="worker", token="b", allowed_peers={"caller"},
                                           executor=runtime, ledger_path=tmp_path / "worker.sqlite", limits=limits):
                    assert (await caller.ask(channel, "safe request", operation_id="same", timeout=5)).text == "executed after enrollment"
    asyncio.run(scenario())
