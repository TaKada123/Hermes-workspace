#!/usr/bin/env python3
"""Scoped Architect pilot installer. Never writes to the source home."""
import argparse
import json
import os
from pathlib import Path
import shutil
import shlex
import sqlite3
import subprocess
import sys

CAPABILITIES = ("skills", "scripts", "references", "plugins", "skins")
PRIVATE = ("memories", "sessions")
DISABLED = ("agent-network", "gumar-runtime-policy")
EXCLUDED = {".git", "__pycache__", ".pytest_cache", "cache", "caches", "logs", "cron",
            "agent-network", "plugin-data", "auth.json", "credentials.json", "tokens.json"}


def excluded(path):
    return (path.name in EXCLUDED or path.name.startswith((".env", "auth.", "state.db"))
            or path.name.endswith((".lock", ".pyc", ".db", ".sqlite", ".sqlite3")))


def overlaps(left, right):
    return left.is_relative_to(right) or right.is_relative_to(left)


def validate_private(path):
    if path.is_symlink():
        raise ValueError("Private state must not be a symlink")
    if path.is_dir():
        for child in path.iterdir():
            validate_private(child)
    elif not path.is_file():
        raise ValueError("Unsupported private state entry")


def audit_capability(path, roots, ancestors=frozenset()):
    resolved = path.resolve()
    if not any(resolved.is_relative_to(root) for root in roots):
        raise ValueError("Capability link escapes explicit capability roots")
    if resolved in ancestors:
        raise ValueError("Capability link cycle")
    if path.is_dir():
        for child in path.iterdir():
            # A preserved external link must not expose credentials, even indirectly.
            if child.name.startswith((".env", "auth.")) or child.name in {"credentials.json", "tokens.json"}:
                raise ValueError("Capability link exposes credential state")
            if not excluded(child):
                audit_capability(child, roots, ancestors | {resolved})
    elif not path.is_file() and not path.is_symlink():
        raise ValueError("Unsupported capability entry")


def capability_plan(path, destination, source, target, roots):
    if excluded(path):
        return []
    if path.is_symlink():
        audit_capability(path, roots)
        resolved = path.resolve()
        link = target / resolved.relative_to(source) if resolved.is_relative_to(source) else resolved
        return [("link", path, destination, link)]
    if path.is_dir():
        plan = [("dir", path, destination, None)]
        for child in path.iterdir():
            plan.extend(capability_plan(child, destination / child.name, source, target, roots))
        return plan
    if path.is_file():
        return [("file", path, destination, None)]
    raise ValueError("Unsupported capability entry")


def copy_capabilities(plan):
    for kind, source, target, link in plan:
        if kind == "dir":
            target.mkdir()
        elif kind == "link":
            target.symlink_to(link)
        else:
            shutil.copy2(source, target)


