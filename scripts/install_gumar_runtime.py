#!/usr/bin/env python3
"""Install the fork's runtime configuration into the active HERMES_HOME.

Legacy backend (``memory.backend: file`` — the default): byte-for-byte the
behavior it always had — the managed files (including
``runtime-config/memories/USER.md``) are copied over the home, config defaults
are applied, replaced files land in ``backups/``.

``sqlite_v2`` backend: ``memories/USER.md`` is NOT copied. Instead the managed
§-entries of ``runtime-config/memories/USER.md`` are imported IDEMPOTENTLY into
the canonical SQLite store (``memories/memory.db``) through the store's PUBLIC
``MemoryStoreV2.import_managed_entries`` API with ``written_by`` =
``installer``:

- a fresh load runs the one-shot legacy migration first (``load_from_disk``);
- the store owns the sha marker (``meta['managed_import_sha:installer']``):
  an unchanged sha imports NOTHING (no duplicate rows);
- a CHANGED sha imports new entries, claims provenance on matching
  migration-imported rows, and deprecates stale installer-written user rows
  (status ``deprecated`` — hidden but kept for audit);
- projections are only ever regenerated THROUGH the store (never written by
  this script directly) and never overwritten on a no-op re-run.

Error policy: the legacy copy path stays fail-safe exactly as before; the v2
import is fail-CLOSED — any store error aborts the install with a clear
message, because silently skipping the managed profile import would degrade a
documented guarantee (the managed USER.md is part of the shipped runtime).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "runtime-config"
PLUGIN_ID = "gumar-runtime-policy"

# Provenance of rows imported from the managed runtime-config profile (the
# store's meta marker key derives from this: ``managed_import_sha:installer``).
INSTALLER_WRITER = "installer"

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


def _copy_tree(skip_user_md: bool = False) -> list[str]:
    home = _hermes_home()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = home / "backups" / "runtime-config" / stamp
    installed: list[str] = []

    mappings = [
        (SOURCE / "SOUL.md", home / "SOUL.md"),
    ]
    if not skip_user_md:
        mappings.append((SOURCE / "memories" / "USER.md", home / "memories" / "USER.md"))
    mappings += [
        (src, home / "policies" / src.name)
        for src in sorted((SOURCE / "policies").glob("*.md"))
    ]
    mappings.append((SOURCE / "MASTER_SPEC.md", home / "policies" / "MASTER_SPEC.md"))
    mappings.append((SOURCE / "CHANGELOG.md", home / "policies" / "CHANGELOG.md"))
    mappings.append((SOURCE / "action_registry.json", home / "policies" / "action_registry.json"))

    # Install the policy plugin as a user override: the active release may be
    # older than this runtime bundle. Never mutate an immutable release tree.
    plugin_source = REPO_ROOT / "plugins" / PLUGIN_ID
    mappings.extend(
        (plugin_source / name, home / "plugins" / PLUGIN_ID / name)
        for name in ("__init__.py", "registry.py", "plugin.yaml")
    )
    # Only the explicit Blender craft exception is shared with Main, not the
    # design profile's memories or wider design skill catalog.
    for relative in (
        "routing/design-router",
        "software-development/blender-mcp",
        "video/cinedance",
        "video/acting-system",
        "creative/lira-image-prompts",
    ):
        skill_source = SOURCE / "skills" / relative
        mappings.extend(
            (src, home / "skills" / relative / src.relative_to(skill_source))
            for src in sorted(skill_source.rglob("*"))
            if src.is_file() and "__pycache__" not in src.parts
        )

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


def _resolve_backend() -> str:
    """Resolve the TARGET home's memory backend after _apply_config.

    The ONE resolver the runtime uses (``tools.memory_tool.resolve_memory_backend``)
    so the installer can never diverge from ``agent_init``/``load_on_disk_store``:
    a fresh home has no flag and stays legacy ``file``.
    """
    from hermes_cli.config import read_raw_config
    from tools.memory_tool import resolve_memory_backend

    return resolve_memory_backend(read_raw_config())


def _split_managed_entries(source: Path) -> list[str]:
    """Managed §-entries of the source file (strict utf-8-sig, empties dropped).

    Same splitting contract as the legacy migration (``_migrate_legacy_files``):
    a file without § separators is ONE entry.
    """
    from tools.memory_tool_store import ENTRY_DELIMITER

    raw = source.read_text(encoding="utf-8-sig")
    return [seg.strip() for seg in raw.split(ENTRY_DELIMITER) if seg.strip()]


def _import_managed_user_memory(home: Path, source: Path) -> dict:
    """Idempotently import the managed USER.md §-entries into the canonical store.

    Thin wrapper over the store's PUBLIC ``import_managed_entries`` (the
    idempotent transactional import — sha marker, claim/deprecate logic —
    lives in the store, not here). Runs the one-shot legacy migration via
    ``load_from_disk``, then delegates. Returns the store's report dict;
    raises on any store error (fail-closed — see module docstring).
    """
    from agent.memory_store_v2 import MemoryStoreV2

    store = MemoryStoreV2(db_path=home / "memories" / "memory.db")
    try:
        store.load_from_disk()
        entries = _split_managed_entries(source)
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        return store.import_managed_entries(
            entries, target="user", written_by=INSTALLER_WRITER, source_sha=sha,
        )
    finally:
        store.close()


def main() -> int:
    home = _hermes_home()
    deferred = _apply_config()
    backend = _resolve_backend()
    installed = _copy_tree(skip_user_md=(backend == "sqlite_v2"))
    print(f"Installed Gumar runtime config into {home}")
    print(f"Enabled plugin: {PLUGIN_ID}")
    print(f"Pinned deferred tools: {deferred} (required {len(REQUIRED_DEFER)})")
    for path in installed:
        print(f"  - {path}")
    if backend == "sqlite_v2":
        print(f"Memory backend: sqlite_v2 — idempotent import of {SOURCE / 'memories' / 'USER.md'}")
        try:
            report = _import_managed_user_memory(home, SOURCE / "memories" / "USER.md")
        except Exception as exc:
            # Fail-closed: silently skipping the managed profile import would
            # degrade a documented guarantee of the shipped runtime.
            print(
                f"error: failed to import managed USER.md into the sqlite_v2 store: {exc}",
                file=sys.stderr,
            )
            return 1
        if report["status"] == "unchanged":
            print(
                "  managed entries unchanged (sha "
                f"{report['sha'][:12]}); no rows touched"
            )
        else:
            print(
                f"  imported: {report['imported']}, claimed: {report['claimed']},"
                f" deprecated: {report['deprecated']}, sha {report['sha'][:12]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
