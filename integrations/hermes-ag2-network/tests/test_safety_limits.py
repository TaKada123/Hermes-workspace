"""Project isolation and per-project grants through the public Network seam."""
import asyncio
from pathlib import Path
import os
import subprocess
from queue import Queue
from threading import Thread

import pytest
from ag2.network import AccessDeniedError

from hermes_ag2_network import (
    ExecutionResult, ExecutionUncertain, Network, NetworkBudgetExceeded, NetworkLimits, network_hub,
)


def test_projects_have_disjoint_channels_sessions_and_history_access(tmp_path: Path):
    async def scenario():
        keys = {
            "caller": "caller-key",
            "architect": "architect-key",
            "designer": "designer-key",
            "outsider": "outsider-key",
        }

        async def architect(request):
            return ExecutionResult(
                text=f"Reviewed {request.project_id}",
                session_id=request.session_origin_id,
                run_id=f"run-{request.operation_id}",
            )

        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(
                hub.url, name="architect", token=keys["architect"],
                allowed_peers=set(), project_peers={"project-a": {"caller"}, "project-b": {"caller"}},
                executor=architect, ledger_path=tmp_path / "architect.sqlite",
            ):
                async with Network.connect(
                    hub.url, name="designer", token=keys["designer"], allowed_peers={"caller"},
                    ledger_path=tmp_path / "designer.sqlite",
                ):
                    async with Network.connect(
                        hub.url, name="outsider", token=keys["outsider"], allowed_peers={"architect"},
                        ledger_path=tmp_path / "outsider.sqlite",
                    ) as outsider:
                        async with Network.connect(
                            hub.url, name="caller", token=keys["caller"], allowed_peers=set(),
                            project_peers={"project-a": {"architect"}, "project-b": {"architect"}},
                            ledger_path=tmp_path / "caller.sqlite",
                        ) as caller:
                            assert [peer.name for peer in await caller.peers(project_id="project-a")] == ["architect"]
                            assert await caller.peers(project_id="ungranted-project") == []

                            channel_a, channel_b = await asyncio.gather(
                                caller.open(peer="architect", project_id="project-a"),
                                caller.open(peer="architect", project_id="project-b"),
                            )
                            assert channel_a != channel_b
                            with pytest.raises(PermissionError, match="project"):
                                await caller.open(peer="designer", project_id="project-a")

                            reply_a, reply_b = await asyncio.gather(
                                caller.ask(channel_a, "Review A", operation_id="project-a-01", timeout=5),
                                caller.ask(channel_b, "Review B", operation_id="project-b-01", timeout=5),
                            )
                            assert reply_a.session_id != reply_b.session_id
                            assert (await caller.history(channel_a))[0].text == "Review A"
                            assert (await caller.history(channel_b))[0].text == "Review B"
                            with pytest.raises(AccessDeniedError):
                                await outsider.history(channel_a)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("max_hops", "max_turns"),
    [(1, 5), (5, 1)],
)
def test_nested_consultation_stops_at_hop_and_turn_budgets(
    tmp_path: Path, max_hops: int, max_turns: int,
):
    async def scenario():
        keys = {"caller": "caller-key", "architect": "architect-key", "designer": "designer-key"}
        limits = NetworkLimits(max_hops=max_hops, max_turns=max_turns, request_timeout=5)
        architect_network: list[Network] = []
        architect_runs = []
        designer_runs = []

        async def architect_executor(request):
            architect_runs.append(request.operation_id)
            channel = await architect_network[0].open(peer="designer", project_id=request.project_id)
            await architect_network[0].ask(channel, "Continue the consultation.",
                                        operation_id=request.operation_id + "-nested", timeout=5)
            return ExecutionResult("unexpectedly reached reply", request.session_current_id, "unexpected")

        async def designer_executor(request):
            designer_runs.append(request.operation_id)
            return ExecutionResult("Designer ran", request.session_current_id, "designer-run")

        async with network_hub(tmp_path / f"hub-{max_hops}-{max_turns}", keys) as hub:
            async with Network.connect(
                hub.url, name="designer", token=keys["designer"], allowed_peers={"architect"},
                executor=designer_executor,
                ledger_path=tmp_path / f"designer-{max_hops}-{max_turns}.sqlite", limits=limits,
            ):
                async with Network.connect(
                    hub.url, name="architect", token=keys["architect"],
                    allowed_peers={"caller", "designer"}, executor=architect_executor,
                    ledger_path=tmp_path / f"architect-{max_hops}-{max_turns}.sqlite", limits=limits,
                ) as architect:
                    architect_network.append(architect)
                    async with Network.connect(
                        hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                        ledger_path=tmp_path / f"caller-{max_hops}-{max_turns}.sqlite", limits=limits,
                    ) as caller:
                        channel = await caller.open(peer="architect", project_id="bounded-chain")
                        with pytest.raises(ExecutionUncertain):
                            await caller.ask(channel, "Start one bounded consultation.",
                                             operation_id=f"bounded-{max_hops}-{max_turns}", timeout=5)
                        assert architect_runs == [f"bounded-{max_hops}-{max_turns}"]
                        assert designer_runs == []

    asyncio.run(scenario())


