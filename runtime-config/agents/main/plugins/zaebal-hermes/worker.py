"""Bounded stdlib subprocess entrypoint; vendored source stays byte-identical."""
import json
import os
from pathlib import Path
import runpy
import sys


def forbid_external(event, args):
    if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.spawn') or event.startswith('socket.'):
        raise PermissionError('External processes/network disabled for Z.A.E.B.A.L. worker')


def main():
    sys.addaudithook(forbid_external)
    core = Path(__file__).resolve().parent / 'vendor' / 'core'
    sys.path.insert(0, str(core))
    from platform_runtime import state_lock
    state = Path(os.environ['ZAEBAL_STATE_DIR'])
    # Single writer per session, including the immutable safety overlay.
    with state_lock(state / 'adapter.lock', timeout=0.3):
        safe = {'auditor': 'none', 'audit_levels': [], 'auditor_command': '',
                'allow_unsafe_auditor': False, 'auto_trigger': True, 'manual_trigger': True}
        target = state / 'config.json'
        try:
            previous = json.loads(target.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            previous = {}
        if isinstance(previous, dict):
            for key in ('auto_trigger', 'manual_trigger'):
                if isinstance(previous.get(key), bool):
                    safe[key] = previous[key]
        pending = state / 'config.pending'
        pending.write_text(json.dumps(safe), encoding='utf-8')
        os.replace(pending, target)
        sys.argv = [str(core / 'zaebal.py'), '--host', 'hermes']
        runpy.run_path(str(core / 'zaebal.py'), run_name='__main__')


if __name__ == '__main__':
    main()
