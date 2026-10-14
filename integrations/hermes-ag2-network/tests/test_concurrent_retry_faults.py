"""Native concurrent retry/cancellation faults: uncertain admission is never replayed."""
import asyncio

import pytest

from hermes_ag2_network import ExecutionResult, ExecutionUncertain, Network, network_hub


def test_concurrent_retry_and_interrupted_caller_do_not_reexecute(tmp_path):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        executions = []
        async def execute(request):
            executions.append(request.operation_id)
            entered.set()
            await release.wait()
            return ExecutionResult('one result', request.session_origin_id, 'one-run')
        async with network_hub(tmp_path / 'hub', {'caller': 'a', 'worker': 'b'}) as hub:
            async with Network.connect(hub.url, name='worker', token='b', allowed_peers={'caller'},
                                       executor=execute, ledger_path=tmp_path / 'worker.sqlite'):
                async with Network.connect(hub.url, name='caller', token='a', allowed_peers={'worker'},
                                           ledger_path=tmp_path / 'caller.sqlite') as caller:
                    channel = await caller.open(peer='worker', project_id='retry-project')
                    pending = asyncio.create_task(caller.ask(channel, 'execute once', operation_id='once', timeout=5))
                    try:
                        await asyncio.wait_for(entered.wait(), 5)
                        with pytest.raises(ValueError, match='operation already awaited'):
                            await caller.ask(channel, 'execute once', operation_id='once', timeout=5)
                        pending.cancel()
                        with pytest.raises(asyncio.CancelledError):
                            await pending
                        with pytest.raises(ExecutionUncertain):
                            await caller.ask(channel, 'execute once', operation_id='once', timeout=5)
                        history = await caller.history(channel)
                        assert len([row for row in history if row.kind == 'request']) == 1
                        assert executions == ['once']
                    finally:
                        release.set()
                        if not pending.done():
                            pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)
    asyncio.run(scenario())
