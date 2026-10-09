# Ported from the Architecture 2.0 Hermes fork (MIT License)
# Copyright (c) 2025-2026 Dmitry Antipin (multi-agent orchestration fork)
"""Installer/verifier backend-awareness tests (ticket #9).

Subprocess-driven contract tests for ``scripts/install_gumar_runtime.py`` and
``scripts/verify_gumar_runtime.py`` against a temp ``HERMES_HOME`` (the real
home is never touched):

- legacy backend (default ``file``): byte-for-byte behavior as before —
  ``USER.md`` copied verbatim, config applied, re-runs identical, a modified
  home copy is still overwritten, and NO ``memory.db`` appears;
- ``sqlite_v2`` backend (flag set in the home's config.yaml): the installer
  imports the managed ``runtime-config/memories/USER.md`` §-entries into the
  canonical store with ``written_by='installer'``, records
  ``meta['installer_user_md_sha']``, regenerates projections through the
  store, re-runs import nothing (no duplicates, sha marker stable, and a
  hand-edited projection is never overwritten);
- changed-source semantics (function-level, stubbed source path — the real
  runtime-config files are never mutated): new entries imported, stale
  installer-written rows deprecated, provenance claimed on migration-imported
  duplicates;
- the verifier is backend-aware: green on both backends, and it FAILS when
  the managed markers are missing from the v2 canonical store.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools.memory_tool_store import ENTRY_DELIMITER

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "install_gumar_runtime.py"
VERIFIER = ROOT / "scripts" / "verify_gumar_runtime.py"
SOURCE_USER_MD = ROOT / "runtime-config" / "memories" / "USER.md"
SOURCE_BYTES = SOURCE_USER_MD.read_bytes()
SOURCE_ENTRIES = [
    seg.strip()
    for seg in SOURCE_USER_MD.read_text(encoding="utf-8-sig").split(ENTRY_DELIMITER)
    if seg.strip()
]
SOURCE_SHA = hashlib.sha256(SOURCE_BYTES).hexdigest()
INSTALLER_SHA_META_KEY = "installer_user_md_sha"
INSTALLER_WRITER = "installer"


def _subprocess_env(home: Path) -> dict:
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home.parent),
        "HERMES_HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUTF8": "1",
        "PYTHONHASHSEED": "0",
        "TZ": "UTC",
    }


def _run_installer(home: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INSTALLER)],
        cwd=ROOT,
        env=_subprocess_env(home),
        capture_output=True,
        text=True,
        timeout=300,
    )


def _run_verifier(home: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VERIFIER)],
        cwd=ROOT,
        env=_subprocess_env(home),
        capture_output=True,
        text=True,
        timeout=300,
    )


def _set_backend(home: Path, backend: str) -> None:
    """Set ``memory.backend`` in the home's config.yaml (the cutover step)."""
    from ruamel.yaml import YAML

    path = home / "config.yaml"
    yaml = YAML()
    cfg = yaml.load(path.read_text(encoding="utf-8-sig"))
    cfg = cfg if isinstance(cfg, dict) else {}
    memory = cfg.get("memory")
    if not isinstance(memory, dict):
        memory = {}
        cfg["memory"] = memory
    memory["backend"] = backend
    yaml.dump(cfg, path)


def _yaml(home: Path) -> dict:
    from ruamel.yaml import YAML

    path = home / "config.yaml"
    cfg = YAML(typ="safe").load(path.read_text(encoding="utf-8-sig"))
    return cfg if isinstance(cfg, dict) else {}


def _db_rows(home: Path, sql: str, params: tuple = ()) -> list:
    con = sqlite3.connect(str(home / "memories" / "memory.db"))
    try:
        con.row_factory = sqlite3.Row
        return list(con.execute(sql, params).fetchall())
    finally:
        con.close()


def _meta(home: Path, key: str):
    rows = _db_rows(home, "SELECT value FROM meta WHERE key=?", (key,))
    return rows[0]["value"] if rows else None


def _load_installer_module():
    spec = importlib.util.spec_from_file_location(
        "install_gumar_runtime_under_test", INSTALLER
    )
    assert spec is not None and spec.loader is not None, "cannot load installer module"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# (a) legacy backend: byte-for-byte behavior as before
# ---------------------------------------------------------------------------


