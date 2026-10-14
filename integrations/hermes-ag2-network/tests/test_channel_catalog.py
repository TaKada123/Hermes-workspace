"""Authenticated channel discovery covers unrecorded channels without widening grants."""
import asyncio

import httpx

from hermes_ag2_network import Network, network_hub
from hermes_ag2_network.tool_api import ToolAPI


def test_catalog_returns_all_owned_project_channels_only(tmp_path):
    async def scenario():
        async with network_hub(tmp_path / 'hub', {'caller': 'a', 'worker': 'b'}) as hub:
            async with Network.connect(hub.url, name='worker', token='b', allowed_peers={'caller'},
                                       ledger_path=tmp_path / 'worker.sqlite'):
                async with Network.connect(hub.url, name='caller', token='a', allowed_peers={'worker'},
                                           ledger_path=tmp_path / 'caller.sqlite') as caller:
                    owned = await caller.open(peer='worker', project_id='owned')
                    await caller.open(peer='worker', project_id='other')
                    async with ToolAPI(caller, 'test-token', port=0) as api:
                        async with httpx.AsyncClient(trust_env=False) as client:
                            url = api.url + '/v1/channels'
                            assert (await client.get(url, params={'project_id': 'owned'})).status_code == 401
                            response = await client.get(url, params={'project_id': 'owned'}, headers={
                                'Authorization': 'Bearer test-token', 'X-Hermes-Profile': 'caller'})
                            assert response.status_code == 200
                            assert response.json()['result'] == [{'channel_id': owned, 'project_id': 'owned'}]
    asyncio.run(scenario())
