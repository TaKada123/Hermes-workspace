"""Completed operation retry must not append another native request/reply (#21)."""
import asyncio
from typing import Any

import pytest

from hermes_ag2_network import ExecutionResult, ExecutionUncertain, Network, network_hub


def test_completed_operation_replays_same_envelopes_across_restart_and_rejects_conflicting_payload(tmp_path):
    async def scenario():
        async def owner(request):
            return ExecutionResult('verified advice', 'owned-session', 'owned-run')

        keys = {'coding': 'coding-key', 'architect': 'architect-key'}
        kwargs: dict[str, Any] = {'name': 'coding', 'token': keys['coding'], 'allowed_peers': {'architect'},
                  'ledger_path': tmp_path / 'coding.sqlite'}
        async with network_hub(tmp_path / 'hub', keys) as hub:
            async with Network.connect(hub.url, name='architect', token=keys['architect'], allowed_peers={'coding'},
                                       ledger_path=tmp_path / 'architect.sqlite', executor=owner):
                async with Network.connect(hub.url, **kwargs) as coding:
                    channel = await coding.open(peer='architect', project_id='project')
                    first = await coding.ask(channel, 'review', operation_id='stable')
                    history = await coding.history(channel)
                    replay = await coding.ask(channel, 'review', operation_id='stable')
                    assert replay == first
                    assert await coding.history(channel) == history
                    assert await coding.send(channel, 'review', operation_id='stable') == first.request_id
                    assert await coding.history(channel) == history
                    with pytest.raises(ExecutionUncertain):
                        await coding.ask(channel, 'changed', operation_id='stable')
                    assert await coding.history(channel) == history
        async with network_hub(tmp_path / 'hub', keys) as hub:
            # Replay a terminal receipt even while the recipient is offline: no new execution/transport.
            async with Network.connect(hub.url, **kwargs) as coding:
                assert await coding.ask(channel, 'review', operation_id='stable', timeout=2) == first
                assert await coding.history(channel) == history
    asyncio.run(scenario())
