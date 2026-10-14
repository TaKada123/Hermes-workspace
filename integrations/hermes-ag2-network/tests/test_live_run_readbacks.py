"""Public Runs/Sessions evidence accepts actual deferred-tool calls, not descriptions."""
import asyncio
import json

import httpx

from hermes_ag2_network.live_runtime import Readbacks


def test_readback_identifies_deferred_invocations_without_exporting_arguments():
    async def scenario():
        def respond(request):
            if '/v1/runs/' in request.url.path:
                body = {'status': 'completed', 'session_id': 'fresh-session', 'output': 'done'}
            elif request.url.path.endswith('/messages'):
                body = {'object': 'list', 'session_id': 'fresh-session', 'data': [
                    {'role': 'user', 'content': 'fresh input'},
                    {'role': 'assistant', 'tool_calls': [{'id': 'describe', 'function': {
                        'name': 'tool_describe', 'arguments': json.dumps({'names': ['not_invoked']})}}]},
                    {'role': 'tool', 'tool_call_id': 'describe', 'content': 'schema'},
                    {'role': 'assistant', 'tool_calls': [{'id': 'invoke', 'function': {
                        'name': 'tool_call', 'arguments': json.dumps({'calls': [
                            {'name': 'agent_network_ask', 'arguments': {'text': 'private-argument'}},
                            {'name': 'memory', 'arguments': {'content': 'private-canary'}},
                        ]})}}]},
                    {'role': 'tool', 'tool_call_id': 'invoke', 'content': 'private result'},
                    {'role': 'assistant', 'content': 'done'},
                ], 'pagination': {'has_more': False, 'limit': 200, 'offset': 0, 'returned': 6}}
            else:
                body = {'session': {'api_call_count': 2}}
            return httpx.Response(200, json=body)
        readbacks = Readbacks('http://runtime.fixture', {'coding': 'fixture-secret'})
        await readbacks.http.aclose()
        readbacks.http = httpx.AsyncClient(base_url='http://runtime.fixture', transport=httpx.MockTransport(respond))
        try:
            record = await readbacks.run('coding', 'fresh-run', 'fresh-session', input_text='fresh input')
            assert record['tool_names'] == ['tool_describe', 'tool_call', 'agent_network_ask', 'memory']
            assert 'not_invoked' not in str(record)
            assert 'private-argument' not in str(record)
            assert 'private-canary' not in str(record)
        finally:
            await readbacks.http.aclose()
    asyncio.run(scenario())
