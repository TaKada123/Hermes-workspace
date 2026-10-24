#!/usr/bin/env python3
"""Experimental installer: dry-run by default, no daemon restart or model calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parent / 'plugin'
NAME = 'zaebal-hermes'


def discover_targets(root, all_profiles=False):
    root = root.expanduser().resolve()
    if root.parent.name == 'profiles' or not (root / 'config.yaml').is_file():
        raise ValueError('--root must be an existing default Hermes home with config.yaml')
    targets = [root]
    profiles = root / 'profiles'
    if all_profiles and profiles.is_dir():
        for p in sorted(profiles.iterdir()):
            if not p.name.startswith('.') and p.is_dir() and not p.is_symlink() and (p / 'config.yaml').is_file():
                targets.append(p)
    return targets


def verify_vendor():
    vendor = SOURCE / 'vendor'
    expected = json.loads((vendor / 'SHA256.json').read_text())
    for name, digest in expected.items():
        if hashlib.sha256((vendor / 'core' / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'vendor hash mismatch: {name}')


def same_package(target):
    for src in SOURCE.rglob('*'):
        if src.is_file() and '__pycache__' not in src.parts:
            dst = target / src.relative_to(SOURCE)
            if not dst.is_file() or src.read_bytes() != dst.read_bytes():
                return False
    return True


def install(root, targets, hermes='hermes', apply=False):
    verify_vendor()
    shared = root / 'plugins' / NAME
    # Preflight every destination before touching any profile.
    if shared.is_symlink() or (shared.exists() and not same_package(shared)):
        raise FileExistsError(f'Foreign or older package: {shared}; preserve it and review manually')
    for home in targets[1:]:
        dest = home / 'plugins' / NAME
        if (dest.exists() or dest.is_symlink()) and not (dest.is_symlink() and dest.resolve() == shared.resolve()):
            raise FileExistsError(f'Foreign plugin destination: {dest}')
    print(json.dumps({'mode': 'apply' if apply else 'dry-run', 'shared_source': str(shared),
                      'targets': [str(h) for h in targets], 'auditor': 'none',
                      'activation': 'enable may hot-reload gateway/backend; fresh process guaranteed; no restart performed'}, ensure_ascii=False, indent=2))
    if not apply:
        return
    if not shared.exists():
        shared.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE, shared, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for home in targets:
        dest = home / 'plugins' / NAME
        if home != root and not dest.is_symlink():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(shared, target_is_directory=True)
        backup_dir = home / 'plugin-data' / NAME / 'install-backups'
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, backup = tempfile.mkstemp(prefix='config-before-enable-', suffix='.yaml', dir=backup_dir)
        with os.fdopen(fd, 'wb') as stream:
            stream.write((home / 'config.yaml').read_bytes())
        env = dict(os.environ, HERMES_HOME=str(home))
        # Avoid ambient named-profile CLI selection; HERMES_HOME is authoritative here.
        env.pop('HERMES_PROFILE', None)
        subprocess.run([hermes, 'plugins', 'enable', NAME, '--no-allow-tool-override'], env=env, check=True, timeout=120)
        # Exact target readback via the official CLI, not a hand-written YAML edit.
        enabled = subprocess.run([hermes, 'config', 'get', 'plugins.enabled', '--json'], env=env,
                                 check=True, text=True, capture_output=True, timeout=30)
        enabled_names = json.loads(enabled.stdout)
        if not isinstance(enabled_names, list) or NAME not in enabled_names:
            raise RuntimeError(f'Enable readback failed for {home}; backup: {backup}')
        if not same_package(dest):
            raise RuntimeError(f'Installed package readback failed: {dest}')
        print(f'VERIFIED {home}; backup={backup}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / '.hermes')
    parser.add_argument('--all-profiles', action='store_true')
    parser.add_argument('--apply', action='store_true', help='Write files and enable; without this flag read-only')
    parser.add_argument('--hermes', default='hermes', help='Reviewed Hermes wrapper executable')
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    install(root, discover_targets(root, args.all_profiles), hermes=args.hermes, apply=args.apply)


if __name__ == '__main__':
    main()
