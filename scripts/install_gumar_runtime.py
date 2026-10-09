#!/usr/bin/env python3
"""Install the fork's runtime configuration into the active HERMES_HOME."""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "runtime-config"
PLUGIN_ID = "gumar-runtime-policy"

# Tools pinned as deferred so the lean tool surface (18 tools instead of 25, ~9.4 KB
# of schemas saved per request) survives a config rewrite or a fresh install. The
# same set is asserted by scripts/verify_gumar_runtime.py::REQUIRED_DEFER.
# NOTE: tools.tool_search.defer is an explicit list that REPLACES the shipped curated
# default, so the curated cold built-ins are repeated here.
REQUIRED_DEFER = (
    # shipped curated cold built-ins
    "computer_use", "session_search", "image_generate", "todo_list", "process_manage",
    "cronjob_manage", "drive_preview", "gui_tour", "desktop_preview", "annotate_preview",
    "show_tip", "desktop_project", "close_terminal", "apply_layout", "read_terminal",
    "read_window_below", "focus_pane",
    # fork additions: cold or login/voice-only tools, all reachable through Tool Search
    "skill_manage", "text_to_speech", "browser_vault_list", "browser_vault_fill",
    "browser_vault_save_login", "browser_vault_enter_code", "browser_vault_unlock",
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".hermes"


def _backup_if_changed(src: Path, dst: Path, backup_root: Path) -> None:
    if not dst.exists() or not dst.is_file():
        return
    try:
        if src.read_bytes() == dst.read_bytes():
            return
    except OSError:
        pass
    target = backup_root / dst.relative_to(_hermes_home())
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dst, target)


def _copy_tree() -> list[str]:
    home = _hermes_home()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = home / "backups" / "runtime-config" / stamp
    installed: list[str] = []

    mappings = [
        (SOURCE / "SOUL.md", home / "SOUL.md"),
        (SOURCE / "memories" / "USER.md", home / "memories" / "USER.md"),
    ]
    mappings += [
        (src, home / "policies" / src.name)
        for src in sorted((SOURCE / "policies").glob("*.md"))
    ]
    mappings.append((SOURCE / "MASTER_SPEC.md", home / "policies" / "MASTER_SPEC.md"))
    mappings.append((SOURCE / "CHANGELOG.md", home / "policies" / "CHANGELOG.md"))
    mappings.append((SOURCE / "action_registry.json", home / "policies" / "action_registry.json"))

    for src, dst in mappings:
        if not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        _backup_if_changed(src, dst, backup_root)
        shutil.copy2(src, dst)
        installed.append(str(dst))

    return installed


def _apply_config() -> int:
    from hermes_cli.config import read_raw_config, save_config

    config = read_raw_config() or {}
    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        config["plugins"] = plugins

    enabled = plugins.get("enabled")
    if not isinstance(enabled, list):
        enabled = []
    if PLUGIN_ID not in enabled:
        enabled.append(PLUGIN_ID)
    plugins["enabled"] = enabled

    # USER.md is a native Hermes memory surface. The supplied profile is larger
    # than the stock 1375-char write budget, so keep it enabled and raise only
    # the user-profile budget; do not alter the user's general MEMORY.md policy.
    memory = config.get("memory")
    if not isinstance(memory, dict):
        memory = {}
        config["memory"] = memory
    memory["memory_enabled"] = True
    memory["user_profile_enabled"] = True
    memory["write_approval"] = False
    current_limit = memory.get("user_char_limit")
    if not isinstance(current_limit, int) or isinstance(current_limit, bool) or current_limit < 4000:
        memory["user_char_limit"] = 4000

    # Pin the deferred tool set. `tools.tool_search.defer` is an explicit list that
    # replaces the shipped curated default, so the curated names are repeated in
    # REQUIRED_DEFER; names added by hand are preserved after ours.
    tools = config.get("tools")
    if not isinstance(tools, dict):
        tools = {}
        config["tools"] = tools
    tool_search = tools.get("tool_search")
    if not isinstance(tool_search, dict):
        tool_search = {}
        tools["tool_search"] = tool_search
    existing = tool_search.get("defer")
    existing = existing if isinstance(existing, list) else []
    pinned = list(REQUIRED_DEFER) + [name for name in existing if name not in REQUIRED_DEFER]
    tool_search["defer"] = pinned

    save_config(config, merge_existing=True)
    return len(pinned)


def main() -> int:
    installed = _copy_tree()
    deferred = _apply_config()
    print(f"Installed Gumar runtime config into {_hermes_home()}")
    print(f"Enabled plugin: {PLUGIN_ID}")
    print(f"Pinned deferred tools: {deferred} (required {len(REQUIRED_DEFER)})")
    for path in installed:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
