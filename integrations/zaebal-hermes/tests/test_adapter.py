"""Контракт реального hook seam; никаких model/API calls."""
import importlib.util
import concurrent.futures
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path('/home/vottak/.hermes/cache/scratch')


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='zaebal-test-', dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        spec = importlib.util.spec_from_file_location('zaebal_test_plugin', ROOT / 'plugin' / '__init__.py')
        assert spec is not None and spec.loader is not None
        self.plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.plugin)
        self.hook = self.plugin.Adapter(Path(self.temp.name)).on_user_turn

    def send(self, text, turn='1', session='s', **extra):
        return self.hook(user_message=text, turn_id=turn, session_id=session, **extra)

    def test_directed_input_produces_protocol(self):
        result = self.send('Ты заебал, опять всё сломал')
        self.assertIn('<zaebal level="1">', result['context'])
        self.assertIsNone(self.send(result['context'], 'injected-protocol-replay'))


    def test_silent_text_praise_and_quoted_profanity(self):
        for n, text in enumerate(['Привет, проверь код', 'Охуенно, спасибо!',
                                  'Переведи фразу «ты заебал»', 'Изучи плагин zaebal']):
            with self.subTest(text=text):
                self.assertIsNone(self.send(text, str(n)))

    def test_escalation_ack_reset_and_manual(self):
        for n, level in enumerate([1, 2, 2, 3]):
            result = self.send('Ты заебал, опять всё сломал', str(n))
            self.assertIn(f'<zaebal level="{level}">', result['context'])
            self.assertNotIn('<zaebal-verdict auditor=', result['context'])
            self.assertIn('Не вызывай никаких дополнительных агентов', result['context'])
        self.assertIn('<zaebal level="0">', self.send('продолжай', 'ack')['context'])
        self.assertIn('<zaebal level="1">', self.send('Ты заебал', 'new')['context'])
        self.assertIn('<zaebal-manual>', self.send('zaebal audit', 'manual')['context'])
        self.assertIn('<zaebal level="2">', self.send('Ты заебал', 'after-manual')['context'])

    def test_history_tool_output_and_malformed_input_never_fallback(self):
        history = [{'role': 'user', 'content': 'Ты заебал'},
                   {'role': 'tool', 'content': 'Ты заебал'}]
        before = copy.deepcopy(history)
        for n, text in enumerate([None, {}, [], 42, '', 'Обычный запрос']):
            self.assertIsNone(self.send(text, str(n), conversation_history=history))
        self.assertEqual(history, before)
        self.assertIsNone(self.send('Ты заебал', 'child', parent_session_id='parent'))
        self.assertIsNone(self.send('Ты заебал', ''))
        self.assertIsNone(self.send('Ты заебал', 'turn', session=''))
        self.assertIn('<zaebal level="1">', self.send('Ты заебал', 'real')['context'])

    def test_repeat_tool_loop_restart_and_concurrent_claim(self):
        args = dict(user_message='Ты заебал', session_id='s', turn_id='same')
        self.assertIn('<zaebal level="1">', self.hook(**args)['context'])
        for _ in range(3):
            self.assertIsNone(self.hook(**args, conversation_history=[{'role': 'tool', 'content': 'Ты заебал'}]))
        reloaded = self.plugin.Adapter(Path(self.temp.name))
        self.assertIsNone(reloaded.on_user_turn(**args))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.send('Ты заебал', 'race'), range(8)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertIn('<zaebal level="2">', next(r for r in results if r)['context'])

    def test_same_session_and_turn_are_isolated_across_profiles(self):
        other = self.plugin.Adapter(Path(self.temp.name) / 'profiles' / 'design')
        for n in range(4):
            self.send('Ты заебал', str(n))
        self.assertIn('<zaebal level="1">', other.on_user_turn(
            user_message='Ты заебал', session_id='s', turn_id='0')['context'])
        self.assertIn('<zaebal level="1">', self.send('Ты заебал', '0', session='independent')['context'])

    def test_external_auditor_poison_config_is_overridden(self):
        state = Path(self.temp.name) / 'plugin-data' / 'zaebal-hermes' / 'sessions' / hashlib.sha256(b's').hexdigest()
        state.mkdir(parents=True)
        marker = Path(self.temp.name) / 'AUDITOR_RAN'
        poison = {'auditor': 'codex', 'audit_levels': [1, 2, 3],
                  'auditor_command': [sys.executable, '-c', f'open({str(marker)!r}, "w").write("bad")']}
        (state / 'config.json').write_text(json.dumps(poison))
        for n in range(4):
            self.assertIsNotNone(self.send('Ты заебал', str(n)))
        self.assertFalse(marker.exists())
        config = json.loads((state / 'config.json').read_text())
        self.assertEqual(config['auditor'], 'none')
        self.assertEqual(config['audit_levels'], [])
        self.assertEqual(config['auditor_command'], '')
        records = [json.loads(x) for x in (state / 'incidents.jsonl').read_text().splitlines()]
        self.assertEqual(len(records), 4)
        self.assertTrue(all(not r['auditor_invoked'] for r in records))
        self.assertTrue(all(not r['verdict_received'] for r in records))

    def test_upstream_session_controls_do_not_falsely_claim_disabled(self):
        off = self.send('zaebal off', 'off')
        self.assertIsNotNone(off)
        self.assertIsNone(self.send('Ты заебал', 'disabled'))
        self.assertIsNotNone(self.send('zaebal on', 'on'))
        self.assertIn('<zaebal level="1">', self.send('Ты заебал', 'enabled')['context'])

    def test_state_error_and_timeout_are_safe_and_no_retry(self):
        broken = Path(self.temp.name) / 'not-dir'
        broken.write_text('file')
        adapter = self.plugin.Adapter(broken)
        self.assertIsNone(adapter.on_user_turn(user_message='Ты заебал', session_id='s', turn_id='1'))
        from unittest.mock import patch
        with patch.object(self.plugin.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 2)) as run:
            self.assertIsNone(self.send('Ты заебал', 'timed-out'))
            self.assertIsNone(self.send('Ты заебал', 'timed-out'))
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
