import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path('/home/vottak/.hermes/cache/scratch')


class InstallerTests(unittest.TestCase):
    def test_discovery_dry_run_shared_runtime_and_conflict(self):
        spec = importlib.util.spec_from_file_location('zaebal_installer', ROOT / 'install.py')
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='zaebal-install-') as tmp:
            home = Path(tmp)
            (home / 'config.yaml').write_text('model: unrelated\n')
            for name in ('design', 'university'):
                profile = home / 'profiles' / name
                profile.mkdir(parents=True)
                (profile / 'config.yaml').write_text('model: unrelated\n')
            (home / 'profiles' / '.hidden').mkdir()
            homes = mod.discover_targets(home, all_profiles=True)
            self.assertEqual([p.name for p in homes], [home.name, 'design', 'university'])
            before = {str(p): p.read_bytes() for p in home.rglob('*') if p.is_file()}
            mod.install(home, homes, hermes='/no-cli-in-dry-run', apply=False)
            self.assertEqual(before, {str(p): p.read_bytes() for p in home.rglob('*') if p.is_file()})
            self.assertFalse((home / 'plugins').exists())
            # A foreign destination fails preflight; no partially installed defaults.
            foreign = home / 'profiles' / 'design' / 'plugins' / 'zaebal-hermes'
            foreign.mkdir(parents=True)
            with self.assertRaises(FileExistsError):
                mod.install(home, homes, hermes='/not-invoked', apply=True)
            self.assertFalse((home / 'plugins').exists())


if __name__ == '__main__':
    unittest.main()