def test_unsettled_run_is_held_after_caller_reconnect(tmp_path: Path):
    async def scenario():
        keys = {"caller": "caller-key", "architect": "architect-key"}
        limits = NetworkLimits(request_timeout=2)
        started = asyncio.Event()
        executed = []

        async def unsettled(request):
            executed.append(request.operation_id)
            started.set()
            await asyncio.Event().wait()

        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(
                hub.url, name="architect", token=keys["architect"], allowed_peers={"caller"},
                executor=unsettled, ledger_path=tmp_path / "architect.sqlite", limits=limits,
            ):
                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                    ledger_path=tmp_path / "caller.sqlite", limits=limits,
                ) as caller:
                    channel = await caller.open(peer="architect", project_id="uncertain-retry")
                    first_attempt = asyncio.create_task(caller.ask(
                        channel, "Submit this once", operation_id="uncertain-01", timeout=2,
                    ))
                    await asyncio.wait_for(started.wait(), timeout=2)
                    with pytest.raises(ExecutionUncertain):
                        await first_attempt

                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                    ledger_path=tmp_path / "caller.sqlite", limits=limits,
                ) as reconnected:
                    with pytest.raises(ExecutionUncertain):
                        await reconnected.ask(
                            channel, "Submit this once", operation_id="uncertain-01", timeout=2,
                        )
                    assert executed == ["uncertain-01"]

    asyncio.run(scenario())


def test_caller_deadline_after_admission_is_uncertain_and_retry_does_not_execute(tmp_path: Path):
    async def scenario():
        keys = {"caller": "caller-key", "architect": "architect-key"}
        started = asyncio.Event()
        release = asyncio.Event()
        executed = []

        async def specialist(request):
            executed.append(request.operation_id)
            started.set()
            await release.wait()
            return ExecutionResult("Committed once", request.session_origin_id, "run-once")

        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(
                hub.url, name="architect", token=keys["architect"], allowed_peers={"caller"},
                executor=specialist, ledger_path=tmp_path / "architect.sqlite",
            ):
                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                    ledger_path=tmp_path / "caller.sqlite",
                ) as caller:
                    channel = await caller.open(peer="architect", project_id="caller-deadline")
                    pending = asyncio.create_task(caller.ask(
                        channel, "Execute once", operation_id="caller-deadline-01", timeout=2,
                    ))
                    await asyncio.wait_for(started.wait(), timeout=2)
                    try:
                        with pytest.raises(ExecutionUncertain):
                            await pending
                    finally:
                        release.set()
                    with pytest.raises(ExecutionUncertain):
                        await caller.ask(
                            channel, "Execute once", operation_id="caller-deadline-01", timeout=5,
                        )
                    assert executed == ["caller-deadline-01"]

    asyncio.run(scenario())


