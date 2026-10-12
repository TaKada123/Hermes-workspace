"""Failure at the public seam stays held instead of auto-executing again."""
import asyncio
from pathlib import Path

import pytest

from hermes_ag2_network import ExecutionUncertain, Network, network_hub


def test_uncertain_executor_is_held_without_automatic_retry(tmp_path: Path):
    executed = []

    async def executor(request):
        executed.append(request.text)  # Observable external executor boundary.
        raise RuntimeError("sensitive exception text must not be placed in a network status")

    async def scenario():
        async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
            async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                       executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                           ledger_path=tmp_path / "caller.sqlite") as caller:
                    channel = await caller.open(peer="architect", project_id="held-work")
                    for _ in range(2):
                        with pytest.raises(ExecutionUncertain, match="operator reconciliation"):
                            await caller.ask(channel, "Execute one operation.", operation_id="held-01", timeout=5)
                    history = await caller.history(channel)
                    # Retry is refused locally, not persisted as unlimited duplicate work.
                    assert [m.kind for m in history] == ["request", "status"]
                    assert all("sensitive exception text" not in m.text for m in history)
                    assert executed == ["Execute one operation."]
    asyncio.run(scenario())
