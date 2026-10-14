"""Idle evidence discovers public acceptance continuations; absent Run discovery blocks success."""
import asyncio

import httpx

from hermes_ag2_network.live_runtime import Readbacks


def test_idle_discovers_new_acceptance_session_but_does_not_claim_run_catalog():
    async def scenario():
        calls = []
        def respond(request):
            calls.append(request.url)
            if request.url.path.endswith('/api/sessions'):
                assert request.url.params['title'] == 'AG2 channel12345'
                return httpx.Response(200, json={'object': 'list', 'data': [
                    {'id': 'known'}, {'id': 'new-tip'}], 'limit': 100, 'offset': 0, 'has_more': False})
            return httpx.Response(200, json={'session': {'api_call_count': 0, 'message_count': 0}})
        owner = Readbacks('http://fixture', {'coding': 'test'})
        await owner.http.aclose()
        owner.http = httpx.AsyncClient(base_url='http://fixture', transport=httpx.MockTransport(respond))
        try:
            found = await owner.activity({'coding': {'known'}}, {'coding': {'channel12345abcd'}}, {})
            assert set(found['sessions']) == {'coding:known', 'coding:new-tip'}
            assert found['run_discovery_available'] is False
            assert len(calls) == 3
        finally:
            await owner.http.aclose()
    asyncio.run(scenario())
