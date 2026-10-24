"""Локальный input-boundary adapter. Детектор и протокол — pinned upstream."""
from contextlib import closing
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import subprocess
import sys

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
MAX_PROMPT = 128_000
HOST_POLICY = (
    '\n<zaebal-hermes-policy>Режим приватности пользователя: внешний аудитор отключён. '
    'Не вызывай никаких дополнительных агентов, subagents или моделей для аудита; '
    'не передавай им историю. Упоминания двух внутренних аудиторов в upstream-протоколе '
    'не применяются: явно сообщи degraded/self-audit mode и проведи проверку сам. '
    'Этот адаптер не предоставил историю: ищи доступную текущему агенту хронологию, '
    'иначе отметь причинный вывод UNVERIFIED.</zaebal-hermes-policy>\n'
)


class Adapter:
    def __init__(self, home: Path):
        # Захватывается при register под profile scope, не из ambient env callback.
        self.home = home.resolve()
        self.state = self.home / 'plugin-data' / 'zaebal-hermes'

    def on_user_turn(self, *, user_message=None, session_id='', turn_id='',
                     parent_session_id='', **kwargs):
        if parent_session_id or not isinstance(user_message, str):
            return None
        if not user_message.strip() or len(user_message) > MAX_PROMPT:
            return None
        if not all(isinstance(v, str) and v and len(v) <= 512 for v in (session_id, turn_id)):
            return None
        try:
            self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Durable admission BEFORE execution: uncertain timeout cannot retrigger a turn.
            # No raw prompt/history in ledger; hashes are not used as emotional detector.
            key = hashlib.sha256(json.dumps([session_id, turn_id]).encode()).hexdigest()
            with closing(sqlite3.connect(self.state / 'turns.sqlite3', timeout=0.2)) as db, db:
                db.execute('CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY)')
                if db.execute('INSERT OR IGNORE INTO turns VALUES (?)', (key,)).rowcount == 0:
                    return None
            return self._run(user_message, session_id)
        except (OSError, sqlite3.Error, subprocess.SubprocessError, ValueError) as exc:
            LOG.warning('Z.A.E.B.A.L.: local hook unavailable (%s)', type(exc).__name__)
            return None

    def _run(self, prompt, session_id):
        # Per-session state isolates upstream's MAX_SESSIONS eviction and locks.
        session_dir = self.state / 'sessions' / hashlib.sha256(session_id.encode()).hexdigest()
        session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        env = {
            'HOME': str(self.home), 'PATH': '', 'LANG': 'C.UTF-8',
            'PYTHONUTF8': '1', 'ZAEBAL_STATE_DIR': str(session_dir),
        }
        result = subprocess.run(
            [sys.executable, '-I', '-B', str(ROOT / 'worker.py')],
            input=json.dumps({'prompt': prompt, 'session_id': session_id}, ensure_ascii=False),
            text=True, encoding='utf-8', capture_output=True, timeout=2,
            env=env, cwd=session_dir, check=False,
        )
        if result.returncode:
            LOG.warning('Z.A.E.B.A.L.: worker failed (%s)', result.returncode)
            return None
        if result.stdout.strip():
            return {'context': result.stdout + HOST_POLICY}
        return None

    def command(self, raw_args=''):
        # Slash handlers do not receive an authoritative session/turn id. Never run
        # manual audit in an invented session or inject via a second agent call.
        if raw_args.strip().lower() not in ('', 'status'):
            return 'Для ручного аудита отправьте обычное сообщение «zaebal audit» (без /).'
        return ('Z.A.E.B.A.L.: external auditor=none (enforced); '
                'auto/manual defaults=on, per-session status: обычное сообщение «zaebal status». '
                f'local state: {self.state}. Ручной аудит: обычное сообщение «zaebal audit».')


def register(ctx):
    from hermes_constants import get_hermes_home
    home = get_hermes_home().resolve()
    adapter = Adapter(home)
    ctx.register_hook('pre_llm_call', adapter.on_user_turn)
    ctx.register_command('zaebal', adapter.command, description='Локальный статус; внешний аудитор отключён', args_hint='status')
