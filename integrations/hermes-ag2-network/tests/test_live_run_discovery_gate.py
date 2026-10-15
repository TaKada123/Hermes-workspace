"""The live executor fails closed unless the Gateway advertises session Run listing."""
import asyncio


def test_missing_run_list_capability_blocks_before_network_state(tmp_path, monkeypatch):
    from hermes_ag2_network.discovery import enroll_profile
    from hermes_ag2_network.live_runtime import Readbacks
    from hermes_ag2_network.live_scenario import LiveScenario

    home = tmp_path / 'home'
    for profile, port in (('coding', 8766), ('architect', 8767)):
        root = home / 'profiles' / profile
        plugin = root / 'plugins' / 'agent-network'
        plugin.mkdir(parents=True)
        (plugin / '__init__.py').write_text('# existing fixture plugin\n')
        (root / 'config.yaml').write_text(
            f'plugins:\n  enabled: [agent-network]\n  entries:\n    agent-network:\n'
            f'      settings:\n        bridge_url: http://127.0.0.1:{port}\n')
        (root / '.env').write_text(f'AGENT_NETWORK_TOOLS_KEY={profile}-tools\n')
        (root / '.env').chmod(0o600)
        memory = root / 'memories'
        memory.mkdir()
        (memory / 'MEMORY.md').write_text('unmodified fixture memory\n')
        enroll_profile(profile, home)

    async def capabilities(_self, _profile, _path, **_params):
        return {'features': {'run_submission': True, 'run_status': True,
                             'run_list_by_session': False,
                             'runs_idempotency': {'durable': True}}}

    monkeypatch.setattr(Readbacks, 'get', capabilities)
    state = tmp_path / 'new-network-state'
    receipt = asyncio.run(LiveScenario(
        'http://127.0.0.1:8642', {'coding': 'coding-api', 'architect': 'architect-api'},
        home=home, state_dir=state, idle_seconds=2).run())

    assert receipt['live_scenario_completed'] is False
    assert receipt['mutations'] == []
    assert 'exact-session Run discovery required' in receipt['blockers'][0]
    assert not state.exists()
