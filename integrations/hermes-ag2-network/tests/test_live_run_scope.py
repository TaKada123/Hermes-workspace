"""Run-specific evidence and nested public pagination, never session-wide tool credit."""
import asyncio
import json

import httpx
import pytest

from hermes_ag2_network.live_runtime import AcceptanceBlocked, Readbacks


@pytest.mark.parametrize('fault', ['old_tool', 'missing_result', 'truncated', 'good', 'repeated_input'])
def test_tools_belong_to_requested_turn_and_have_correlated_results(fault):
    async def scenario():
        rows: list[dict] = [
            {'role': 'user', 'content': 'old input'},
            {'role': 'assistant', 'tool_calls': [{'id': 'old', 'function': {'name': 'memory', 'arguments': '{}'}}]},
            {'role': 'tool', 'tool_call_id': 'old', 'content': 'private old result'},
            {'role': 'assistant', 'content': 'old output'},
            {'role': 'user', 'content': 'current unique input'},
        ]
        if fault != 'old_tool':
            rows.append({'role': 'assistant', 'tool_calls': [{'id': 'new', 'function': {
                'name': 'tool_call', 'arguments': json.dumps({'calls': [{'name': 'agent_network_ask',
                    'arguments': {'operation_id': 'op', 'text': 'private'}}]})}}]})
            if fault != 'missing_result':
                rows.append({'role': 'tool', 'tool_call_id': 'new', 'content': '{"ok":true}'})
        rows.append({'role': 'assistant', 'content': 'current output'})
        if fault == 'repeated_input':
            rows[0].update(content='current unique input', timestamp=1)
            rows[4]['timestamp'] = 12
            rows[-1]['timestamp'] = 15
        offsets = []
        def respond(request):
            if '/v1/runs/' in request.url.path:
                body: dict = {'status': 'completed', 'session_id': 's', 'output': 'current output'}
                if fault == 'repeated_input':
                    body.update(created_at=10, updated_at=20)
            elif request.url.path.endswith('/messages'):
                offset = int(request.url.params.get('offset', 0))
                offsets.append(offset)
                # A real nested pagination contract may report more on a short page.
                page = rows[offset:offset + 4]
                body = {'session_id': 's', 'messages': page, 'pagination': {
                    'offset': offset, 'limit': 200, 'returned': len(page),
                    'has_more': offset + len(page) < len(rows)}}
                if fault == 'truncated' and offset:
                    body['messages'] = []
                    body['pagination'].update(returned=0, has_more=True)
            else:
                body = {'session': {'api_call_count': 2}}
            return httpx.Response(200, json=body)
        owner = Readbacks('http://fixture', {'coding': 'test'})
        await owner.http.aclose()
        owner.http = httpx.AsyncClient(base_url='http://fixture', transport=httpx.MockTransport(respond))
        try:
            if fault in {'missing_result', 'truncated'}:
                with pytest.raises(AcceptanceBlocked):
                    await owner.run('coding', 'r', 's', input_text='current unique input')
            else:
                record = await owner.run('coding', 'r', 's', input_text='current unique input')
                assert record['tool_names'] == ([] if fault == 'old_tool' else ['tool_call', 'agent_network_ask'])
                assert offsets == [0, 4]
                assert 'private' not in json.dumps(record)
        finally:
            await owner.http.aclose()
    asyncio.run(scenario())
