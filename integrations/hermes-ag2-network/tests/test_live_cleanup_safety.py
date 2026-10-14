"""Cancellation and malformed prerequisites never skip invocation-owned cleanup."""
import asyncio

import pytest
import yaml

from hermes_ag2_network.live_runtime import AcceptanceBlocked, profile_resources
from hermes_ag2_network.live_scenario import LiveScenario


@pytest.mark.parametrize('settings', [
    {'plugins': None}, {'plugins': {'entries': None}},
    {'plugins': {'entries': {'agent-network': None}}},
    {'plugins': {'entries': {'agent-network': {'settings': None}}}},
    {'plugins': {'enabled': None}}, {'memory': None},
])
def test_null_configuration_is_safe_prerequisite_blocker(tmp_path, settings):
    root = tmp_path / 'profiles' / 'coding'
    (root / 'plugins' / 'agent-network').mkdir(parents=True)
    (root / 'plugins' / 'agent-network' / '__init__.py').write_text('')
    (root / '.env').write_text('AGENT_NETWORK_TOOLS_KEY=test-only\n')
    (root / '.env').chmod(0o600)
    valid = {'plugins': {'enabled': ['agent-network'], 'entries': {
        'agent-network': {'settings': {'bridge_url': 'http://127.0.0.1:12345'}}}}}
    valid.update(settings)
    (root / 'config.yaml').write_text(yaml.safe_dump(valid))
    with pytest.raises(AcceptanceBlocked, match='configuration.*no automatic repair'):
        profile_resources(tmp_path, 'coding')


@pytest.mark.parametrize('phase', ['processes', 'memory', 'http'])
def test_cancel_during_cleanup_returns_receipt_and_reaps_owned_resources(tmp_path, monkeypatch, phase):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        removed, stopped, closed = [], [], []
        memory_runs = []
        owner = LiveScenario('http://127.0.0.1:1', {}, home=tmp_path, state_dir=tmp_path / 'state')

        class Network:
            owns_state = True
            async def stop(self):
                if phase == 'processes':
                    entered.set()
                    await release.wait()
                stopped.append(True)
                return [{'pid': 123, 'returncode': 0}]
            def remove_credentials(self):
                removed.append(True)

        class HTTP:
            async def aclose(self):
                if phase == 'http':
                    entered.set()
                    await release.wait()
                closed.append(True)

        async def cleanup_memory():
            if phase == 'memory':
                entered.set()
                await release.wait()
            memory_runs.append('new-cleanup-run')

        # Already-created invocation resources; prerequisite failure enters normal cleanup.
        monkeypatch.setattr(owner, 'network', Network())
        await owner.readbacks.http.aclose()
        monkeypatch.setattr(owner.readbacks, 'http', HTTP())
        monkeypatch.setattr(owner, 'cleanup_memory', cleanup_memory)
        task = asyncio.create_task(owner.run())
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()  # repeated shutdown signals must not abandon shielded cleanup
        release.set()
        receipt = await asyncio.wait_for(task, 5)
        assert stopped and removed and closed
        assert receipt['live_scenario_completed'] is False
        assert any('cancel' in b.lower() for b in receipt['blockers'])
        if phase != 'http':
            assert memory_runs == []
    asyncio.run(scenario())
