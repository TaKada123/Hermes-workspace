"""Opt-in live Coding/Architect acceptance using native AG2 and authenticated Hermes Runs.

Controlled tests exercise guards/evidence, never substitute a live model response.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import time
from typing import Any
import uuid

import httpx

from .executor import HermesHTTPExecutor
from .discovery import enrolled_profiles
from .network import Network
from .types import (ExecutionBudget, ExecutionRequest, ExecutionTaskContext, ExecutionUncertain,
                    network_execution_context_id)
from .live_runtime import AcceptanceBlocked, Readbacks, TemporaryNetwork, digest, ledger_metadata, profile_resources


STEPS = {
    '1': 'Coding initiates Architect consultation', '2': 'Architect receives native AG2 request',
    '3': 'Architect replies through owning Hermes Run', '4': 'Coding receives reply and continues',
    '5': 'Coding consults Architect again', '6': 'Both channel sessions continue',
    '7': 'Each owning runtime writes independent private memory', '8': 'Temporary Hub/Bridge processes restart',
    '9': 'History/identities/sessions continue after restart', '10': 'No duplicate, canary leakage or idle activity',
}


def verify_exchange(history: list[dict], operation_id: str) -> dict:
    requests = [m for m in history if m.get('kind') == 'request' and m.get('operation_id') == operation_id]
    replies = [m for m in history if m.get('kind') == 'reply' and m.get('operation_id') == operation_id]
    if (len(requests) != 1 or len(replies) != 1 or replies[0].get('causation_id') != requests[0].get('envelope_id')
            or not replies[0].get('session_id') or not replies[0].get('run_id')):
        raise ValueError('one correlated request and terminal Hermes reply required')
    return replies[0]


def public_history(rows: list[dict]) -> list[dict]:
    return [{**{k: row.get(k) for k in ('envelope_id', 'sender_id', 'kind', 'operation_id',
                'causation_id', 'session_id', 'run_id')}, 'text_sha256': digest(row.get('text', ''))} for row in rows]


class LiveScenario:
    def __init__(self, api_url: str, credentials: dict, *, home: Path, state_dir: Path, idle_seconds: float = 10):
        if idle_seconds < 2 or idle_seconds > 300:
            raise ValueError('idle observation must be between 2 and 300 seconds')
        self.api_url, self.credentials, self.home, self.state = api_url, credentials, home, state_dir
        self.idle_seconds = idle_seconds
        self.tag = 'acceptance-' + uuid.uuid4().hex
        self.projects = [self.tag + '-alpha', self.tag + '-beta']
        self.receipt: dict[str, Any] = {'phase': 'live', 'ready': True, 'live_scenario_completed': False,
                        'scenario_id': self.tag, 'projects': self.projects, 'steps': {
                            k: {'criterion': value, 'status': 'not_run'} for k, value in STEPS.items()},
                        'blockers': [], 'mutations': [], 'runs': [], 'channels': {}, 'checks': {}, 'cleanup': {}}
        self.sessions = {'coding': set(), 'architect': set()}
        self.resources = {}
        self.network = None
        self.readbacks = Readbacks(api_url, credentials)
        self.memories = {}
        self._cancelled = False

    def passed(self, *steps):
        for key in steps:
            self.receipt['steps'][key]['status'] = 'passed'

    async def tool(self, profile: str, method: str, path: str, **kwargs):
        assert self.network is not None
        async with httpx.AsyncClient(trust_env=False, timeout=310) as client:
            response = await client.request(method, self.resources[profile]['url'] + path,
                                            headers=self.network.headers(profile), **kwargs)
            response.raise_for_status()
            body = response.json()
            if body.get('profile') != profile or body.get('ok') is not True:
                raise AcceptanceBlocked(f'{profile}: ToolAPI receipt binding mismatch')
            return body['result']

    async def native_history(self, channel: str) -> list[dict]:
        return await self.tool('coding', 'GET', '/v1/history', params={'channel_id': channel})

    async def record_run(self, profile: str, reply: dict, input_text: str):
        origin = ''
        if self.network is not None and self.network.owns_state:
            mappings = ledger_metadata(self.state)['sessions']
            origin = next((r['origin_id'] for r in mappings if r['profile'] == profile
                           and r['current_id'] == reply['session_id']), '')
        record = await self.readbacks.run(profile, reply['run_id'], reply['session_id'], origin, input_text=input_text)
        self.sessions[profile].add(reply['session_id'])
        self.receipt['runs'].append(record)
        self.receipt['mutations'].append({'profile': profile, 'run_id': reply['run_id'],
                                          'session_id': reply['session_id']})
        return record

    async def consult(self, caller: Network, outer: str, project: str, turn: str) -> tuple[str, dict]:
        operation = project + '-' + turn
        nested_operation = operation + '-architect'
        marker = project + '-result'
        prompt = (
            f'Authorized acceptance only. Project {project}. Use agent_network_open with peer architect, project_id {project}. '
            f'Use agent_network_ask on that channel with operation_id {nested_operation}. '
            f'Ask: "For project {project}, propose one concrete durable request/reply design improvement. '
            f'Include marker {marker} in your answer. Reply directly, do not consult another agent, '
            f'do not expose or edit private memory, files, configuration, skills or existing conversations." '
            f'This is consultation {turn}: reuse the existing channel and discussion, do not create another project. '
            f'After the genuine tool answer, continue your own work: state a concrete implementation decision based on the advice '
            f'and include marker {marker}. Do not claim a consultation if tools fail. No external services or model changes.')
        reply = await caller.ask(outer, prompt, operation_id=operation, timeout=300)
        if reply.kind != 'reply':
            raise AcceptanceBlocked('Coding did not produce a terminal reply; retain admission and inspect owning Run')
        record = await self.record_run('coding', asdict(reply), prompt)
        if not any('agent_network_ask' in name for name in record['tool_names']):
            raise AcceptanceBlocked('Coding Run did not invoke agent_network_ask; model prose is not consultation evidence')
        channel = (await self.tool('coding', 'POST', '/v1/open', json={'peer': 'architect', 'project_id': project}))['channel_id']
        history = await self.native_history(channel)
        try:
            child = verify_exchange(history, nested_operation)
        except ValueError:
            raise AcceptanceBlocked('Architect native WAL lacks exactly one correlated request/reply for the requested operation') from None
        child_input = next(row['text'] for row in history if row.get('kind') == 'request'
                           and row.get('operation_id') == nested_operation)
        await self.record_run('architect', child, child_input)
        if marker not in child.get('text', '') or marker not in reply.text:
            raise AcceptanceBlocked('Coding/Architect outputs lack independent project markers')
        other = next(p for p in self.projects if p != project)
        if other + '-result' in reply.text or any(other + '-result' in m.get('text', '') for m in history):
            raise AcceptanceBlocked('another project marker appeared in this project output/history')
        self.receipt['channels'][project] = {'coding_architect': channel, 'acceptance_coding': outer,
                                             'history': public_history(history)}
        return prompt, child

    async def faults(self):
        assert self.network is not None
        resource = self.resources['coding']
        async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
            cases: list[tuple[str, str, str, dict[str, Any], int]] = [
                ('wrong_token', 'GET', '/v1/peers', {'headers': {'Authorization': 'Bearer invalid', 'X-Hermes-Profile': 'coding'}}, 401),
                ('wrong_profile', 'GET', '/v1/peers', {'headers': {**self.network.headers('coding'), 'X-Hermes-Profile': 'architect'}}, 403),
                ('malformed_input', 'POST', '/v1/open', {'json': {}}, 400),
                ('unauthorized_peer', 'POST', '/v1/open', {'json': {'peer': 'default', 'project_id': self.projects[0]}}, 403),
                ('unauthorized_project', 'POST', '/v1/open', {'json': {'peer': 'architect', 'project_id': 'ungranted'}}, 403),
                ('missing_channel', 'GET', '/v1/history', {'params': {'channel_id': 'missing-acceptance-channel'}}, 404),
            ]
            found = {}
            for name, method, path, kwargs, expected in cases:
                headers = kwargs.pop('headers', self.network.headers('coding'))
                response = await client.request(method, resource['url'] + path, headers=headers, **kwargs)
                found[name] = response.status_code
                if response.status_code != expected:
                    raise AcceptanceBlocked(f'{name}: expected safe HTTP {expected}, got {response.status_code}')
            self.receipt['checks']['errors'] = found

    async def memory_turn(self, profile: str, text: str, operation: str):
        if self._cancelled:
            raise asyncio.CancelledError
        # Send private canaries directly to the freshly-created owning network session,
        # never in an AG2 request/envelope or another profile's input.
        mappings = ledger_metadata(self.state)['sessions']
        mapping = next(r for r in mappings if r['profile'] == profile and r['project_id'] == self.projects[0])
        session, current, channel = mapping['origin_id'], mapping['current_id'], mapping['channel_id']
        context = ExecutionTaskContext(network_execution_context_id(profile, self.projects[0],
            channel, operation), (profile,), ExecutionBudget(time.time() + 300, 1, 0))
        async with HermesHTTPExecutor(self.api_url, profile=profile, token=self.credentials[profile]) as executor:
            try:
                result = await executor(ExecutionRequest(profile, self.projects[0], channel,
                                        operation, text, session, current, _task_context=context))
            except (ExecutionUncertain, asyncio.CancelledError):
                self.memories[profile]['unsettled_run_id'] = context.run_id
                self.receipt['mutations'].append({'profile': profile, 'run_id': context.run_id,
                                                  'session_id': session, 'status': 'unsettled'})
                raise
        record = await self.record_run(profile, {'run_id': result.run_id, 'session_id': result.session_id}, text)
        if not any('memory' in name for name in record['tool_names']):
            raise AcceptanceBlocked(f'{profile}: owning runtime did not invoke a memory tool')

    async def private_memory(self):
        for profile, resource in self.resources.items():
            if resource['memory_backend'] != 'file':
                raise AcceptanceBlocked(f'{profile}: memory backend is not legacy file; preserve it. This live canary verifier does not migrate or inspect a private database')
            path = resource['root'] / 'memories' / 'MEMORY.md'
            if not path.is_file():
                raise AcceptanceBlocked(f'{profile}: legacy memory acceptance file absent; preserve actual backend, no migration')
            self.memories[profile] = {'path': path, 'before': path.read_bytes(),
                                      'marker': self.tag + '-private-' + profile, 'attempted': False}
        for profile, data in self.memories.items():
            data['attempted'] = True
            await self.memory_turn(profile,
                f'Authorized temporary private memory test. Use your owning memory tool to add exactly one entry '
                f'"{data["marker"]}" to your general memory (not USER). Do not transmit it via agent_network, '
                f'do not change backend/config/SOUL/skills/MCP or other entries. Reply "stored" only after the tool succeeds.',
                self.tag + '-memory-add-' + profile)
        ownership = {}
        for profile, data in self.memories.items():
            body = data['path'].read_bytes()
            other = next(v for k, v in self.memories.items() if k != profile)
            ownership[profile] = {'own_canary_present': data['marker'].encode() in body,
                                   'other_canary_absent': other['marker'].encode() not in body,
                                   'original_sha256': digest(data['before']), 'canary_sha256': digest(data['marker'])}
            if not all(ownership[profile][k] for k in ('own_canary_present', 'other_canary_absent')):
                raise AcceptanceBlocked(f'{profile}: independent memory canary readback failed')
        self.receipt['checks']['memory'] = ownership
        self.passed('7')

    async def cleanup_memory(self):
        result = {}
        for profile, data in self.memories.items():
            if not data['attempted']:
                continue
            held = [r for r in ledger_metadata(self.state)['held'] if r['profile'] == profile]
            if held:
                self.receipt['blockers'].append(f'{profile}: network Run held; owning-runtime reconciliation required before private memory cleanup')
                continue
            if 'unsettled_run_id' in data:
                run_id = data['unsettled_run_id']
                status = (await self.readbacks.get(profile, f'v1/runs/{run_id}')).get('status') if run_id else 'unknown'
                if status not in {'completed', 'failed', 'cancelled', 'interrupted'}:
                    self.receipt['blockers'].append(f'{profile}: memory Run unsettled; do not start cleanup until owning-runtime terminal readback')
                    continue
            await self.memory_turn(profile,
                    f'Acceptance cleanup: use your owning memory tool to delete ONLY the exact temporary entry '
                    f'"{data["marker"]}" from general memory, preserving every unrelated entry and settings. '
                    f'No agent_network calls. Reply "removed" after success.', self.tag + '-memory-delete-' + profile)
            result[profile] = {'canary_absent': data['marker'].encode() not in data['path'].read_bytes(),
                               'original_bytes_restored': data['path'].read_bytes() == data['before']}
            if not result[profile]['canary_absent']:
                self.receipt['blockers'].append(f'{profile}: temporary memory entry remains; owning-runtime cleanup required')
            if not result[profile]['original_bytes_restored']:
                self.receipt['blockers'].append(f'{profile}: memory bytes differ after owning-runtime cleanup; verify unrelated entries. No automatic file restoration')
        self.receipt['cleanup']['memory'] = result

    async def verify_histories(self):
        checked = []
        seen = set()
        for project in self.projects:
            for profile in ('coding', 'architect'):
                catalog = await self.tool(profile, 'GET', '/v1/channels', params={'project_id': project})
                if not isinstance(catalog, list):
                    raise AcceptanceBlocked('native channel catalog unavailable; cannot prove all-history privacy')
                for entry in catalog:
                    if not isinstance(entry, dict) or entry.get('project_id') != project or not entry.get('channel_id'):
                        raise AcceptanceBlocked('native channel catalog malformed or outside acceptance project')
                    channel = entry['channel_id']
                    if channel in seen:
                        continue
                    seen.add(channel)
                    history = await self.tool(profile, 'GET', '/v1/history', params={'channel_id': channel})
                    for data in self.memories.values():
                        if any(data['marker'] in json.dumps(row, ensure_ascii=False) for row in history):
                            raise AcceptanceBlocked('private memory canary leaked to native channel history')
                    for operation in {row['operation_id'] for row in history if row['kind'] == 'request'}:
                        try:
                            verify_exchange(history, operation)
                        except ValueError:
                            raise AcceptanceBlocked('project history has missing/duplicated correlated messages') from None
                    checked.append({'project': project, 'profile': profile, 'channel_id': channel,
                                    'history': public_history(history)})
        required = {row[k] for row in self.receipt['channels'].values()
                    for k in ('coding_architect', 'acceptance_coding')}
        if not required <= seen:
            raise AcceptanceBlocked('native channel catalog omitted a known acceptance channel')
        self.receipt['checks']['canary_history_scope'] = checked

    async def idle_activity(self):
        metadata = ledger_metadata(self.state)
        channels = {p: set() for p in self.sessions}
        sessions = {p: set(ids) for p, ids in self.sessions.items()}
        runs = {p: set() for p in self.sessions}
        for row in metadata['sessions']:
            profile = row['profile']
            channels[profile].add(row['channel_id'])
            sessions[profile].update((row['origin_id'], row['current_id']))
        for row in self.receipt['runs'] + metadata['held']:
            if row.get('run_id'):
                runs[row['profile']].add(row['run_id'])
        return await self.readbacks.activity(sessions, channels, runs)

    async def exercise(self):
        assert self.network is not None
        arguments: dict[str, Any] = {'name': 'acceptance', 'token': self.network.keys['acceptance'], 'allowed_peers': {'coding', 'architect'},
                     'ledger_path': self.state / 'acceptance.sqlite', 'control_path': self.state / 'admission.sqlite'}
        async with Network.connect(self.network.url, **arguments) as caller:
            identities = {p.name: p.agent_id for p in await caller.peers()}
            self.receipt['identities'] = identities
            outer = await caller.open(peer='coding', project_id=self.projects[0])
            first_prompt, first = await self.consult(caller, outer, self.projects[0], 'first')
            self.passed('1', '2', '3', '4')
            _, second = await self.consult(caller, outer, self.projects[0], 'second')
            coding_runs = [r for r in self.receipt['runs'] if r['profile'] == 'coding']
            if coding_runs[-1]['origin_session_id'] != coding_runs[-2]['origin_session_id']:
                raise AcceptanceBlocked('Coding second consultation forked its session lineage')
            if first['session_id'] != second['session_id']:
                # Native rotation is allowed only with a stable origin receipt.
                runs = [r for r in self.receipt['runs'] if r['profile'] == 'architect']
                if runs[-1]['origin_session_id'] != runs[-2]['origin_session_id']:
                    raise AcceptanceBlocked('Architect second consultation forked its session lineage')
            self.passed('5', '6')
            before = await self.readbacks.snapshot(self.sessions)
            replays = await asyncio.gather(*(caller.ask(outer, first_prompt,
                operation_id=self.projects[0] + '-first', timeout=10) for _ in range(2)), return_exceptions=True)
            refused = [r for r in replays if isinstance(r, ValueError) and str(r) == 'operation already awaited']
            replies = [r for r in replays if not isinstance(r, BaseException)]
            if not replies or len(refused) + len(replies) != 2:
                raise AcceptanceBlocked('concurrent retry returned an unexpected or uncertain outcome; no automatic replay')
            replay = replies[0]
            after = await self.readbacks.snapshot(self.sessions)
            if before != after or any(r.kind != 'reply' or asdict(r) != asdict(replay) for r in replies):
                raise AcceptanceBlocked('duplicate operation caused additional Hermes activity')
            try:
                verify_exchange([asdict(m) for m in await caller.history(outer)], self.projects[0] + '-first')
            except ValueError:
                raise AcceptanceBlocked('duplicate retry appended a duplicate native request/reply') from None
            self.receipt['checks']['duplicate_replay'] = {'run_id': replay.run_id,
                'counters_unchanged': True, 'concurrent_retries': 2, 'same_native_receipt': True,
                'locally_refused_pending_retry_count': len(refused)}
            await self.faults()
            await self.private_memory()
            primary_channel = self.receipt['channels'][self.projects[0]]['coding_architect']
            old_history = await self.native_history(primary_channel)
            before_restart = ledger_metadata(self.state)['sessions']
        self.receipt['restart'] = {'stopped': await self.network.stop()}
        await self.network.start()
        self.receipt['restart']['new_pids'] = list(self.network.pids[-3:])
        self.passed('8')
        async with Network.connect(self.network.url, **arguments) as caller:
            if identities != {p.name: p.agent_id for p in await caller.peers()}:
                raise AcceptanceBlocked('native identities changed on restart')
            if old_history != await self.native_history(primary_channel):
                raise AcceptanceBlocked('native history changed on restart')
            reopened = await caller.open(peer='coding', project_id=self.projects[0])
            if reopened != outer:
                raise AcceptanceBlocked('outer project channel changed on restart')
            await self.consult(caller, outer, self.projects[0], 'after-restart')
            after_restart = ledger_metadata(self.state)['sessions']
            if ({(r['profile'], r['project_id'], r['channel_id']): r['origin_id'] for r in before_restart}
                    != {(r['profile'], r['project_id'], r['channel_id']): r['origin_id'] for r in after_restart}):
                raise AcceptanceBlocked('restart changed stable Hermes origin-session mapping')
            if self.receipt['channels'][self.projects[0]]['coding_architect'] != primary_channel:
                raise AcceptanceBlocked('Coding/Architect channel changed on restart')
            self.passed('9')
            parallel_outer = await caller.open(peer='coding', project_id=self.projects[1])
            await asyncio.gather(self.consult(caller, outer, self.projects[0], 'parallel'),
                                 self.consult(caller, parallel_outer, self.projects[1], 'parallel'))
            self.receipt['checks']['two_project_parallel'] = {'submitted_concurrently': True,
                'profile_execution_serialized': True, 'distinct_channels': primary_channel != self.receipt['channels'][self.projects[1]]['coding_architect']}
            mappings = ledger_metadata(self.state)['sessions']
            for profile in ('coding', 'architect'):
                owned = [r for r in mappings if r['profile'] == profile]
                if len({r['origin_id'] for r in owned}) != len(owned) or len({r['current_id'] for r in owned}) != len(owned):
                    raise AcceptanceBlocked(f'{profile}: projects share a Hermes session; parallel isolation failed')
            await self.verify_histories()
            before = await self.idle_activity()
            start = time.monotonic()
            await asyncio.sleep(self.idle_seconds)
            after = await self.idle_activity()
            unchanged = before == after
            self.receipt['checks']['idle'] = {'observed_seconds': time.monotonic() - start,
                'scope': 'public acceptance-channel session discovery, session counters, and every Run for each discovered acceptance session; no unrelated/global-zero claim',
                'before': before, 'after': after, 'unchanged': unchanged,
                'complete': True, 'new_run_discovery': 'authenticated exact-session GET /v1/runs'}
            if not unchanged:
                raise AcceptanceBlocked('idle acceptance sessions or Runs produced activity')
            self.passed('10')

    def cancelled(self):
        self._cancelled = True
        message = 'Acceptance cancelled; no new Hermes cleanup Runs submitted. Retain ledger and settle owning Runs before memory cleanup'
        if message not in self.receipt['blockers']:
            self.receipt['blockers'].append(message)

    async def protected_cleanup(self, awaitable, label: str, timeout: float):
        # Signals cancel the caller, not this bounded resource finalizer. Repeated
        # signals still set the no-new-Runs gate while owned processes are reaped.
        task = asyncio.create_task(asyncio.wait_for(awaitable, timeout))
        while True:
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                self.cancelled()
                if task.cancelled():
                    self.receipt['blockers'].append(f'{label}: cleanup cancelled internally; operator verification required')
                    return None
            except Exception as exc:  # health: allow BLE001 -- sanitized resource finalization receipt
                self.receipt['blockers'].append(f'{label}: cleanup unsettled ({type(exc).__name__}); operator verification required')
                return None

    async def run(self) -> dict:
        self._cancelled = False
        try:
            self.resources = {p: profile_resources(self.home, p) for p in ('coding', 'architect')}
            self.receipt['profile_backends'] = {p: r['memory_backend'] for p, r in self.resources.items()}
            enrolled = enrolled_profiles(self.home)
            missing = sorted(set(self.resources) - set(enrolled))
            if missing:
                raise AcceptanceBlocked('Explicit bridge enrollment missing: ' + ', '.join(missing) +
                    '; owner must authorize profiles --home ROOT --enroll NAME. Executor does not alter live enrollment/config.')
            for profile in self.resources:
                capabilities = await self.readbacks.get(profile, 'v1/capabilities')
                features = capabilities.get('features', {})
                if (features.get('run_submission') is not True or features.get('run_status') is not True
                        or features.get('run_list_by_session') is not True
                        or features.get('runs_idempotency', {}).get('durable') is not True):
                    raise AcceptanceBlocked(f'{profile}: durable public Runs/idempotency and exact-session Run discovery required before mutation')
            self.network = TemporaryNetwork(self.state, self.home, self.api_url, self.credentials, self.resources, self.projects)
            self.network.prepare()
            self.receipt['mutations'].append({'temporary_network_state': str(self.state)})
            await self.network.start()
            await self.exercise()
        except asyncio.CancelledError:
            self.cancelled()
        except AcceptanceBlocked as exc:
            self.receipt['blockers'].append(str(exc))
        except Exception as exc:  # health: allow BLE001 -- sanitize provider/tool/private exception bodies in evidence
            self.receipt['blockers'].append(f'Live acceptance stopped ({type(exc).__name__}); no automatic retry of uncertain work. Inspect recorded Runs/retained ledger.')
        finally:
            if self.network is not None:
                # Prevent queued/parallel transport from starting a new writer during cleanup.
                self.receipt['cleanup']['processes'] = await self.protected_cleanup(
                    self.network.stop(), 'Owned processes', 65)
            processes = self.receipt['cleanup'].get('processes')
            reaped = processes is not None and all(row['returncode'] is not None for row in processes)
            if self.network is not None and not reaped:
                self.receipt['blockers'].append('Owned process cleanup incomplete; no new memory Runs, operator verification required')
            try:
                if not self._cancelled and reaped:
                    async with asyncio.timeout(330):
                        await self.cleanup_memory()
            except asyncio.CancelledError:
                self.cancelled()
            except Exception as exc:  # health: allow BLE001 -- do not leak owning runtime/private memory in cleanup failure
                self.receipt['blockers'].append(f'Owning-runtime memory cleanup unsettled ({type(exc).__name__}); operator readback required')
            if self.network is not None:
                if self.network.owns_state:
                    try:
                        self.receipt['ledger_metadata'] = ledger_metadata(self.state)
                    except (OSError, sqlite3.Error, ValueError):
                        self.receipt['blockers'].append('Operational ledger metadata unreadable; retain state for operator reconciliation')
                    finally:
                        try:
                            self.network.remove_credentials()
                            self.receipt['cleanup']['temporary_credentials_removed'] = True
                        except OSError:
                            self.receipt['cleanup']['temporary_credentials_removed'] = False
                            self.receipt['blockers'].append('Temporary credential removal failed; operator cleanup required')
                    self.receipt['cleanup']['durable_state_retained'] = str(self.state)
            unchanged = {}
            for profile, resource in self.resources.items():
                try:
                    unchanged[profile] = digest(resource['config'].read_bytes()) == resource['config_sha256']
                except OSError:
                    unchanged[profile] = False
            self.receipt['cleanup']['profile_configs_unchanged'] = unchanged
            if not all(self.receipt['cleanup']['profile_configs_unchanged'].values()):
                self.receipt['blockers'].append('Profile configuration changed during acceptance; operator review required, no automatic restoration')
            await self.protected_cleanup(self.readbacks.http.aclose(), 'HTTP client', 15)
        self.receipt['live_scenario_completed'] = (not self.receipt['blockers'] and
            all(step['status'] == 'passed' for step in self.receipt['steps'].values()) and
            all(self.receipt['cleanup']['profile_configs_unchanged'].values()))
        return self.receipt