def test_saved_result_is_replayed_after_caller_reconnect_without_second_run(tmp_path: Path):
    async def scenario():
        keys = {"caller": "caller-key", "architect": "architect-key"}
        executed = []
        completed = asyncio.Event()

        async def specialist(request):
            executed.append(request.operation_id)
            completed.set()
            return ExecutionResult("Committed result", "session-one", "run-one")

        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(
                hub.url, name="architect", token=keys["architect"], allowed_peers={"caller"},
                executor=specialist, ledger_path=tmp_path / "architect.sqlite",
            ):
                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                    ledger_path=tmp_path / "caller.sqlite",
                ) as caller:
                    channel = await caller.open(peer="architect", project_id="lost-reply")
                    await caller.send(channel, "Send once despite the lost reply", operation_id="lost-01")

                await asyncio.wait_for(completed.wait(), timeout=2)
                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                    ledger_path=tmp_path / "caller.sqlite",
                ) as reconnected:
                    reply = await reconnected.ask(
                        channel, "Send once despite the lost reply", operation_id="lost-01", timeout=2,
                    )
                    assert reply.text == "Committed result"
                    with pytest.raises(ExecutionUncertain):
                        await reconnected.ask(
                            channel, "Conflicting input under the same ID", operation_id="lost-01", timeout=2,
                        )
                    replay = await reconnected.ask(
                        channel, "Send once despite the lost reply", operation_id="lost-01", timeout=2,
                    )
                    assert (replay.text, replay.session_id, replay.run_id) == (
                        "Committed result", "session-one", "run-one",
                    )
                    assert executed == ["lost-01"]

    asyncio.run(scenario())


def test_pending_request_cap_backpressures_without_parallel_runs(tmp_path: Path):
    async def scenario():
        keys = {"caller": "caller-key", "architect": "architect-key"}
        server_limits = NetworkLimits(max_pending=1, request_timeout=5)
        caller_limits = NetworkLimits(max_pending=2, request_timeout=5)
        entered = asyncio.Event()
        release = asyncio.Event()
        executed = []
        active = 0
        max_active = 0

        async def specialist(request):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            executed.append(request.operation_id)
            try:
                if request.operation_id == "pending-a":
                    entered.set()
                    await release.wait()
                return ExecutionResult(request.project_id, request.session_origin_id, "run-" + request.operation_id)
            finally:
                active -= 1

        async with network_hub(tmp_path / "hub", keys) as hub:
            async with Network.connect(
                hub.url, name="architect", token=keys["architect"], allowed_peers={"caller"},
                executor=specialist, ledger_path=tmp_path / "architect.sqlite", limits=server_limits,
            ):
                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                    ledger_path=tmp_path / "caller.sqlite", limits=caller_limits,
                ) as caller:
                    channel_a, channel_b = await asyncio.gather(
                        caller.open(peer="architect", project_id="pending-project-a"),
                        caller.open(peer="architect", project_id="pending-project-b"),
                    )
                    first = asyncio.create_task(caller.ask(
                        channel_a, "Run project A", operation_id="pending-a", timeout=5,
                    ))
                    await asyncio.wait_for(entered.wait(), timeout=2)
                    with pytest.raises(NetworkBudgetExceeded):
                        await caller.ask(channel_b, "Run project B", operation_id="pending-b", timeout=5)
                    release.set()
                    assert (await first).text == "pending-project-a"
                    assert (await caller.ask(
                        channel_b, "Run project B", operation_id="pending-b", timeout=5,
                    )).text == "pending-project-b"
                    assert executed == ["pending-a", "pending-b"]
                    assert max_active == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("memory_backend", ["file", "sqlite_v2"])
