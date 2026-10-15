"""Full executor contract with real AG2/processes and a CONTROLLED HTTP owner runtime.

Not live Hermes/model evidence. Each fake model action is explicit test data at the public
HTTP boundary; production executor has no injectable mock or simulated-success mode.
"""
import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from threading import Thread
from urllib.request import Request, urlopen
from urllib.parse import parse_qs, urlsplit
import uuid

from hermes_ag2_network.discovery import enroll_profile
from hermes_ag2_network.live_scenario import LiveScenario


def test_real_process_executor_verifies_controlled_steps_and_run_discovery(tmp_path):
    home = tmp_path / 'home'
    ports = {}
    import socket
    for index, profile in enumerate(('coding', 'architect')):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            ports[profile] = sock.getsockname()[1]
        root = home / 'profiles' / profile
        (root / 'plugins' / 'agent-network').mkdir(parents=True)
        (root / 'plugins' / 'agent-network' / '__init__.py').write_text('# controlled installation marker\n')
        (root / 'memories').mkdir()
        (root / 'memories' / 'MEMORY.md').write_text('original controlled private entry\n')
        (root / 'config.yaml').write_text(f'plugins:\n  enabled: [agent-network]\n  entries:\n    agent-network:\n      settings:\n        bridge_url: http://127.0.0.1:{ports[profile]}\n')
        (root / '.env').write_text(f'AGENT_NETWORK_TOOLS_KEY={profile}-tools\n')
        (root / '.env').chmod(0o600)
        enroll_profile(profile, home)
    sessions, runs, idempotency = {}, {}, {}
    errors = []

    def capture(pattern, text):
        found = re.search(pattern, text)
        assert found is not None, 'controlled prompt did not match the expected public contract'
        return found[1]

    class Handler(BaseHTTPRequestHandler):
        def respond(self, body, status=200):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_GET(self):
            profile = self.path.split('/')[2]
            path = self.path.split('?', 1)[0].split('/', 3)[3]
            assert self.headers.get('Authorization') == f'Bearer {profile}-api'
            if path == 'v1/capabilities':
                return self.respond({'features': {'run_submission': True, 'run_status': True,
                                                   'run_list_by_session': True,
                                                   'runs_idempotency': {'durable': True}}})
            if path == 'v1/runs':
                query = parse_qs(urlsplit(self.path).query)
                session_id = query['session_id'][0]
                limit = int(query.get('limit', ['100'])[0])
                offset = int(query.get('offset', ['0'])[0])
                rows = [{'run_id': run_id, 'session_id': row['session_id'], 'status': row['status'],
                         'created_at': row['created_at'], 'updated_at': row.get('updated_at')}
                        for run_id, row in runs.items()
                        if row['session_id'] == session_id and run_id in idempotency.values()]
                page = rows[offset:offset + limit]
                return self.respond({'object': 'list', 'session_id': session_id, 'data': page,
                    'pagination': {'limit': limit, 'offset': offset, 'returned': len(page),
                                   'has_more': offset + len(page) < len(rows)}})
            if path == 'api/sessions':
                query = parse_qs(urlsplit(self.path).query)
                title = query.get('title', [''])[0]
                data = [row for (p, _), row in sessions.items() if p == profile and row.get('title') == title]
                return self.respond({'object': 'list', 'data': data, 'limit': 100, 'offset': 0, 'has_more': False})
            if path.startswith('v1/runs/'):
                return self.respond(runs[path.rsplit('/', 1)[1]])
            session_id = path.split('/')[2]
            key = (profile, session_id)
            if path.endswith('/messages'):
                query = parse_qs(urlsplit(self.path).query)
                limit = int(query['limit'][0])
                offset = int(query.get('offset', ['0'])[0])
                rows = sessions[key]['messages'][offset:offset + limit]
                return self.respond({'session_id': session_id, 'messages': rows,
                    'pagination': {'limit': limit, 'offset': offset, 'returned': len(rows)}})
            return self.respond({'session': {k: v for k, v in sessions[key].items() if k != 'messages'}})

        def do_POST(self):
            profile = self.path.split('/')[2]
            path = self.path.split('/', 3)[3]
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert self.headers.get('Authorization') == f'Bearer {profile}-api'
            if path == 'api/sessions':
                key = (profile, body['id'])
                if key in sessions:
                    return self.respond({'error': {'code': 'session_exists'}}, 409)
                sessions[key] = {'id': body['id'], 'title': body['title'], 'messages': [], 'message_count': 0, 'tool_call_count': 0,
                                 'api_call_count': 0, 'input_tokens': 0, 'output_tokens': 0}
                return self.respond({'session': {'id': body['id']}}, 201)
            assert path == 'v1/runs'
            identity = self.headers['Idempotency-Key']
            if identity in idempotency:
                return self.respond({'run_id': idempotency[identity]})
            run_id = uuid.uuid4().hex
            idempotency[identity] = run_id
            runs[run_id] = {'run_id': run_id, 'session_id': body['session_id'], 'status': 'queued', 'created_at': time.time()}
            context_id = self.headers['X-Hermes-Run-Context-Id']

            def work():
                try:
                    text = body['input']
                    row = sessions[(profile, body['session_id'])]
                    row['messages'].append({'role': 'user', 'content': text, 'timestamp': time.time()})
                    row['api_call_count'] += 1
                    output = 'controlled direct reply'
                    if 'memory tool' in text:
                        marker = capture(r'"(acceptance-[^"]+)"', text)
                        path = home / 'profiles' / profile / 'memories' / 'MEMORY.md'
                        if 'add exactly' in text:
                            path.write_text(path.read_text() + marker + '\n')
                        else:
                            path.write_text(path.read_text().replace(marker + '\n', ''))
                        row['messages'].append({'role': 'assistant', 'tool_calls': [{'id': run_id + '-tool',
                            'function': {'name': 'memory', 'arguments': '{}'}}]})
                        row['messages'].append({'role': 'tool', 'tool_call_id': run_id + '-tool', 'content': 'success'})
                    elif profile == 'coding':
                        project = capture(r'Project (acceptance-[^. ]+)', text)
                        operation = capture(r'operation_id (acceptance-[^. ]+)', text)
                        marker = project + '-result'

                        def tool(path, payload):
                            request = Request(f'http://127.0.0.1:{ports[profile]}/v1/{path}',
                                data=json.dumps(payload).encode(), headers={'Authorization': f'Bearer {profile}-tools',
                                'X-Hermes-Profile': profile, 'X-Hermes-Run-Context-Id': context_id, 'Content-Type': 'application/json'})
                            with urlopen(request, timeout=20) as response:
                                return json.load(response)['result']
                        channel = tool('open', {'peer': 'architect', 'project_id': project})['channel_id']
                        reply = tool('ask', {'channel_id': channel, 'operation_id': operation,
                                            'text': f'controlled advice request, marker {marker}', 'timeout_seconds': 20})
                        assert reply['kind'] == 'reply'
                        row['messages'].append({'role': 'assistant', 'tool_calls': [{'id': run_id + '-tool',
                            'function': {'name': 'agent_network_ask', 'arguments': json.dumps({'operation_id': operation})}}]})
                        row['messages'].append({'role': 'tool', 'tool_call_id': run_id + '-tool', 'content': json.dumps(reply)})
                        output = 'controlled Coding continuation ' + reply['text']
                    else:
                        marker = capture(r'marker (acceptance-[^ ]+)', text)
                        output = 'controlled Architect advice ' + marker
                    row['messages'].append({'role': 'assistant', 'content': output, 'timestamp': time.time()})
                    row['message_count'] = len(row['messages'])
                    row['tool_call_count'] = sum(bool(m.get('tool_calls')) for m in row['messages'])
                    runs[run_id].update(status='completed', output=output, updated_at=time.time())
                except Exception as exc:
                    errors.append(type(exc).__name__)
                    runs[run_id].update(status='failed')
            self.respond({'run_id': run_id})
            Thread(target=work, daemon=True).start()

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        state = tmp_path / 'network'
        receipt = asyncio.run(LiveScenario(f'http://127.0.0.1:{server.server_port}',
            {'coding': 'coding-api', 'architect': 'architect-api'}, home=home,
            state_dir=state, idle_seconds=2).run())
        assert not errors, errors
        assert receipt['live_scenario_completed'] is True
        assert all(receipt['steps'][str(i)]['status'] == 'passed' for i in range(1, 11)), receipt['blockers']
        assert receipt['blockers'] == []
        assert receipt['checks']['idle']['complete'] is True
        assert receipt['checks']['idle']['unchanged'] is True
        assert receipt['checks']['two_project_parallel']['distinct_channels'] is True
        assert all(row['original_bytes_restored'] for row in receipt['cleanup']['memory'].values())
        assert all(row['returncode'] is not None for row in receipt['cleanup']['processes'])
        assert not list(state.glob('*.key'))
        assert not (state / 'identities.json').exists()
        assert len(set(receipt['restart']['new_pids'])) == 3
        assert all((home / 'profiles' / p / 'memories' / 'MEMORY.md').read_text() == 'original controlled private entry\n'
                   for p in ('coding', 'architect'))
        # Refusing an existing state directory must never delete pre-existing credentials.
        sentinel = state / 'coding-api.key'
        sentinel.write_text('do-not-touch')
        blocked = asyncio.run(LiveScenario(f'http://127.0.0.1:{server.server_port}',
            {'coding': 'coding-api', 'architect': 'architect-api'}, home=home,
            state_dir=state, idle_seconds=2).run())
        assert blocked['live_scenario_completed'] is False
        assert blocked['mutations'] == []
        assert sentinel.read_text() == 'do-not-touch'
        # An unusable receipt target is detected before any Sessions/Runs mutation.
        bad_parent = tmp_path / 'not-a-directory'
        bad_parent.write_text('keep')
        keys = {}
        for p in ('coding', 'architect'):
            keys[p] = tmp_path / (p + '-api.key')
            keys[p].write_text(p + '-api')
            keys[p].chmod(0o600)
        unused = tmp_path / 'unused-network'
        count = len(runs)
        result = subprocess.run([sys.executable, '-m', 'hermes_ag2_network.live_acceptance',
            '--api-url', f'http://127.0.0.1:{server.server_port}', '--execute', '--home', str(home),
            '--state-dir', str(unused), '--receipt', str(bad_parent / 'receipt.json'),
            '--coding-api-key-file', str(keys['coding']), '--architect-api-key-file', str(keys['architect'])],
            env={**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1] / 'src')},
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 2 and '--receipt' in result.stderr
        assert not unused.exists() and len(runs) == count
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