def config(hermes, home, *args):
    env = dict(os.environ, HERMES_HOME=str(home))
    env.pop("HERMES_PROFILE", None)
    result = subprocess.run([str(hermes), "config", *args], env=env,
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        # CLI output may contain config values; never echo it.
        raise ValueError("Hermes config operation failed (output suppressed)")
    return result.stdout


def backup_database(source, target):
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(target) as copied:
            original.backup(copied)
            if copied.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("SQLite backup failed integrity check")


def copy_private(source, target):
    if source.is_symlink():
        raise ValueError("Private state must not be a symlink")
    if source.is_dir():
        target.mkdir()
        for child in source.iterdir():
            copy_private(child, target / child.name)
    elif source.is_file():
        shutil.copy2(source, target)
    else:
        raise ValueError("Unsupported private state entry")


def write_launcher(target, hermes, alias):
    launcher = target / "architect-direct"
    launcher.write_text(
        '#!/bin/sh\n'
        'for arg in "$@"; do\n'
        '  case "$arg" in -p|--profile|--profile=*|-p?*)\n'
        '    printf "%s\\n" "Direct agent refuses profile overrides" >&2; exit 2;;\n'
        '  esac\n'
        'done\n'
        'unset HERMES_PROFILE\n'
        f'export HERMES_HOME={shlex.quote(str(target))}\n'
        f'exec {shlex.quote(str(hermes))} "$@"\n', encoding="utf-8")
    launcher.chmod(0o700)
    if alias:
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(launcher)


def install(args):
    if args.source.is_symlink() or args.target.is_symlink():
        raise ValueError("Home paths must not be symlinks")
    source = args.source.resolve()
    target = args.target.resolve()
    definitions = args.definitions.resolve()
    hermes = args.hermes.absolute()
    if not source.is_dir() or not (source / "config.yaml").is_file():
        raise ValueError("Source home/config is missing")
    if any(overlaps(a, b) for a, b in ((source, target), (definitions, target), (source, definitions))):
        raise ValueError("Source, target and definitions must not overlap")
    if (source / "config.yaml").is_symlink():
        raise ValueError("Source config must not be a symlink")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError("Target must be absent or empty")
    if args.launcher and os.path.lexists(args.launcher):
        raise ValueError("Launcher alias already exists")
    if args.launcher:
        args.launcher = args.launcher.parent.resolve() / args.launcher.name
        if any(args.launcher.is_relative_to(root) for root in (source, target, definitions)):
            raise ValueError("Launcher alias must be outside input and target trees")
    if not hermes.is_file() or not os.access(hermes, os.X_OK):
        raise ValueError("An executable provisioned Hermes launcher is required")
    manifest = json.loads((definitions / "manifest.json").read_text())
    if manifest["agent_id"] != "architect":
        raise ValueError("Only the Architect pilot is supported")
    if not (definitions / "SOUL.md").is_file():
        raise ValueError("Architect SOUL is required")
    roots = [source / name for name in CAPABILITIES]
    for root in args.allow_capability_root:
        root = root.resolve()
        if root.name not in CAPABILITIES or any(overlaps(root, p) for p in (source, target, definitions)):
            raise ValueError("Explicit shared roots must be separate capability directories")
        roots.append(root)
    plan = []
    for name in CAPABILITIES:
        path = source / name
        if os.path.lexists(path):
            plan.extend(capability_plan(path, target / name, source, target, roots))
    for name in (*PRIVATE, "state.db"):
        if os.path.lexists(source / name):
            validate_private(source / name)
    os.umask(0o077)
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.chmod(0o700)
    snapshot = target / ".direct-agent/source-snapshot"
    snapshot.mkdir(parents=True)
    for name in PRIVATE:
        if (source / name).exists():
            copy_private(source / name, snapshot / name)
            copy_private(snapshot / name, target / name)
    if (source / "state.db").exists():
        if (source / "state.db").is_symlink():
            raise ValueError("Database must not be a symlink")
        backup_database(source / "state.db", snapshot / "state.db")
        shutil.copy2(snapshot / "state.db", target / "state.db")
    shutil.copy2(source / "config.yaml", snapshot / "config.yaml")
    shutil.copy2(source / "config.yaml", target / "config.yaml")
    copy_capabilities(plan)
    plugins = json.loads(config(hermes, target, "get", "plugins", "--json"))
    enabled = [name for name in plugins.get("enabled", []) if name not in DISABLED]
    disabled = list(dict.fromkeys([*plugins.get("disabled", []), *DISABLED]))
    config(hermes, target, "set", "plugins.enabled", json.dumps(enabled))
    config(hermes, target, "set", "plugins.disabled", json.dumps(disabled))
    shutil.copy2(definitions / "SOUL.md", target / "SOUL.md")
    shutil.copy2(definitions / "manifest.json", target / ".direct-agent/manifest.json")
    write_launcher(target, hermes, args.launcher)
    print("Architect home installed; source unchanged. Private state output suppressed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("install")
    for name in ("source", "target", "definitions", "hermes"):
        command.add_argument("--" + name, type=Path, required=True)
    command.add_argument("--launcher", type=Path, help="Optional new alias; never overwrites")
    command.add_argument("--allow-capability-root", type=Path, action="append", default=[],
                         help="Explicit shared skills/scripts/references/plugins/skins directory (repeatable)")
    args = parser.parse_args()
    try:
        install(args)
    except (OSError, ValueError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        reason = str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else "I/O or data failure"
        print(f"Install refused or failed: {reason}. Inspect target before retrying.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