class TestLegacyBehaviorUnchanged:
    def test_fresh_install_copies_user_md_verbatim_applies_config(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        first = _run_installer(home)
        assert first.returncode == 0, first.stdout + first.stderr

        # USER.md is the byte-for-byte managed copy (legacy behavior).
        assert (home / "memories" / "USER.md").read_bytes() == SOURCE_BYTES
        assert (home / "SOUL.md").is_file()
        assert (home / "policies" / "MASTER_SPEC.md").is_file()

        cfg = _yaml(home)
        assert "gumar-runtime-policy" in (cfg.get("plugins") or {}).get("enabled", [])
        # The config writer strips default-equal keys; assert semantics the
        # way the runtime (and scripts/verify_gumar_runtime.py) reads them.
        memory_cfg = cfg.get("memory") or {}
        assert memory_cfg.get("memory_enabled", True) is True
        assert memory_cfg.get("user_profile_enabled", True) is True
        assert memory_cfg.get("write_approval", False) is False
        assert memory_cfg.get("user_char_limit", 0) >= 4000

        # Legacy backend: the v2 database must never appear.
        assert not (home / "memories" / "memory.db").exists()

        # Second run: identical result, still no v2 DB.
        second = _run_installer(home)
        assert second.returncode == 0, second.stdout + second.stderr
        assert (home / "memories" / "USER.md").read_bytes() == SOURCE_BYTES
        assert not (home / "memories" / "memory.db").exists()

    def test_legacy_still_overwrites_modified_home_copy(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        assert _run_installer(home).returncode == 0

        # Simulate the agent editing USER.md between runs: the legacy
        # installer keeps re-applying the managed copy (unchanged contract).
        (home / "memories" / "USER.md").write_text("agent live memory\n", encoding="utf-8")
        result = _run_installer(home)
        assert result.returncode == 0, result.stdout + result.stderr
        assert (home / "memories" / "USER.md").read_bytes() == SOURCE_BYTES


# ---------------------------------------------------------------------------
# (b) sqlite_v2 backend: idempotent canonical-store import
# ---------------------------------------------------------------------------


class TestV2IdempotentImport:
    def test_cutover_imports_entries_and_rerun_is_stable(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        assert _run_installer(home).returncode == 0  # legacy first install
        _set_backend(home, "sqlite_v2")  # cutover

        result = _run_installer(home)
        assert result.returncode == 0, result.stdout + result.stderr

        # Canonical store created; every managed §-entry is present exactly
        # once, typed legacy, installer-owned.
        db = home / "memories" / "memory.db"
        assert db.exists()
        rows = _db_rows(
            home,
            "SELECT target, type, content, status, written_by FROM memories"
            " WHERE target='user' AND status='active'",
        )
        assert {r["content"] for r in rows} == set(SOURCE_ENTRIES)
        assert all(r["type"] == "legacy" for r in rows)
        assert all(r["written_by"] == INSTALLER_WRITER for r in rows)
        assert _meta(home, INSTALLER_SHA_META_KEY) == SOURCE_SHA

        # Projections exist and are store-regenerated (never hand-copied).
        assert (home / "memories" / "USER.md").is_file()
        assert (home / "memories" / "MEMORY.md").is_file()

        count = len(rows)

        # Simulate the agent editing the projection after cutover.
        (home / "memories" / "USER.md").write_text("canary\n", encoding="utf-8")

        second = _run_installer(home)
        assert second.returncode == 0, second.stdout + second.stderr

        # No duplicates, sha marker untouched, projection NOT overwritten.
        rows2 = _db_rows(
            home,
            "SELECT content FROM memories WHERE target='user' AND status='active'",
        )
        assert len(rows2) == count
        assert _meta(home, INSTALLER_SHA_META_KEY) == SOURCE_SHA
        assert (home / "memories" / "USER.md").read_text(encoding="utf-8") == "canary\n"

    def test_verifier_green_after_v2_install(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        assert _run_installer(home).returncode == 0
        _set_backend(home, "sqlite_v2")
        assert _run_installer(home).returncode == 0

        verified = _run_verifier(home)
        assert verified.returncode == 0, verified.stdout + verified.stderr


# ---------------------------------------------------------------------------
# (c) changed-source semantics (function-level, stubbed source path)
# ---------------------------------------------------------------------------


class TestChangedSourceImport:
    def test_changed_source_imports_new_and_deprecates_stale(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        (home / "memories").mkdir(parents=True)
        monkeypatch.setenv("HERMES_HOME", str(home))
        module = _load_installer_module()

        stub = tmp_path / "stub-user.md"  # never touches runtime-config
        stub.write_text("Запись А\n§\nЗапись Б", encoding="utf-8")

        first = module._import_managed_user_memory(home, stub)
        assert first["status"] == "imported"
        assert first["imported"] == 2
        assert _meta(home, INSTALLER_SHA_META_KEY) == hashlib.sha256(
            stub.read_bytes()
        ).hexdigest()

        rows = _db_rows(home, "SELECT content, status, written_by FROM memories WHERE target='user'")
        assert {(r["content"], r["status"]) for r in rows} == {
            ("Запись А", "active"),
            ("Запись Б", "active"),
        }
        assert all(r["written_by"] == INSTALLER_WRITER for r in rows)

        # Source changes: Б removed, В added.
        stub.write_text("Запись А\n§\nЗапись В", encoding="utf-8")
        second = module._import_managed_user_memory(home, stub)
        assert second["imported"] == 1
        assert second["deprecated"] == 1
        assert _meta(home, INSTALLER_SHA_META_KEY) == hashlib.sha256(
            stub.read_bytes()
        ).hexdigest()

        by_content = {
            r["content"]: r
            for r in _db_rows(home, "SELECT content, status, written_by FROM memories WHERE target='user'")
        }
        assert len(by_content) == 3  # no duplicate rows ever
        assert by_content["Запись А"]["status"] == "active"
        assert by_content["Запись Б"]["status"] == "deprecated"  # hidden, kept for audit
        assert by_content["Запись В"]["status"] == "active"
        assert by_content["Запись В"]["written_by"] == INSTALLER_WRITER

    def test_migration_imported_duplicates_are_claimed_not_duplicated(
        self, tmp_path, monkeypatch
    ):
        home = tmp_path / "home"
        (home / "memories").mkdir(parents=True)
        # A pre-cutover flat USER.md: the one-shot legacy migration imports
        # it WITHOUT provenance; the installer must CLAIM the matching row
        # instead of adding a duplicate.
        (home / "memories" / "USER.md").write_text("Старая копия профиля", encoding="utf-8")
        monkeypatch.setenv("HERMES_HOME", str(home))
        module = _load_installer_module()

        stub = tmp_path / "stub-user.md"
        stub.write_text("Старая копия профиля\n§\nНовая запись", encoding="utf-8")
        report = module._import_managed_user_memory(home, stub)
        assert report["claimed"] == 1
        assert report["imported"] == 1

        rows = _db_rows(
            home, "SELECT content, written_by FROM memories WHERE target='user' AND status='active'"
        )
        assert {(r["content"], r["written_by"]) for r in rows} == {
            ("Старая копия профиля", INSTALLER_WRITER),
            ("Новая запись", INSTALLER_WRITER),
        }

        # Idempotent re-run with the unchanged stub: nothing at all.
        again = module._import_managed_user_memory(home, stub)
        assert again["status"] == "unchanged"
        assert again["imported"] == 0
        assert len(
            _db_rows(home, "SELECT content FROM memories WHERE target='user' AND status='active'")
        ) == 2


# ---------------------------------------------------------------------------
# (d) verifier behavior on both backends
# ---------------------------------------------------------------------------


class TestVerifierBackendAware:
    def test_verifier_green_on_legacy_home(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        assert _run_installer(home).returncode == 0

        verified = _run_verifier(home)
        assert verified.returncode == 0, verified.stdout + verified.stderr

    def test_verifier_fails_when_canonical_marker_row_removed(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        assert _run_installer(home).returncode == 0
        _set_backend(home, "sqlite_v2")
        assert _run_installer(home).returncode == 0
        assert _run_verifier(home).returncode == 0

        # Remove the canonical row carrying the managed markers. The stale
        # projection still holds the text — the verifier must check the
        # canonical store and fail on the mismatch.
        con = sqlite3.connect(str(home / "memories" / "memory.db"))
        con.execute("DELETE FROM memories WHERE target='user' AND content LIKE '%EndeavourOS%'")
        con.commit()
        con.close()

        failed = _run_verifier(home)
        assert failed.returncode != 0
        assert "EndeavourOS" in (failed.stdout + failed.stderr)
        assert "canonical" in (failed.stdout + failed.stderr)
