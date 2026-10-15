"""Acceptance executor public interface; controlled HTTP is never a live receipt."""
import asyncio
import json
from pathlib import Path


def test_two_project_isolation_requires_each_profile_to_have_distinct_project_mappings():
    from hermes_ag2_network.live_scenario import validate_project_mappings

    expected_channels = {
        'project-alpha': {'coding': {'control-alpha'}, 'architect': {'coding-alpha'}},
        'project-beta': {'coding': {'control-beta'}, 'architect': {'coding-beta'}},
    }
    mappings = [
        {'profile': profile, 'project_id': project, 'channel_id': channel,
         'origin_id': f'{profile}-origin-{project}', 'current_id': f'{profile}-current-{project}'}
        for project, channels in expected_channels.items()
        for profile, profile_channels in channels.items() for channel in profile_channels
    ]
    validate_project_mappings(('project-alpha', 'project-beta'), mappings, expected_channels)
    mappings[-1] = {**mappings[-1], 'project_id': 'project-alpha'}
    try:
        validate_project_mappings(('project-alpha', 'project-beta'), mappings, expected_channels)
    except ValueError:
        pass
    else:
        raise AssertionError('mislabelled project session mapping must block isolation PASS')


def test_project_history_rejects_cross_project_operation_and_content():
    from hermes_ag2_network.live_scenario import validate_project_history

    validate_project_history('project-alpha', 'project-beta', [
        {'kind': 'request', 'operation_id': 'project-alpha-first', 'text': 'alpha result'}])
    for row in (
        {'kind': 'request', 'operation_id': 'project-beta-first', 'text': 'alpha result'},
        {'kind': 'reply', 'operation_id': 'project-alpha-first', 'text': 'project-beta-result'},
    ):
        try:
            validate_project_history('project-alpha', 'project-beta', [row])
        except ValueError:
            pass
        else:
            raise AssertionError('cross-project history must block isolation PASS')


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
