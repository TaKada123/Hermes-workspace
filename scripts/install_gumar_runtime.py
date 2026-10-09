#!/usr/bin/env python3
"""Install the fork's runtime configuration into the active HERMES_HOME.

Legacy backend (``memory.backend: file`` — the default): byte-for-byte the
behavior it always had — the managed files (including
``runtime-config/memories/USER.md``) are copied over the home, config defaults
are applied, replaced files land in ``backups/``.

``sqlite_v2`` backend: ``memories/USER.md`` is NOT copied. Instead the managed
§-entries of ``runtime-config/memories/USER.md`` are imported IDEMPOTENTLY into
the canonical SQLite store (``memories/memory.db``) with ``written_by`` =
``installer``:

- a fresh load runs the one-shot legacy migration first (``load_from_disk``);
- ``meta['installer_user_md_sha']`` = sha256 of the managed source file is the
  idempotency marker: an unchanged sha imports NOTHING (no duplicate rows);
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
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "runtime-config"
PLUGIN_ID = "gumar-runtime-policy"

# Provenance of rows imported from the managed runtime-config profile.
INSTALLER_WRITER = "installer"
# meta key holding the sha256 of the managed USER.md source at last import —
# the idempotency marker (read by tickets #9/#11, never the agent).
INSTALLER_USER_MD_SHA_KEY = "installer_user_md_sha"

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _projection_paths(store) -> dict[str, Path]:
    """MEMORY.md/USER.md projection paths for the target home (store-owned paths)."""
    return {"memory": store._path_for("memory"), "user": store._path_for("user")}


def _import_managed_user_memory(home: Path, source: Path) -> dict:
    """Idempotently import the managed USER.md §-entries into the canonical store.

    Runs the one-shot legacy migration if needed (``load_from_disk``), then:

    - unchanged ``meta['installer_user_md_sha']`` → import NOTHING (only a
      missing projection is regenerated through the store; existing projection
      files are never touched);
    - otherwise one transaction imports every source §-entry as a user-target
      ``legacy`` row with ``written_by='installer'``, claims provenance on
      matching migration-imported rows (``written_by`` NULL), re-activates
      deprecated rows whose content returned to the managed source, and
      deprecates stale installer-written user rows (hidden, kept for audit).

    Projections are regenerated THROUGH the store after the import. Returns a
    report dict; raises on any store error (fail-closed — see module docstring).
    """
    from agent.memory_store_v2 import MemoryStoreV2

    store = MemoryStoreV2(db_path=home / "memories" / "memory.db")
    try:
        store.load_from_disk()

        entries = _split_managed_entries(source)
        sha = hashlib.sha256(source.read_bytes()).hexdigest()

        rows = store._query(
            "SELECT value FROM meta WHERE key = ?", (INSTALLER_USER_MD_SHA_KEY,)
        )
        previous_sha = rows[0][0] if rows else None

        if previous_sha == sha:
            # Idempotent no-op: never re-import, never overwrite projections.
            # Regenerate only MISSING projection files (the store regenerates
            # them; a missing derived view is not an overwrite).
            for target, path in _projection_paths(store).items():
                if not path.is_file():
                    store._rewrite_projection(target)
            return {
                "status": "unchanged",
                "imported": 0,
                "claimed": 0,
                "deprecated": 0,
                "sha": sha,
            }

        def _txn(conn) -> tuple[int, int, int]:
            imported = 0
            claimed = 0
            deprecated = 0
            for entry in entries:
                row = conn.execute(
                    "SELECT id, written_by, status FROM memories"
                    " WHERE target='user' AND content=? LIMIT 1",
                    (entry,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO memories(id, target, type, content, importance,"
                        " confidence, status, project, written_by, created_at, updated_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            str(uuid.uuid4()), "user", "legacy", entry, 0.5, 0.7,
                            "active", None, INSTALLER_WRITER, _now(), _now(),
                        ),
                    )
                    imported += 1
                elif row["status"] == "deprecated":
                    # The entry returned to the managed source: re-activate it.
                    conn.execute(
                        "UPDATE memories SET status='active', updated_at=?"
                        " WHERE id=?",
                        (_now(), row["id"]),
                    )
                    if not row["written_by"]:
                        conn.execute(
                            "UPDATE memories SET written_by=? WHERE id=?",
                            (INSTALLER_WRITER, row["id"]),
                        )
                        claimed += 1
                    imported += 1
                elif not row["written_by"]:
                    # Migration-imported duplicate (flat files carry no
                    # provenance): claim it instead of duplicating.
                    conn.execute(
                        "UPDATE memories SET written_by=? WHERE id=?",
                        (INSTALLER_WRITER, row["id"]),
                    )
                    claimed += 1
                # else: already installer-owned, or another writer owns this
                # exact content — leave the row untouched.
            stale = conn.execute(
                "SELECT id, content FROM memories WHERE target='user'"
                " AND written_by=? AND status IN ('active','pinned')",
                (INSTALLER_WRITER,),
            ).fetchall()
            for row in stale:
                if row["content"] not in entries:
                    conn.execute(
                        "UPDATE memories SET status='deprecated', updated_at=?"
                        " WHERE id=?",
                        (_now(), row["id"]),
                    )
                    deprecated += 1
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (INSTALLER_USER_MD_SHA_KEY, sha),
            )
            return imported, claimed, deprecated

        imported, claimed, deprecated = store._execute_write(_txn)

        # Projections are derived views: regenerate them THROUGH the store
        # (this script never writes the files directly).
        for target in ("memory", "user"):
            store._rewrite_projection(target)

        return {
            "status": "imported",
            "imported": imported,
            "claimed": claimed,
            "deprecated": deprecated,
            "sha": sha,
        }
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
