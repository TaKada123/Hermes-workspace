"""All acceptance network paths, including the outer control channel, exclude canaries."""
import asyncio

import pytest

from hermes_ag2_network.live_runtime import AcceptanceBlocked
from hermes_ag2_network.live_scenario import LiveScenario


@pytest.mark.parametrize('leaking', ['outer', 'unrecorded'])
def test_private_marker_in_control_or_unrecorded_channel_blocks_acceptance(tmp_path, monkeypatch, leaking):
    async def scenario():
        owner = LiveScenario('http://127.0.0.1:1', {}, home=tmp_path, state_dir=tmp_path / 'state')
        owner.memories = {'coding': {'marker': 'private-canary'}}
        owner.projects = ['project']
        owner.receipt['channels'] = {'project': {'coding_architect': 'peer', 'acceptance_coding': 'outer'}}
        async def tool(profile, method, path, **kwargs):
            if path == '/v1/channels':
                return [{'channel_id': channel, 'project_id': 'project'} for channel in ['peer', 'outer', 'unrecorded']]
            channel = kwargs['params']['channel_id']
            return [{'kind': 'reply', 'text': 'private-canary'}] if channel == leaking else []
        monkeypatch.setattr(owner, 'tool', tool)
        try:
            with pytest.raises(AcceptanceBlocked, match='canary'):
                await owner.verify_histories()
        finally:
            await owner.readbacks.http.aclose()
    asyncio.run(scenario())
