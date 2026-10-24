"""Запускается hermes --run-module runpy в свежем процессе / isolated home."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from hermes_constants import get_hermes_home
from hermes_cli.plugins import get_plugin_manager
from agent.turn_context import _collect_pre_llm_call_context, compose_user_api_content

import unittest


class InstalledHostSmoke(unittest.TestCase):
    def test_installed_hook_and_dynamic_tail(self):
        manager = get_plugin_manager()
        manager.discover_and_load()
        entries = [p for p in manager.list_plugins() if p['name'] == 'zaebal-hermes']
        assert len(entries) == 1, entries
        assert entries[0]['enabled'] and not entries[0]['error'], entries
        assert entries[0]['hooks'] == 1 and entries[0]['commands'] == 1, entries
        
        agent = SimpleNamespace(session_id='host-session', model='no-model-used', platform='cli')
        prompt = 'Ты заебал, опять всё сломал'
        messages = [{'role': 'system', 'content': 'CACHE-PREFIX-UNCHANGED'},
                    {'role': 'user', 'content': 'исторический запрос'},
                    {'role': 'assistant', 'content': 'старый ответ'},
                    {'role': 'user', 'content': prompt}]
        before = copy.deepcopy(messages)
        levels = []
        for n, level in enumerate([1, 2, 2, 3]):
            context = _collect_pre_llm_call_context(
                agent, effective_task_id='task', turn_id=str(n), original_user_message=prompt,
                messages=messages, conversation_history=messages[:-1])
            assert f'<zaebal level="{level}">' in context, context
            wire = compose_user_api_content(prompt, '', context)
            assert isinstance(wire, str)
            assert wire.startswith(prompt + '\n\n'), wire
            assert messages == before
            assert wire.count(f'<zaebal level="{level}">') == 1
            levels.append(level)
        repeat = _collect_pre_llm_call_context(
            agent, effective_task_id='task', turn_id='3', original_user_message=prompt,
            messages=messages + [{'role': 'tool', 'content': prompt}], conversation_history=messages)
        assert repeat == '', repeat
        # Neither prior user messages nor tool text are the input boundary.
        assert manager.invoke_hook('pre_llm_call', session_id='history', turn_id='x',
                                   conversation_history=messages) == []
        from hermes_cli.plugins import PluginManager, get_plugin_command_handler
        status = get_plugin_command_handler('zaebal')
        assert status is not None and 'auditor=none' in status('status')
        other = get_hermes_home() / 'profiles' / 'design'
        same_process_isolation = None
        if other.is_dir():
            secondary = PluginManager(scope_key=str(other))
            secondary.discover_and_load()
            args = dict(session_id='same-in-process', turn_id='same', user_message=prompt)
            one = manager.invoke_hook('pre_llm_call', **args)
            two = secondary.invoke_hook('pre_llm_call', **args)
            assert len(one) == len(two) == 1, (one, two)
            assert '<zaebal level="1">' in one[0]['context']
            assert '<zaebal level="1">' in two[0]['context']
            same_process_isolation = True
        print(json.dumps({'home': str(get_hermes_home()), 'loader': 'installed PluginManager',
                          'same_process_profile_isolation': same_process_isolation,
                          'plugin': entries[0], 'levels': levels, 'system_prefix': 'unchanged',
                          'duplicate': 'silent', 'history_only': 'silent',
                          'model_calls': 0, 'live_install': False}, ensure_ascii=False))
