"""Fresh installed loader + installer, without model/network requests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path('/home/vottak/.hermes/cache/scratch')
HERMES = '/home/vottak/.local/bin/hermes'


class HostTests(unittest.TestCase):
    def test_real_cli_install_enable_and_hook_in_two_profiles(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='zaebal-host-') as tmp:
            home = Path(tmp)
            for p in [home, home / 'profiles' / 'design']:
                p.mkdir(parents=True, exist_ok=True)
                (p / 'config.yaml').write_text('model: preserve-model\ncustom_zaebal_test: preserve-me\nplugins:\n  enabled: []\n')
            result = subprocess.run([sys.executable, str(ROOT / 'install.py'), '--root', str(home),
                                     '--all-profiles', '--hermes', HERMES, '--apply'],
                                    capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.count('VERIFIED '), 2)
            shared = home / 'plugins' / 'zaebal-hermes'
            linked = home / 'profiles' / 'design' / 'plugins' / 'zaebal-hermes'
            self.assertTrue(linked.is_symlink())
            self.assertEqual(linked.resolve(), shared.resolve())
            for p in [home, home / 'profiles' / 'design']:
                config = (p / 'config.yaml').read_text()
                self.assertIn('preserve-model', config)
                self.assertIn('preserve-me', config)
                env = {k: v for k, v in os.environ.items() if not k.startswith('HERMES_')}
                env['HERMES_HOME'] = str(p)
                smoke = subprocess.run([HERMES, '--run-module', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'host_smoke.py'],
                                       env=env, text=True, capture_output=True, timeout=90)
                self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
                receipt = json.loads(smoke.stdout.splitlines()[-1])
                self.assertEqual(receipt['levels'], [1, 2, 2, 3])
                self.assertEqual(receipt['home'], str(p))
                print('HOST_RECEIPT', json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
