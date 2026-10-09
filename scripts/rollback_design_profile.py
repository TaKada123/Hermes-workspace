#!/usr/bin/env python3
"""Undo the Design Agent installation (profile, Main routing, policy edits).

Restores every pre-change file from the recorded backup manifest, removes the
native `design` profile and the files this installation created, then re-applies
the untouched runtime configuration.

Dry-run first:
    python scripts/rollback_design_profile.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP = Path.home() / ".hermes" / "backups" / "design-agent"
CREATED_PATHS = (
    "runtime-config/profiles/design",
    "runtime-config/skills/routing/design-router",
    "scripts/install_design_profile.py",
    "scripts/verify_design_profile.py",
)
PROFILE_NAME = "design"


def _latest_manifest(backup: Path | None) -> Path:
    if backup is not None:
        return backup / "manifest.json"
    candidates = sorted((p / "manifest.json" for p in DEFAULT_BACKUP.glob("*") if p.is_dir()), reverse=True)
    if not candidates:
        raise SystemExit(f"no backup manifest found under {DEFAULT_BACKUP}")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, default=None, help="backup directory holding manifest.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-profile", action="store_true", help="do not delete the design profile home")
    args = parser.parse_args()

    manifest_path = _latest_manifest(args.backup)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    print(f"manifest: {manifest_path}")
    print(f"mode: {'dry-run' if args.dry_run else 'apply'}")

    for row in manifest.get("files", []):
        src, dst = Path(row["backup"]), Path(row["path"])
        if not src.is_file():
            print(f"  ! missing backup copy for {dst}")
            continue
        print(f"  restore {dst}")
        if not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for rel in CREATED_PATHS:
        target = REPO_ROOT / rel
        if target.exists():
            print(f"  remove {target}")
            if not args.dry_run:
                shutil.rmtree(target) if target.is_dir() else target.unlink()

    if not args.keep_profile:
        hermes = shutil.which("hermes")
        if hermes is None:
            print("  ! hermes executable not found; delete the profile manually")
        else:
            print(f"  delete profile {PROFILE_NAME}")
            if not args.dry_run:
                subprocess.run([hermes, "profile", "delete", "-y", PROFILE_NAME], timeout=180)

    installer = REPO_ROOT / "scripts" / "install_gumar_runtime.py"
    if installer.is_file():
        print("  re-apply runtime configuration (install_gumar_runtime.py)")
        if not args.dry_run:
            env = dict(os.environ)
            result = subprocess.run(
                ["python3", str(installer)], cwd=REPO_ROOT, env=env, timeout=600,
                text=True, encoding="utf-8", errors="replace", capture_output=True,
            )
            print(result.stdout.strip() or result.stderr.strip())

    print("rollback complete" if not args.dry_run else "dry-run complete; nothing was changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
