"""Acceptance executor public interface; controlled HTTP is never a live receipt."""
import asyncio
import json
from pathlib import Path



def test_execute_with_unready_api_never_creates_network_state(cli, endpoint, tmp_path):
    run, receipt, _, _ = cli
    url, state = endpoint
    state['status'] = 503
    target = tmp_path / 'new-network'
    result = run(url, '--execute', '--state-dir', str(target))
    assert result.returncode == 2
    saved = json.loads(receipt.read_text())
    assert saved['phase'] == 'readiness'
    assert saved['mutations'] == []
    assert not target.exists()


def test_evidence_requires_correlated_terminal_runs_not_model_prose():
    from hermes_ag2_network.live_scenario import verify_exchange
    request = {'kind': 'request', 'envelope_id': 'req', 'operation_id': 'op'}
    reply = {'kind': 'reply', 'envelope_id': 'rep', 'operation_id': 'op',
             'causation_id': 'req', 'session_id': 'session', 'run_id': 'run', 'text': 'advice'}
    assert verify_exchange([request, reply], 'op')['run_id'] == 'run'
    for change in ({'causation_id': 'other'}, {'run_id': ''}, {'kind': 'status'}):
        broken = {**reply, **change}
        try:
            verify_exchange([request, broken], 'op')
        except ValueError:
            pass
        else:
            raise AssertionError('uncorrelated/unterminated exchange must fail')


def test_missing_plugin_secret_blocks_before_creating_state(tmp_path):
    from hermes_ag2_network.live_scenario import LiveScenario
    home = tmp_path / 'home'
    for profile in ('coding', 'architect'):
        p = home / 'profiles' / profile
        p.mkdir(parents=True)
        (p / 'config.yaml').write_text('memory: {}\n')
    target = tmp_path / 'state'
    scenario = LiveScenario('http://127.0.0.1:1', {'coding': 'key', 'architect': 'other'},
                            home=home, state_dir=target, idle_seconds=2)
    receipt = asyncio.run(scenario.run())
    assert receipt['live_scenario_completed'] is False
    assert receipt['mutations'] == []
    assert not target.exists()
    assert receipt['blockers']
