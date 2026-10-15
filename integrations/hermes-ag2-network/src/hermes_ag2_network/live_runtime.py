"""Private acceptance resources. No gateway restart, profile settings write or raw logs."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import subprocess
import sys

import httpx
import yaml

from .cli import protected_file


class AcceptanceBlocked(RuntimeError):
    """Only safe, authored prerequisites belong in this exception."""


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def source_identity() -> dict:
    """Tie installed/source execution to content, not a misleading dirty HEAD claim."""
    package = Path(__file__).parent
    files = sorted(package.glob('*.py'))
    source_hash = digest(b''.join(p.name.encode() + b'\0' + p.read_bytes() + b'\0' for p in files))
    result = {'package_source_sha256': source_hash, 'git_sha': None, 'dirty': None}
    try:
        result['git_sha'] = subprocess.check_output(['git', '-C', str(package), 'rev-parse', 'HEAD'],
                                                    stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
        result['dirty'] = bool(subprocess.check_output(['git', '-C', str(package), 'status', '--porcelain'],
                                                       stderr=subprocess.DEVNULL, text=True, timeout=5).strip())
    except (OSError, subprocess.SubprocessError):
        pass  # An installed wheel need not carry Git metadata; the source hash remains authoritative.
    return result


def ledger_metadata(state: Path) -> dict:
    """Read only invocation-owned operational IDs; never serialize payload/results/private text."""
    result = {'sessions': [], 'held': []}
    for profile in ('coding', 'architect'):
        path = state / f'{profile}.sqlite'
        if not path.exists():
            continue
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            result['sessions'].extend(dict(row) for row in db.execute(
                'SELECT profile,project_id,channel_id,origin_id,current_id FROM hermes_sessions'))
            for row in db.execute('SELECT profile,request FROM held_execution'):
                request = json.loads(row['request'])
                context = request.get('_task_context') or {}
                result['held'].append({**{k: request.get(k) for k in ('profile', 'project_id', 'channel_id',
                    'operation_id', 'session_origin_id', 'session_current_id')},
                    'run_id': context.get('run_id'), 'network_context_id': context.get('network_context_id')})
    return result


def private_write(path: Path, text: str) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        output.write(text)


def profile_resources(home: Path, profile: str) -> dict:
    root = home / 'profiles' / profile
    config = root / 'config.yaml'
    plugin = root / 'plugins' / 'agent-network' / '__init__.py'
    if not config.is_file() or not plugin.is_file():
        raise AcceptanceBlocked(f'{profile}: existing configured agent-network plugin required; no automatic installation')
    # Read only the plugin's existing secret, never copy the profile environment.
    env = protected_file(str(root / '.env'))
    match = re.search(r'^AGENT_NETWORK_TOOLS_KEY=(.+)$', env, re.MULTILINE)
    if match is None:
        raise AcceptanceBlocked(f'{profile}: existing AGENT_NETWORK_TOOLS_KEY required')
    token = match.group(1).strip().strip('\"\'')
    if not token or any(not 33 <= ord(c) <= 126 for c in token):
        raise AcceptanceBlocked(f'{profile}: invalid existing tool credential')
    try:
        settings = yaml.safe_load(config.read_text())
    except yaml.YAMLError:
        raise AcceptanceBlocked(f'{profile}: invalid YAML configuration; owner must repair syntax, no automatic repair') from None
    if not isinstance(settings, dict):
        raise AcceptanceBlocked(f'{profile}: invalid profile configuration; no automatic repair')
    plugins = settings.get('plugins', {})
    memory = settings.get('memory', {})
    node = plugins
    for key in ('entries', 'agent-network', 'settings'):
        if not isinstance(node, dict):
            raise AcceptanceBlocked(f'{profile}: invalid plugin configuration; owner must repair structures, no automatic repair')
        node = node.get(key, {})
    if (not isinstance(node, dict) or not isinstance(memory, dict)
            or not isinstance(plugins.get('enabled', []), list)):
        raise AcceptanceBlocked(f'{profile}: invalid profile configuration; owner must repair structures, no automatic repair')
    url = node.get('bridge_url', '')
    if ('agent-network' not in plugins.get('enabled', []) or
            not isinstance(url, str) or not re.fullmatch(r'http://127\.0\.0\.1:[0-9]+', url)):
        raise AcceptanceBlocked(f'{profile}: explicit existing loopback bridge_url required')
    port = int(url.rsplit(':', 1)[1])
    if not 1 <= port <= 65535:
        raise AcceptanceBlocked(f'{profile}: invalid existing bridge port')
    return {'root': root, 'config': config, 'config_sha256': digest(config.read_bytes()),
            'memory_backend': settings.get('memory', {}).get('backend', 'file'),
            'token': token, 'url': url, 'port': port}


class TemporaryNetwork:
    """Separate native Hub/Bridge processes; stop only PIDs created by this owner."""

    def __init__(self, state: Path, home: Path, api_url: str, credentials: dict, profiles: dict, projects: list[str]):
        self.state, self.home, self.api_url = state, home, api_url
        self.credentials, self.profiles, self.projects = credentials, profiles, projects
        self.processes = []
        self.pids = []
        self.owns_state = False
        self.keys = {name: secrets.token_urlsafe(32) for name in ('acceptance', 'coding', 'architect')}
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.hub_port = sock.getsockname()[1]
        self.url = f'ws://127.0.0.1:{self.hub_port}'

    def prepare(self):
        for name, resource in self.profiles.items():
            with socket.socket() as sock:
                try:
                    sock.bind(('127.0.0.1', resource['port']))
                except OSError:
                    raise AcceptanceBlocked(f'{name}: existing bridge port occupied; do not stop an unrelated listener') from None
        self.state.mkdir(mode=0o700, parents=False, exist_ok=False)
        self.owns_state = True
        private_write(self.state / 'identities.json', json.dumps(self.keys))
        for name in self.profiles:
            private_write(self.state / f'{name}-hub.key', self.keys[name])
            private_write(self.state / f'{name}-tools.key', self.profiles[name]['token'])
            private_write(self.state / f'{name}-api.key', self.credentials[name])

    async def launch(self, *args):
        # No inherited provider credentials or model override. API resolves the owning runtime.
        env = {'PATH': os.environ.get('PATH', ''), 'HOME': str(Path.home()),
               'HERMES_HOME': str(self.home), 'PYTHONPATH': str(Path(__file__).parents[1])}
        proc = await asyncio.create_subprocess_exec(sys.executable, '-m', 'hermes_ag2_network.cli', *args,
                                                    env=env, stdout=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.DEVNULL)
        self.processes.append(proc)
        self.pids.append(proc.pid)
        return proc

    async def start(self):
        hub = await self.launch('hub', '--store', str(self.state / 'hub'), '--keys-file',
                                str(self.state / 'identities.json'), '--port', str(self.hub_port))
        async with asyncio.timeout(15):
            while True:
                if hub.returncode is not None:
                    raise AcceptanceBlocked('temporary Hub failed startup; no live runtime changes made')
                try:
                    reader, writer = await asyncio.open_connection('127.0.0.1', self.hub_port)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(.1)
        for name, resource in self.profiles.items():
            args = ['bridge', '--hub-url', self.url, '--name', name, '--ledger', str(self.state / f'{name}.sqlite'),
                    '--control-db', str(self.state / 'admission.sqlite'), '--hub-key-file', str(self.state / f'{name}-hub.key'),
                    '--api-url', self.api_url, '--api-key-file', str(self.state / f'{name}-api.key'),
                    '--tool-api-key-file', str(self.state / f'{name}-tools.key'), '--tool-api-port', str(resource['port'])]
            for project in self.projects:
                for peer in ('architect' if name == 'coding' else 'coding', 'acceptance'):
                    args.extend(['--project-peer', f'{project}={peer}'])
            proc = await self.launch(*args)
            async with httpx.AsyncClient(trust_env=False, timeout=2) as client:
                async with asyncio.timeout(15):
                    while True:
                        if proc.returncode is not None:
                            raise AcceptanceBlocked(f'{name}: temporary Bridge startup failed; explicit existing enrollment required')
                        try:
                            response = await client.get(resource['url'] + '/v1/peers', headers=self.headers(name))
                            if response.status_code == 200 and response.json().get('profile') == name:
                                break
                        except (httpx.HTTPError, ValueError):
                            pass
                        await asyncio.sleep(.1)

    def headers(self, name: str) -> dict:
        return {'Authorization': 'Bearer ' + self.profiles[name]['token'], 'X-Hermes-Profile': name}

    async def stop(self):
        stopped = []
        for proc in reversed(self.processes):
            if proc.returncode is None:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass  # Owned process exited between returncode check and signal.
                try:
                    await asyncio.wait_for(proc.wait(), 15)
                except TimeoutError:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass  # The child can exit concurrently with escalation.
                    try:
                        await asyncio.wait_for(proc.wait(), 5)
                    except TimeoutError:
                        # Keep an unreaped returncode in the receipt, but attempt every
                        # other owned child before deferring to the operator.
                        stopped.append({'pid': proc.pid, 'returncode': None})
                        continue
            stopped.append({'pid': proc.pid, 'returncode': proc.returncode})
        self.processes = [proc for proc in self.processes if proc.returncode is None]
        return stopped

    def remove_credentials(self):
        # Exact list of this invocation's files; retained WAL/ledgers are never deleted.
        for filename in ['identities.json'] + [f'{p}-{kind}.key' for p in self.profiles for kind in ('hub', 'tools', 'api')]:
            (self.state / filename).unlink(missing_ok=True)


class Readbacks:
    def __init__(self, url: str, credentials: dict):
        self.http = httpx.AsyncClient(base_url=url, trust_env=False, timeout=15, follow_redirects=False)
        self.credentials = credentials

    async def get(self, profile: str, path: str, **params):
        response = await self.http.get(f'/p/{profile}/{path}', params=params,
                                       headers={'Authorization': 'Bearer ' + self.credentials[profile]})
        response.raise_for_status()
        return response.json()

    async def messages(self, profile: str, session_id: str) -> list[dict]:
        rows = []
        for _ in range(100):
            body = await self.get(profile, f'api/sessions/{session_id}/messages',
                                  limit=200, offset=len(rows), order='oldest')
            page = body.get('messages', body.get('data'))
            pagination = body.get('pagination')
            if (not isinstance(page, list) or not all(isinstance(row, dict) for row in page)
                    or not isinstance(pagination, dict) or body.get('session_id') != session_id
                    or pagination.get('offset') != len(rows) or pagination.get('returned') != len(page)
                    or pagination.get('limit') != 200):
                raise AcceptanceBlocked(f'{profile}: incomplete/malformed public message pagination')
            more = pagination.get('has_more', len(page) == 200)
            if not isinstance(more, bool) or (more and not page):
                raise AcceptanceBlocked(f'{profile}: non-progressing public message pagination')
            rows.extend(page)
            if not more:
                return rows
        raise AcceptanceBlocked(f'{profile}: message pagination bound exceeded; no truncated evidence accepted')

    async def run(self, profile: str, run_id: str, session_id: str, origin_id: str = '', *, input_text: str = '') -> dict:
        body = await self.get(profile, f'v1/runs/{run_id}')
        if (body.get('status') != 'completed' or body.get('partial') or body.get('interrupted')
                or not body.get('session_id')):
            raise AcceptanceBlocked(f'{profile}: Run readback not complete/correlated')
        if body['session_id'] != session_id:
            tip = await self.get(profile, f'api/sessions/{body["session_id"]}/messages', limit=0)
            if tip.get('session_id') != session_id:
                raise AcceptanceBlocked(f'{profile}: Run and canonical session tip do not correlate')
        session = await self.get(profile, f'api/sessions/{session_id}')
        value = session.get('session', {})
        from .live_evidence import turn_tools
        rows = await self.messages(profile, session_id)
        tools, invocations = turn_tools(rows, input_text, body.get('output'), body.get('created_at'), body.get('updated_at'))
        counters = {key: value[key] for key in ('message_count', 'tool_call_count', 'api_call_count',
                    'input_tokens', 'output_tokens') if key in value}
        return {'profile': profile, 'run_id': run_id, 'session_id': session_id,
                'origin_session_id': origin_id or value.get('_lineage_root_id') or session_id,
                'status': body['status'], 'tool_names': tools, 'tool_invocations': invocations,
                'input_sha256': digest(input_text), 'counters': counters}

    async def activity(self, sessions: dict[str, set[str]], channels: dict[str, set[str]], runs: dict[str, set[str]]) -> dict:
        discovered = {p: set(ids) for p, ids in sessions.items()}
        for profile, ids in channels.items():
            for channel in sorted(ids):
                offset = 0
                for _ in range(100):
                    body = await self.get(profile, 'api/sessions', title='AG2 ' + channel[:12],
                                          include_children=True, limit=100, offset=offset)
                    page = body.get('data')
                    if (not isinstance(page, list) or body.get('offset') != offset
                            or body.get('limit') != 100 or not isinstance(body.get('has_more'), bool)
                            or not all(isinstance(r, dict) and isinstance(r.get('id'), str) for r in page)):
                        raise AcceptanceBlocked(f'{profile}: public acceptance-session discovery unavailable/incomplete')
                    discovered.setdefault(profile, set()).update(row['id'] for row in page)
                    if not body['has_more']:
                        break
                    if not page:
                        raise AcceptanceBlocked(f'{profile}: non-progressing acceptance-session discovery')
                    offset += 100
                else:
                    raise AcceptanceBlocked(f'{profile}: acceptance-session discovery bound exceeded')

        statuses = {}
        for profile, ids in discovered.items():
            for session_id in sorted(ids):
                offset = 0
                for _ in range(100):
                    body = await self.get(profile, 'v1/runs', session_id=session_id, limit=100, offset=offset)
                    page = body.get('data')
                    pagination = body.get('pagination')
                    if (body.get('object') != 'list' or body.get('session_id') != session_id
                            or not isinstance(page, list) or not isinstance(pagination, dict)
                            or pagination.get('limit') != 100 or pagination.get('offset') != offset
                            or pagination.get('returned') != len(page)
                            or not isinstance(pagination.get('has_more'), bool)
                            or not all(isinstance(row, dict) and isinstance(row.get('run_id'), str)
                                       and row.get('session_id') == session_id
                                       and isinstance(row.get('status'), str) for row in page)):
                        raise AcceptanceBlocked(f'{profile}: authenticated session Run discovery unavailable/incomplete')
                    for row in page:
                        statuses[f'{profile}:{row["run_id"]}'] = {
                            'status': row['status'], 'session_id': row['session_id']}
                    if not pagination['has_more']:
                        break
                    if not page:
                        raise AcceptanceBlocked(f'{profile}: non-progressing session Run discovery')
                    offset += len(page)
                else:
                    raise AcceptanceBlocked(f'{profile}: session Run discovery bound exceeded')

        # Keep exact-ID reads for submitted Runs as a second public readback, including any
        # continuation whose current session ID rotated between submit and observation.
        for profile, run_ids in runs.items():
            for run_id in sorted(run_ids):
                body = await self.get(profile, f'v1/runs/{run_id}')
                if not isinstance(body.get('status'), str):
                    raise AcceptanceBlocked(f'{profile}: known Run status unavailable')
                statuses[f'{profile}:{run_id}'] = {
                    'status': body['status'], 'session_id': body.get('session_id')}
        return {'sessions': await self.snapshot(discovered), 'runs': statuses,
                'run_discovery_available': True}

    async def snapshot(self, sessions: dict[str, set[str]]) -> dict:
        result = {}
        for profile, ids in sessions.items():
            for session_id in sorted(ids):
                body = await self.get(profile, f'api/sessions/{session_id}')
                row = body.get('session', {})
                if not isinstance(row.get('api_call_count'), int):
                    raise AcceptanceBlocked(f'{profile}: public api_call_count unavailable; cannot prove idle model activity')
                result[f'{profile}:{session_id}'] = {k: row.get(k) for k in
                    ('api_call_count', 'message_count', 'tool_call_count', 'input_tokens', 'output_tokens')}
        return result