def test_private_profile_stores_are_not_copied_or_exposed(tmp_path: Path, memory_backend: str, request):
    profile_home = tmp_path / "private-profile"
    profile_home.mkdir()
    (profile_home / "config.yaml").write_text(f"memory:\n  backend: {memory_backend}\n", encoding="utf-8")
    sentinel = "PRIVATE-MEMORY-MUST-STAY-LOCAL-7314"
    core_python = request.config.getoption("--hermes-core-python")
    fixture_code = """
import sys
from agent.memory_store_v2 import MemoryStoreV2
from tools.memory_tool import load_on_disk_store, resolve_memory_backend
from hermes_cli.config import load_config
backend, sentinel = sys.argv[1:]
assert resolve_memory_backend(load_config()) == backend
store = load_on_disk_store()
assert isinstance(store, MemoryStoreV2) == (backend == "sqlite_v2")
assert store.add("memory", sentinel)["success"]
assert store.add("user", "Private user preference: " + sentinel)["success"]
if isinstance(store, MemoryStoreV2):
    assert store.recall("7314")["count"] == 2
# Freeze the normal session-start prompt snapshot after seeding the fixture.
store.load_from_disk()
print("ready", flush=True)
try:
    for command in sys.stdin:
        assert command.strip() == "read"
        assert sentinel in store.format_for_system_prompt("memory")
        assert resolve_memory_backend(load_config()) == backend
        print("verified", flush=True)
finally:
    if isinstance(store, MemoryStoreV2):
        store.close()
"""
    runtime = subprocess.Popen(
        [core_python, "-c", fixture_code, memory_backend, sentinel],
        cwd=Path(__file__).resolve().parents[3],
        env={**os.environ, "HERMES_HOME": str(profile_home)},
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    stdin, stdout, stderr = runtime.stdin, runtime.stdout, runtime.stderr
    assert stdin is not None and stdout is not None and stderr is not None
    lines: Queue[str] = Queue()
    errors = []
    def read_lines():
        for line in stdout:
            lines.put(line.strip())
    def read_errors():
        errors.append(stderr.read())
    reader = Thread(target=read_lines, daemon=True)
    error_reader = Thread(target=read_errors, daemon=True)
    reader.start()
    error_reader.start()
    def shutdown():
        stdin.close()
        try:
            runtime.wait(timeout=30)
        except subprocess.TimeoutExpired:
            runtime.kill()
            runtime.wait(timeout=30)
            raise
        finally:
            reader.join(timeout=5)
            error_reader.join(timeout=5)
            stdout.close()
            stderr.close()
        assert runtime.returncode == 0, "".join(errors)
    request.addfinalizer(shutdown)
    assert lines.get(timeout=30) == "ready", "owning runtime initialization failed"
    def owning_runtime(mode):
        stdin.write(mode + "\n")
        stdin.flush()
        assert lines.get(timeout=30) == "verified", "owning runtime did not respond"
    private_before = {str(path.relative_to(profile_home)): path.read_bytes()
                      for path in profile_home.rglob("*") if path.is_file()}

    async def scenario():
        received = []

        async def executor(request):
            # Controlled owning runtime loads the genuine configured backend. The bridge
            # sees only the explicit response, never the local prompt/store snapshot.
            await asyncio.to_thread(owning_runtime, "read")
            received.append(request.text)
            return ExecutionResult("Approved network response only.", request.session_origin_id, "private-test-run")

        keys = {"caller": "caller-key", "architect": "architect-key"}
        hub_path = tmp_path / "hub"
        caller_ledger = tmp_path / "caller.sqlite"
        architect_ledger = tmp_path / "architect.sqlite"
        async with network_hub(hub_path, keys) as hub:
            async with Network.connect(
                hub.url, name="architect", token=keys["architect"], allowed_peers={"caller"},
                executor=executor, ledger_path=architect_ledger,
            ):
                async with Network.connect(
                    hub.url, name="caller", token=keys["caller"], allowed_peers={"architect"},
                    ledger_path=caller_ledger,
                ) as caller:
                    channel = await caller.open(peer="architect", project_id="private-isolation")
                    reply = await caller.ask(
                        channel, "Public question only", operation_id="private-safe-01", timeout=5,
                    )
                    history = await caller.history(channel)
                    assert received == ["Public question only"]
                    assert reply.text == "Approved network response only."
                    assert all(sentinel not in message.text for message in history)

        owning_runtime("read")
        assert {str(path.relative_to(profile_home)): path.read_bytes()
                for path in profile_home.rglob("*") if path.is_file()} == private_before
        for network_state in (hub_path, caller_ledger, architect_ledger, tmp_path / "network-admission.sqlite"):
            paths = network_state.rglob("*") if network_state.is_dir() else (network_state,)
            assert all(sentinel.encode() not in path.read_bytes() for path in paths if path.is_file())

    asyncio.run(scenario())
