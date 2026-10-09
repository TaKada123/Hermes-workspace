#!/usr/bin/env python3
"""Install the isolated native Hermes design profile and Main router."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "runtime-config"
CONTRACT_PATH = SOURCE / "profiles" / "design" / "profile-contract.json"
PROFILE_NAME = "design"
IDENTITY_MARKERS = ("config.yaml", ".env", "SOUL.md", "profile.yaml", "auth.json", "state.db")


def _hermes_root() -> Path:
    raw = os.environ.get("HERMES_HOME")
    if not raw:
        return Path.home() / ".hermes"
    home = Path(raw).expanduser().resolve()
    if home.parent.name == "profiles":
        return home.parent.parent
    return home


def _hermes() -> str:
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("hermes executable not found; publish launchers before installing the design profile")
    return executable


def _run(*args: str) -> str:
    completed = subprocess.run(
        [_hermes(), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"hermes {' '.join(args)} failed: {detail}")
    return completed.stdout


def _config_value(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def _set(profile: str | None, key: str, value: Any) -> None:
    prefix = ("-p", profile) if profile else ()
    _run(*prefix, "config", "set", key, _config_value(value))


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _backup_root(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / "backups" / "design-profile" / stamp


def _copy_file(src: Path, dst: Path, backup: Path, root: Path) -> bool:
    if not src.is_file():
        raise FileNotFoundError(src)
    payload = src.read_bytes()
    if dst.is_file() and dst.read_bytes() == payload:
        return False
    if dst.is_file():
        target = backup / dst.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, target)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _copy_tree(src: Path, dst: Path, backup: Path, root: Path) -> int:
    if not src.is_dir():
        raise FileNotFoundError(src)
    changed = 0
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        changed += int(_copy_file(path, dst / path.relative_to(src), backup, root))
    return changed


def _profile_exists(profile_home: Path) -> bool:
    return profile_home.is_dir() and any((profile_home / name).exists() for name in IDENTITY_MARKERS)


def _ensure_profile(profile_home: Path, description: str) -> bool:
    if _profile_exists(profile_home):
        return False
    _run(
        "profile",
        "create",
        PROFILE_NAME,
        "--no-skills",
        "--description",
        description,
    )
    if not _profile_exists(profile_home):
        raise RuntimeError(f"native profile creation did not publish {profile_home}")
    return True


def _install_profile_files(contract: dict[str, Any], root: Path, profile_home: Path, backup: Path) -> int:
    source = SOURCE / "profiles" / PROFILE_NAME
    changed = 0
    for rel in ("SOUL.md", "memories/USER.md", "memories/MEMORY.md"):
        changed += int(_copy_file(source / rel, profile_home / rel, backup, root))
    changed += _copy_tree(source / "memories" / "design", profile_home / "memories" / "design", backup, root)
    changed += _copy_tree(source / "skills", profile_home / "skills", backup, root)

    for rel in contract["profile_skills_from_default"]:
        changed += _copy_tree(root / "skills" / rel, profile_home / "skills" / rel, backup, root)

    policy_dst = profile_home / "policies"
    for src in sorted((SOURCE / "policies").glob("*.md")):
        changed += int(_copy_file(src, policy_dst / src.name, backup, root))
    for src, name in (
        (SOURCE / "MASTER_SPEC.md", "MASTER_SPEC.md"),
        (SOURCE / "CHANGELOG.md", "CHANGELOG.md"),
        (SOURCE / "action_registry.json", "action_registry.json"),
    ):
        changed += int(_copy_file(src, policy_dst / name, backup, root))
    return changed


def _configure_main(contract: dict[str, Any], root: Path, backup: Path) -> int:
    changed = _copy_tree(
        SOURCE / "skills" / "routing" / "design-router",
        root / "skills" / "routing" / "design-router",
        backup,
        root,
    )
    config = _read_yaml_mapping(root / "config.yaml")
    existing = (config.get("skills") or {}).get("disabled", [])
    existing = existing if isinstance(existing, list) else []
    disabled = list(existing)
    for name in contract["main_disabled_skills"]:
        if name not in disabled:
            disabled.append(name)
    _set(None, "skills.disabled", disabled)
    return changed


def _configure_design(contract: dict[str, Any], root: Path) -> None:
    model = contract["model"]
    _set(PROFILE_NAME, "model.provider", model["provider"])
    _set(PROFILE_NAME, "model.base_url", model["base_url"])
    _set(PROFILE_NAME, "model.default", model["default"])
    _set(PROFILE_NAME, "agent.reasoning_effort", model["reasoning_effort"])
    _set(PROFILE_NAME, "agent.max_turns", 150)
    _set(PROFILE_NAME, "terminal.backend", contract["terminal"]["backend"])
    _set(PROFILE_NAME, "terminal.cwd", contract["terminal"]["cwd"])
    _set(PROFILE_NAME, "web.backend", "nous")
    _set(PROFILE_NAME, "browser.cloud_provider", "nous")
    _set(PROFILE_NAME, "image_gen.provider", "nous")
    _set(PROFILE_NAME, "memory.memory_enabled", True)
    _set(PROFILE_NAME, "memory.user_profile_enabled", True)
    _set(PROFILE_NAME, "memory.memory_char_limit", 5000)
    _set(PROFILE_NAME, "memory.user_char_limit", 2000)
    _set(PROFILE_NAME, "memory.write_approval", False)
    _set(PROFILE_NAME, "plugins.enabled", [contract["policies"]["plugin"]])
    _set(PROFILE_NAME, "platform_toolsets.cli", contract["toolsets"])

    main_cfg = _read_yaml_mapping(root / "config.yaml")
    defer = ((main_cfg.get("tools") or {}).get("tool_search") or {}).get("defer", [])
    if isinstance(defer, list):
        _set(PROFILE_NAME, "tools.tool_search.defer", defer)

    _run(
        "profile",
        "describe",
        PROFILE_NAME,
        "--text",
        contract["description"],
    )


def main() -> int:
    contract = _read_json(CONTRACT_PATH)
    if contract.get("profile") != PROFILE_NAME:
        raise RuntimeError(f"profile-contract.json must target {PROFILE_NAME}")

    root = _hermes_root()
    profile_home = root / "profiles" / PROFILE_NAME
    backup = _backup_root(root)
    created = _ensure_profile(profile_home, contract["description"])
    profile_changes = _install_profile_files(contract, root, profile_home, backup)
    main_changes = _configure_main(contract, root, backup)
    _configure_design(contract, root)

    print("Design profile installed")
    print(f"  profile: {PROFILE_NAME}")
    print(f"  home: {profile_home}")
    print(f"  created: {str(created).lower()}")
    print(f"  copied/updated profile files: {profile_changes}")
    print(f"  copied/updated Main router files: {main_changes}")
    print(f"  backup (only replaced files): {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
